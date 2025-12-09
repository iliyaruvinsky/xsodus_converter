"""SQL renderer that converts Scenario IR to target database SQL."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from ..domain import (
    AggregationNode,
    AggregationSpec,
    DataSource,
    Expression,
    ExpressionType,
    JoinNode,
    JoinType,
    Node,
    NodeKind,
    Predicate,
    PredicateKind,
    RankNode,
    Scenario,
    UnionNode,
)
from ..domain.types import DatabaseMode, HanaVersion, XMLFormat
from .function_translator import translate_hana_function, translate_raw_formula, _substitute_placeholders


@dataclass(slots=True)
class RenderContext:
    """Context for SQL rendering."""

    scenario: Scenario
    schema_overrides: Dict[str, str]
    target_schema: Optional[str]
    client: str
    language: str
    database_mode: DatabaseMode
    hana_version: Optional[HanaVersion]
    xml_format: Optional[XMLFormat]
    cte_aliases: Dict[str, str]
    warnings: List[str]
    currency_udf: Optional[str] = None
    currency_schema: Optional[str] = None
    currency_table: Optional[str] = None

    def __init__(
        self,
        scenario: Scenario,
        schema_overrides: Optional[Dict[str, str]] = None,
        target_schema: Optional[str] = None,
        client: Optional[str] = None,
        language: Optional[str] = None,
        database_mode: DatabaseMode = DatabaseMode.SNOWFLAKE,
        hana_version: Optional[HanaVersion] = None,
        xml_format: Optional[XMLFormat] = None,
        currency_udf: Optional[str] = None,
        currency_schema: Optional[str] = None,
        currency_table: Optional[str] = None,
    ):
        self.scenario = scenario
        self.schema_overrides = schema_overrides or {}
        self.target_schema = target_schema  # Universal target schema for all table references
        self.client = client or scenario.metadata.default_client or "PROD"
        self.language = language or scenario.metadata.default_language or "EN"
        self.database_mode = database_mode
        self.hana_version = hana_version
        self.xml_format = xml_format
        self.cte_aliases = {}
        self.warnings = []
        self.currency_udf = currency_udf
        self.currency_schema = currency_schema
        self.currency_table = currency_table

    def get_cte_alias(self, node_id: str) -> str:
        """Get or create a CTE alias for a node."""
        if node_id not in self.cte_aliases:
            # CRITICAL FIX: Clean XML metadata prefixes (#/0/, #//, #/N/) before creating alias
            # This prevents invalid SQL like "FROM 0/prj_visits" (should be "FROM prj_visits")
            from ..parser.scenario_parser import _clean_ref
            import re
            cleaned = _clean_ref(node_id)
            # Also strip bare digit+slash prefixes (e.g., "0/prj_visits" -> "prj_visits")
            # SQL identifiers cannot start with digits, so we must remove patterns like "0/", "1/", etc.
            cleaned = re.sub(r'^\d+/', '', cleaned)
            normalized = cleaned.lower().replace(" ", "_").replace("/", "_")
            self.cte_aliases[node_id] = normalized
        return self.cte_aliases[node_id]

    def resolve_schema(self, schema_name: str) -> str:
        """Resolve schema name with overrides.

        If target_schema is set, use it for ALL schema references (cross-system migration).
        Otherwise, use schema_overrides for specific mappings.
        """
        # If target_schema is set, use it for all table schema references
        if self.target_schema:
            return self.target_schema
        # Otherwise, check individual schema overrides
        return self.schema_overrides.get(schema_name, schema_name)


def render_scenario(
    scenario: Scenario,
    schema_overrides: Optional[Dict[str, str]] = None,
    target_schema: Optional[str] = None,
    client: Optional[str] = None,
    language: Optional[str] = None,
    database_mode: DatabaseMode = DatabaseMode.SNOWFLAKE,
    hana_version: Optional[HanaVersion] = None,
    xml_format: Optional[XMLFormat] = None,
    create_view: bool = False,
    view_name: Optional[str] = None,
    currency_udf: Optional[str] = None,
    currency_schema: Optional[str] = None,
    currency_table: Optional[str] = None,
    return_warnings: bool = False,
    validate: bool = True,
) -> str | tuple[str, list[str]]:
    """Render a Scenario IR to target database SQL.
    
    Args:
        database_mode: Target database system (Snowflake/HANA)
        hana_version: HANA version for version-specific SQL (when mode=HANA)
        xml_format: XML format type for context (ColumnView/Calculation:scenario)
        return_warnings: If True, returns (sql, warnings) tuple; otherwise returns sql string only.
        validate: If True, validate the generated SQL (default: True).
    
    Returns:
        SQL string, or (sql, warnings) tuple if return_warnings=True.
    """

    ctx = RenderContext(
        scenario,
        schema_overrides,
        target_schema,
        client,
        language,
        database_mode,
        hana_version,
        xml_format,
        currency_udf,
        currency_schema,
        currency_table,
    )
    ordered_nodes = _topological_sort(scenario)
    ctes: List[str] = []

    for node_id in ordered_nodes:
        if node_id in scenario.data_sources:
            continue
        if node_id not in scenario.nodes:
            ctx.warnings.append(f"Node {node_id} referenced but not found")
            continue
        node = scenario.nodes[node_id]
        cte_sql = _render_node(ctx, node)
        if cte_sql:
            cte_alias = ctx.get_cte_alias(node_id)
            ctes.append(f"  {cte_alias} AS (\n    {cte_sql.replace(chr(10), chr(10) + '    ')}\n  )")

    final_node_id = _find_final_node(scenario, ordered_nodes)
    if not final_node_id:
        # Critical error: Missing final node
        error_msg = "No terminal node found - cannot generate valid SQL"
        ctx.warnings.append(error_msg)
        # If no CTEs exist, create a placeholder to avoid invalid SQL
        if not ctes:
            placeholder_cte = "  final AS (\n    SELECT NULL AS placeholder\n  )"
            ctes.append(placeholder_cte)
            ctx.cte_aliases["final"] = "final"
        final_select = "SELECT * FROM final" if ctes else ""
        sql = _assemble_sql(ctes, final_select, ctx.warnings, scenario=scenario)
        # Note: We still return SQL with placeholder, but validation will catch this as error
        if validate:
            from .validator import ValidationResult
            validation_result = ValidationResult()
            validation_result.add_error(error_msg, "MISSING_FINAL_NODE")
            if validation_result.has_errors:
                error_msg_full = "; ".join([str(e) for e in validation_result.errors])
                raise ValueError(f"SQL validation failed: {error_msg_full}")
        return (sql, ctx.warnings) if return_warnings else sql

    # Check if final_node_id is a data source (not a rendered CTE)
    if final_node_id in scenario.data_sources:
        # Use the data source directly in FROM clause
        from_clause = _render_from(ctx, final_node_id)
        
        # If we have a logical model, select its attributes instead of *
        if scenario.logical_model and scenario.logical_model.attributes:
            select_items: List[str] = []
            table_alias = final_node_id
            
            # Add regular attributes from logical model
            for attr in scenario.logical_model.attributes:
                if attr.column_name:
                    col_expr = f"{from_clause}.{attr.column_name}"
                    select_items.append(f"{col_expr} AS {_quote_identifier(attr.name)}")
            
            # Add calculated attributes from logical model
            for calc_attr in scenario.logical_model.calculated_attributes:
                # For RAW expressions, qualify column references with table name
                if calc_attr.expression.expression_type == ExpressionType.RAW:
                    formula = calc_attr.expression.value
                    # Replace quoted column names with qualified table.column references
                    import re
                    def qualify_column(match):
                        col_name = match.group(1)
                        return f"{from_clause}.{_quote_identifier(col_name)}"
                    formula = re.sub(r'"([^"]+)"', qualify_column, formula)
                    # Translate HANA syntax to target database
                    from .function_translator import translate_raw_formula
                    # Create a minimal context for translation
                    class FormulaContext:
                        def __init__(self, ctx):
                            self.client = ctx.client
                            self.language = ctx.language
                            self.database_mode = ctx.database_mode
                            self.hana_version = ctx.hana_version
                    formula_ctx = FormulaContext(ctx)
                    col_expr = translate_raw_formula(formula, formula_ctx)
                else:
                    col_expr = _render_expression(ctx, calc_attr.expression, from_clause)
                select_items.append(f"{col_expr} AS {_quote_identifier(calc_attr.name)}")
            
            if select_items:
                select_clause = ",\n    ".join(select_items)
                final_select = f"SELECT\n    {select_clause}\nFROM {from_clause}"
            else:
                final_select = f"SELECT * FROM {from_clause}"
        else:
            final_select = f"SELECT * FROM {from_clause}"
        
        if create_view:
            view = view_name or scenario.metadata.scenario_id
            sql = _assemble_sql(ctes, final_select, ctx.warnings, view_name=view, database_mode=ctx.database_mode, scenario=scenario)
        else:
            sql = _assemble_sql(ctes, final_select, ctx.warnings, database_mode=ctx.database_mode, scenario=scenario)
        return (sql, ctx.warnings) if return_warnings else sql

    final_alias = ctx.cte_aliases.get(final_node_id, "final")
    # If final_node_id is not in cte_aliases, the node wasn't rendered as a CTE
    # Create a placeholder CTE to avoid invalid SQL
    if final_node_id not in ctx.cte_aliases:
        if not ctes:
            placeholder_cte = "  final AS (\n    SELECT NULL AS placeholder\n  )"
            ctes.append(placeholder_cte)
            ctx.cte_aliases["final"] = "final"
            ctx.warnings.append(f"Final node {final_node_id} referenced but not found in CTEs; using placeholder CTE")
        else:
            # If we have CTEs but final_node_id is missing, use the last CTE
            ctx.warnings.append(f"Final node {final_node_id} referenced but not found in CTEs; using last CTE")
            final_alias = list(ctx.cte_aliases.values())[-1] if ctx.cte_aliases else "final"
    # Get column list from final node
    final_node = scenario.nodes.get(final_node_id)
    if final_node and final_node.view_attributes:
        # Use explicit column list
        column_list = ", ".join([_quote_identifier(col) for col in final_node.view_attributes])
        final_select = f"SELECT {column_list} FROM {final_alias}"
    else:
        final_select = f"SELECT * FROM {final_alias}"

    if create_view:
        view = view_name or scenario.metadata.scenario_id
        sql = _assemble_sql(ctes, final_select, ctx.warnings, view_name=view, database_mode=ctx.database_mode, scenario=scenario)
    else:
        sql = _assemble_sql(ctes, final_select, ctx.warnings, database_mode=ctx.database_mode, scenario=scenario)
    
    # Validate SQL if enabled
    if validate:
        from .validator import (
            analyze_query_complexity,
            validate_performance,
            validate_query_completeness,
            validate_snowflake_specific,
            validate_sql_structure,
        )
        
        structure_result = validate_sql_structure(sql)
        completeness_result = validate_query_completeness(scenario, sql, ctx)
        performance_result = validate_performance(sql, scenario)
        snowflake_result = validate_snowflake_specific(sql)
        complexity_result = analyze_query_complexity(sql, scenario)
        
        # Merge validation results
        all_results = [structure_result, completeness_result, performance_result, snowflake_result, complexity_result]
        if any(r.has_errors for r in all_results):
            # Collect all errors
            all_errors = []
            for r in all_results:
                all_errors.extend(r.errors)
            error_msg = "; ".join([str(e) for e in all_errors])
            raise ValueError(f"SQL validation failed: {error_msg}")
        
        # Merge warnings into context warnings
        for result in all_results:
            for warning in result.warnings:
                ctx.warnings.append(warning.message)
            for info in result.info:
                ctx.warnings.append(f"Info: {info.message}")
    
    return (sql, ctx.warnings) if return_warnings else sql


def _topological_sort(scenario: Scenario) -> List[str]:
    """Topologically sort nodes and data sources by dependencies."""

    in_degree: Dict[str, int] = defaultdict(int)
    graph: Dict[str, List[str]] = defaultdict(list)
    all_ids: Set[str] = set(scenario.data_sources.keys()) | set(scenario.nodes.keys())

    for node_id, node in scenario.nodes.items():
        all_ids.add(node_id)
        for input_id in node.inputs:
            # CRITICAL: Clean input_id using same logic as get_cte_alias to ensure matching
            # Input IDs might be: "#/0/prj_visits", "#//prj_visits", "prj_visits"
            # We need to normalize them all to "prj_visits" to match node_id
            from ..parser.scenario_parser import _clean_ref
            import re
            cleaned_input = _clean_ref(input_id)
            cleaned_input = re.sub(r'^\d+/', '', cleaned_input)  # Remove digit+slash prefixes

            if cleaned_input in all_ids:
                graph[cleaned_input].append(node_id)
                in_degree[node_id] += 1
            else:
                in_degree[node_id] += 0

    for ds_id in scenario.data_sources:
        in_degree[ds_id] = 0

    queue = deque([node_id for node_id in all_ids if in_degree[node_id] == 0])
    result: List[str] = []

    while queue:
        current = queue.popleft()
        result.append(current)
        for dependent in graph[current]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if len(result) < len(all_ids):
        missing = all_ids - set(result)
        return result + list(missing)

    return result


def _find_final_node(scenario: Scenario, ordered: List[str]) -> Optional[str]:
    """Find the terminal node (one that no other node depends on)."""

    if not ordered:
        return None

    if scenario.logical_model and scenario.logical_model.base_node_id:
        return scenario.logical_model.base_node_id

    referenced: Set[str] = set()
    for node in scenario.nodes.values():
        for input_id in node.inputs:
            referenced.add(input_id.lstrip("#"))

    for node_id in reversed(ordered):
        if node_id not in referenced and node_id in scenario.nodes:
            return node_id

    return ordered[-1] if ordered else None


def _render_node(ctx: RenderContext, node: Node) -> str:
    """Render a single node to SQL SELECT statement."""

    if node.kind == NodeKind.PROJECTION:
        return _render_projection(ctx, node)
    if node.kind == NodeKind.JOIN and isinstance(node, JoinNode):
        return _render_join(ctx, node)
    if node.kind == NodeKind.AGGREGATION and isinstance(node, AggregationNode):
        return _render_aggregation(ctx, node)
    if node.kind == NodeKind.UNION and isinstance(node, UnionNode):
        return _render_union(ctx, node)
    if node.kind == NodeKind.RANK and isinstance(node, RankNode):
        return _render_rank(ctx, node)
    if node.kind == NodeKind.CALCULATION:
        return _render_calculation(ctx, node)

    # Critical error: Unsupported node type
    error_msg = f"Unsupported node type {node.kind} - conversion not possible"
    ctx.warnings.append(error_msg)
    # Still try to render something, but validation will catch this as error
    return "SELECT 1 AS placeholder"


def _render_projection(ctx: RenderContext, node: Node) -> str:
    """Render a projection node."""

    if not node.inputs:
        ctx.warnings.append(f"Projection {node.node_id} has no inputs")
        return "SELECT 1 AS placeholder"

    input_id = node.inputs[0].lstrip("#")
    from_clause = _render_from(ctx, input_id)

    columns: List[str] = []
    target_sql_map: Dict[str, str] = {}
    for mapping in node.mappings:
        col_expr = _render_expression(ctx, mapping.expression, from_clause)
        columns.append(f"{col_expr} AS {_quote_identifier(mapping.target_name)}")
        target_sql_map[mapping.target_name.upper()] = col_expr

    # Collect calculated column names and build a map for expansion
    calc_column_names = set()
    calc_column_map = {}  # Maps column name to its expression
    
    for calc_name, calc_attr in node.calculated_attributes.items():
        calc_column_names.add(calc_name.upper())
        
        # Expand references to other calculated columns in this formula
        # Create a modified expression with expanded references
        expanded_expr = calc_attr.expression
        
        # If this is a RAW expression, expand any calculated column references
        if expanded_expr.expression_type == ExpressionType.RAW:
            formula = expanded_expr.value
            import re
            # Replace references to previously defined calculated columns
            for prev_calc_name, prev_calc_expr in calc_column_map.items():
                pattern = rf'"{re.escape(prev_calc_name)}"'
                if re.search(pattern, formula, re.IGNORECASE):
                    formula = re.sub(pattern, f'({prev_calc_expr})', formula, flags=re.IGNORECASE)
            # Replace references to mapped columns
            for target_name, source_expr in target_sql_map.items():
                pattern = rf'"{re.escape(target_name)}"'
                if re.search(pattern, formula, re.IGNORECASE):
                    formula = re.sub(pattern, source_expr, formula, flags=re.IGNORECASE)
            expanded_expr = Expression(
                expression_type=ExpressionType.RAW,
                value=formula,
                data_type=calc_attr.expression.data_type,
                language=calc_attr.expression.language,
            )
        
        calc_expr = _render_expression(ctx, expanded_expr, from_clause)
        columns.append(f"{calc_expr} AS {_quote_identifier(calc_name)}")
        
        # Store the rendered expression for future expansions
        calc_column_map[calc_name.upper()] = calc_expr

    if not columns:
        columns = ["*"]

    select_clause = ",\n    ".join(columns)
    
    # Build target→source name mapping for filter translation
    target_to_source_map = {}
    for mapping in node.mappings:
        # Extract source column name from expression
        if mapping.expression.expression_type == ExpressionType.COLUMN:
            source_col = mapping.expression.value
            target_col = mapping.target_name
            if source_col != target_col:
                target_to_source_map[target_col.upper()] = source_col
    
    # Render filters and map target names to source names
    where_clause = _render_filters(ctx, node.filters, from_clause)
    
    # For base table queries, replace target column names with source names in WHERE
    if where_clause and target_to_source_map and input_id in ctx.scenario.data_sources:
        import re
        for target_name, source_name in target_to_source_map.items():
            # Replace "TARGET_NAME" with "SOURCE_NAME"
            quoted_target = f'"{target_name}"'
            quoted_source = f'"{source_name}"'
            where_clause = where_clause.replace(quoted_target, quoted_source)

    # Check if WHERE clause references any calculated columns
    needs_subquery = False
    if where_clause and calc_column_names:
        where_upper = where_clause.upper()
        for calc_col in calc_column_names:
            # Check if calculated column is referenced in WHERE
            # Look for patterns like "CALMONTH" or PLACEHOLDER."$$IP_CALMONTH$$"
            if f'"{calc_col}"' in where_clause or calc_col in where_upper:
                needs_subquery = True
                break

    # If filters reference calculated columns, wrap in subquery
    if needs_subquery and where_clause:
        # Qualify ALL column references with subquery alias (not just calculated ones)
        # In a subquery, all columns need to be qualified with the subquery alias
        import re
        
        qualified_where = where_clause
        
        # For HANA mode, remove always-true parameter filter clauses
        if ctx.database_mode == DatabaseMode.HANA:
            # Remove patterns like: ( '' = '' OR ... ) AND
            qualified_where = re.sub(r"\(\s*''\s*=\s*'[^']*'\s+OR\s+[^)]+\)\s+AND\s+", '', qualified_where)
            # Remove at end: AND ( '' = '' OR ... )
            qualified_where = re.sub(r"AND\s+\(\s*''\s*=\s*'[^']*'\s+OR\s+[^)]+\)", '', qualified_where)
        
        # Find all quoted identifiers "COLUMN_NAME" and qualify them with calc.
        # Pattern: "IDENTIFIER" not already preceded by an alias (word.)
        def qualify_column(match):
            quoted_id = match.group(0)
            # Check if already qualified (preceded by alias.)
            return quoted_id  # Will be replaced by pattern below
        
        # ====================================================================
        # ⚠️ CRITICAL - Column Qualification for SAP BEx Columns (BUG-019)
        # ====================================================================
        # This regex must match ALL quoted identifiers including SAP special chars
        # Pattern: r'(?<!\.)"([^"]+)" matches /BIC/*, /BI0/*, and all other quoted names
        #
        # WRONG PATTERN (pre-BUG-019): r'(?<!\.)"([A-Z_][A-Z0-9_]*)"'
        # - Only matched alphanumeric identifiers
        # - Excluded SAP columns like "/BIC/EYTRTNUM"
        # - Caused: sql syntax error: incorrect syntax near "AND"
        #
        # CORRECT PATTERN (BUG-019 fix, validated 39ms HANA execution):
        # - r'(?<!\.)"([^"]+)"' matches ANY characters inside quotes
        # - See: BUG-019-FIX-SUMMARY.md and FIXES_AFTER_COMMIT_4eff5fb.md
        # ====================================================================

        # Replace all "IDENTIFIER" with calc."IDENTIFIER" if not already qualified
        # Pattern: Match "..." but not when preceded by a dot (already qualified)
        # BUG-019: Match ANY quoted identifier including SAP columns like "/BIC/FIELD"
        pattern = r'(?<!\.)("[^"]+")'
        qualified_where = re.sub(pattern, r'calc.\1', qualified_where)
        
        # Fix double qualification (calc.calc. → calc.)
        qualified_where = qualified_where.replace('calc.calc.', 'calc.')
        
        # Fix PLACEHOLDER.calc."$$IP → PLACEHOLDER."$$IP
        qualified_where = qualified_where.replace('PLACEHOLDER.calc."$$', 'PLACEHOLDER."$$')
        
        # Clean up trailing AND
        qualified_where = re.sub(r'\s+AND\s*$', '', qualified_where)
        # Clean up leading AND
        qualified_where = re.sub(r'^\s*AND\s+', '', qualified_where)
        
        # FINAL cleanup: Remove parameter conditions AFTER all qualification
        if ctx.database_mode == DatabaseMode.HANA:
            qualified_where = _cleanup_hana_parameter_conditions(qualified_where)
            # BUG-022: Check if WHERE clause is effectively empty after cleanup
            qualified_where_stripped = qualified_where.strip()
            if qualified_where_stripped in ('', '()'):
                qualified_where = ''

        if qualified_where:
            sql = f"SELECT * FROM (\n  SELECT\n      {select_clause.replace(chr(10) + '    ', chr(10) + '      ')}\n  FROM {from_clause}\n) AS calc\nWHERE {qualified_where}"
        else:
            sql = f"SELECT * FROM (\n  SELECT\n      {select_clause.replace(chr(10) + '    ', chr(10) + '      ')}\n  FROM {from_clause}\n) AS calc"
    else:
        # No subquery needed
        # For HANA mode, still clean up parameter conditions
        if ctx.database_mode == DatabaseMode.HANA and where_clause:
            where_clause = _cleanup_hana_parameter_conditions(where_clause)
            # BUG-022: Check if WHERE clause is effectively empty after cleanup
            where_clause_stripped = where_clause.strip()
            if where_clause_stripped in ('', '()'):
                where_clause = ''

        sql = f"SELECT\n    {select_clause}\nFROM {from_clause}"
        if where_clause:
            sql += f"\nWHERE {where_clause}"

    return sql


def _render_join(ctx: RenderContext, node: JoinNode) -> str:
    """Render a join node."""

    if len(node.inputs) < 2:
        ctx.warnings.append(f"Join {node.node_id} has fewer than 2 inputs")
        return "SELECT 1 AS placeholder"

    left_id = node.inputs[0].lstrip("#")
    right_id = node.inputs[1].lstrip("#")

    # BUG-028: Render proper FROM clauses for both CTEs and data sources
    left_from = _render_from(ctx, left_id)
    right_from = _render_from(ctx, right_id)

    # Get aliases for column references
    left_alias = ctx.get_cte_alias(left_id)
    right_alias = ctx.get_cte_alias(right_id)

    join_type_str = _map_join_type_to_sql(node.join_type)

    conditions: List[str] = []
    for condition in node.conditions:
        left_expr = _render_expression(ctx, condition.left, left_alias)
        right_expr = _render_expression(ctx, condition.right, right_alias)
        conditions.append(f"{left_expr} = {right_expr}")

    if not conditions:
        # Critical error: Cartesian product
        error_msg = f"Join {node.node_id} creates cartesian product (no join conditions)"
        ctx.warnings.append(error_msg)
        # Still generate SQL with 1=1 but mark as critical issue
        conditions = ["1=1"]

    on_clause = " AND ".join(conditions)

    columns: List[str] = []
    seen_targets = set()  # Track columns already added to avoid duplicates
    column_map = {}  # BUG-033: Map target column name → source expression for expansion

    for mapping in node.mappings:
        # Skip hidden columns - only include if in view_attributes list
        if node.view_attributes and mapping.target_name not in node.view_attributes:
            continue
        # Skip duplicate target names (keep first occurrence)
        if mapping.target_name in seen_targets:
            continue
        seen_targets.add(mapping.target_name)
        # Determine which alias to use based on source_node
        if mapping.source_node:
            # source_node is like "#Aggregation_1" or "#Projection_2"
            source_node_id = mapping.source_node.lstrip("#")
            source_alias = ctx.get_cte_alias(source_node_id)
        else:
            # Default to left alias if no source_node specified
            source_alias = left_alias
        source_expr = _render_expression(ctx, mapping.expression, source_alias)
        columns.append(f"{source_expr} AS {_quote_identifier(mapping.target_name)}")

        # BUG-033: Store mapping for calculated column expansion
        column_map[mapping.target_name.upper()] = source_expr

    # BUG-033: Expand calculated column references to mapped columns
    # Calculated columns may reference column aliases defined in the same SELECT
    # HANA doesn't allow this - we must expand to the source expressions
    for calc_name, calc_attr in node.calculated_attributes.items():
        if calc_attr.expression.expression_type == ExpressionType.RAW:
            formula = calc_attr.expression.value
            import re

            # Expand references to mapped columns
            # Replace "COLUMN_NAME" with (source_expr)
            for col_name, col_expr in column_map.items():
                pattern = rf'"{re.escape(col_name)}"'
                if re.search(pattern, formula, re.IGNORECASE):
                    # Wrap in parentheses for safety
                    formula = re.sub(pattern, f'({col_expr})', formula, flags=re.IGNORECASE)

            calc_expr = translate_raw_formula(formula, ctx)
        else:
            calc_expr = _render_expression(ctx, calc_attr.expression, left_alias)

        columns.append(f"{calc_expr} AS {_quote_identifier(calc_name)}")

    if not columns:
        columns = [f"{left_alias}.*", f"{right_alias}.*"]

    select_clause = ",\n    ".join(columns)
    where_clause = _render_filters(ctx, node.filters, left_alias)

    # BUG-022: Clean up parameter conditions for HANA mode
    if ctx.database_mode == DatabaseMode.HANA and where_clause:
        where_clause = _cleanup_hana_parameter_conditions(where_clause)
        where_clause_stripped = where_clause.strip()
        if where_clause_stripped in ('', '()'):
            where_clause = ''

    # BUG-028: Use proper FROM rendering for both CTEs and tables, with AS clauses for aliases
    sql = f"SELECT\n    {select_clause}\nFROM {left_from} AS {left_alias}\n{join_type_str} JOIN {right_from} AS {right_alias} ON {on_clause}"
    if where_clause:
        sql += f"\nWHERE {where_clause}"

    return sql


def _render_aggregation(ctx: RenderContext, node: AggregationNode) -> str:
    """Render an aggregation node."""

    if not node.inputs:
        ctx.warnings.append(f"Aggregation {node.node_id} has no inputs")
        return "SELECT 1 AS placeholder"

    input_id = node.inputs[0].lstrip("#")
    from_clause = _render_from(ctx, input_id)

    # Identify calculated column names first (case-insensitive)
    calc_col_names = set(k.upper() for k in node.calculated_attributes.keys())
    
    # Build target→expression mapping for GROUP BY
    target_to_expr_map = {}
    for mapping in node.mappings:
        target_to_expr_map[mapping.target_name.upper()] = mapping.expression
    
    # For GROUP BY, use actual column expressions from input (not aliases)
    # Skip calculated columns - they'll be in outer query
    group_by_cols: List[str] = []
    for col_name in node.group_by:
        if col_name.upper() not in calc_col_names:
            # Use the source expression, not the alias
            if col_name.upper() in target_to_expr_map:
                expr = target_to_expr_map[col_name.upper()]
                group_by_cols.append(_render_expression(ctx, expr, from_clause))
            else:
                group_by_cols.append(_quote_identifier(col_name))

    select_items: List[str] = []
    
    # Identify columns that are aggregated (measures, not dimensions)
    aggregated_col_names = set(agg.target_name.upper() for agg in node.aggregations)
    
    # Add mappings (passthrough columns from input)
    # But skip calculated columns AND aggregated columns (will be added separately)
    for mapping in node.mappings:
        if (mapping.target_name.upper() not in calc_col_names and 
            mapping.target_name.upper() not in aggregated_col_names):
            col_expr = _render_expression(ctx, mapping.expression, from_clause)
            select_items.append(f"{col_expr} AS {_quote_identifier(mapping.target_name)}")
    
    # Note: Don't add group_by columns separately - they're already in mappings
    # The group_by list just determines which columns go in GROUP BY clause

    # Build reverse mapping for aggregation specs: target → source expression
    target_to_source_expr = {}
    for mapping in node.mappings:
        target_to_source_expr[mapping.target_name.upper()] = mapping.expression
    
    for agg_spec in node.aggregations:
        agg_func = agg_spec.function.upper()
        
        # Check if the aggregation column name is a renamed column (in mappings)
        # If so, use the source expression, not the target name
        if agg_spec.expression.expression_type == ExpressionType.COLUMN:
            col_name = agg_spec.expression.value
            if col_name.upper() in target_to_source_expr:
                # Use the source expression from mappings
                agg_expr = _render_expression(ctx, target_to_source_expr[col_name.upper()], from_clause)
            else:
                agg_expr = _render_expression(ctx, agg_spec.expression, from_clause)
        else:
            agg_expr = _render_expression(ctx, agg_spec.expression, from_clause)
        
        select_items.append(f"{agg_func}({agg_expr}) AS {_quote_identifier(agg_spec.target_name)}")

    # Note: Don't add calculated columns here - they need special handling
    # because they can't be in GROUP BY of the same SELECT

    if not select_items:
        select_items = ["*"]

    select_clause = ",\n    ".join(select_items)
    where_clause = _render_filters(ctx, node.filters, from_clause)

    # BUG-022: Clean up parameter conditions for HANA mode
    if ctx.database_mode == DatabaseMode.HANA and where_clause:
        where_clause = _cleanup_hana_parameter_conditions(where_clause)
        where_clause_stripped = where_clause.strip()
        if where_clause_stripped in ('', '()'):
            where_clause = ''

    # Build GROUP BY clause first
    group_by_clause = ""
    if group_by_cols:
        group_by_clause = f"GROUP BY {', '.join(group_by_cols)}"
    
    # Check if there are calculated columns that need to be added AFTER grouping
    has_calc_cols = len(node.calculated_attributes) > 0
    
    if has_calc_cols:
        # Wrap: inner query groups, outer query adds calculated columns
        inner_sql = f"SELECT\n    {select_clause}\nFROM {from_clause}"
        if where_clause:
            inner_sql += f"\nWHERE {where_clause}"
        if group_by_clause:
            inner_sql += f"\n{group_by_clause}"

        # BUG-032: Build calc_column_map for expansion (similar to projections)
        # Some calculated columns reference OTHER calculated columns in the same SELECT
        # Example: WEEKDAY references YEAR, both are in outer SELECT
        calc_column_map = {}  # Maps calc column name → rendered expression

        # Outer SELECT adds calculated columns
        outer_select = ["agg_inner.*"]
        for calc_name, calc_attr in node.calculated_attributes.items():
            # Qualify column refs in formula with agg_inner
            if calc_attr.expression.expression_type == ExpressionType.RAW:
                formula = calc_attr.expression.value
                import re

                # BUG-032: First, expand references to previously defined calculated columns
                # Replace "CALC_COL" with (calc_expr) before qualifying with agg_inner
                for prev_calc_name, prev_calc_expr in calc_column_map.items():
                    pattern = rf'"{re.escape(prev_calc_name)}"'
                    if re.search(pattern, formula, re.IGNORECASE):
                        formula = re.sub(pattern, f'({prev_calc_expr})', formula, flags=re.IGNORECASE)

                # Then qualify remaining column refs with agg_inner."COLUMN"
                # Only qualify if not already qualified (not preceded by .)
                formula = re.sub(r'(?<!\.)"([A-Z_][A-Z0-9_]*)"', r'agg_inner."\1"', formula)
                calc_expr = translate_raw_formula(formula, ctx)
            else:
                calc_expr = _render_expression(ctx, calc_attr.expression, "agg_inner")

            outer_select.append(f"{calc_expr} AS {_quote_identifier(calc_name)}")

            # BUG-032: Store rendered expression for future expansions
            calc_column_map[calc_name.upper()] = calc_expr

        outer_clause = ",\n    ".join(outer_select)
        sql = f"SELECT\n    {outer_clause}\nFROM (\n  {inner_sql.replace(chr(10), chr(10) + '  ')}\n) AS agg_inner"
    else:
        # Simple aggregation - no calculated columns
        sql = f"SELECT\n    {select_clause}\nFROM {from_clause}"
        if where_clause:
            sql += f"\nWHERE {where_clause}"
        if group_by_clause:
            sql += f"\n{group_by_clause}"

    return sql


def _render_union(ctx: RenderContext, node: UnionNode) -> str:
    """Render a union node."""

    if len(node.inputs) < 2:
        ctx.warnings.append(f"Union {node.node_id} has fewer than 2 inputs")
        return "SELECT 1 AS placeholder"

    union_queries: List[str] = []
    target_columns = list(dict.fromkeys(mapping.target_name for mapping in node.mappings)) if node.mappings else []

    for input_id in node.inputs:
        input_id = input_id.lstrip("#")
        input_alias = ctx.get_cte_alias(input_id) if input_id in ctx.cte_aliases else _render_from(ctx, input_id)

        input_mappings = [m for m in node.mappings if (m.source_node or "").lstrip("#") == input_id]
        if input_mappings and target_columns:
            select_items: List[str] = []
            for target_col in target_columns:
                mapping = next((m for m in input_mappings if m.target_name == target_col), None)
                if mapping:
                    col_expr = _render_expression(ctx, mapping.expression, input_alias)
                    select_items.append(f"{col_expr} AS {_quote_identifier(target_col)}")
                else:
                    select_items.append(f"NULL AS {_quote_identifier(target_col)}")
            select_clause = ",\n    ".join(select_items)
        else:
            select_clause = "*"

        union_queries.append(f"SELECT\n    {select_clause}\nFROM {input_alias}")

    union_keyword = "UNION ALL" if node.union_all else "UNION"
    sql = f"\n{union_keyword}\n".join(union_queries)

    if node.filters:
        where_clause = _render_filters(ctx, node.filters, None)

        # BUG-022: Clean up parameter conditions for HANA mode
        if ctx.database_mode == DatabaseMode.HANA and where_clause:
            where_clause = _cleanup_hana_parameter_conditions(where_clause)
            where_clause_stripped = where_clause.strip()
            if where_clause_stripped in ('', '()'):
                where_clause = ''

        if where_clause:
            sql = f"SELECT * FROM (\n{sql}\n) AS union_result\nWHERE {where_clause}"

    return sql


def _render_rank(ctx: RenderContext, node: RankNode) -> str:
    """Render a rank/window node to SQL."""

    if not node.inputs:
        ctx.warnings.append(f"Rank {node.node_id} has no inputs")
        return "SELECT 1 AS placeholder"

    input_id = node.inputs[0].lstrip("#")
    from_clause = _render_from(ctx, input_id)

    select_items: List[str] = []
    for mapping in node.mappings:
        col_expr = _render_expression(ctx, mapping.expression, from_clause)
        select_items.append(f"{col_expr} AS {_quote_identifier(mapping.target_name)}")

    partition_exprs = [
        _render_column_ref(ctx, col, from_clause) for col in node.partition_by if col
    ]
    order_exprs: List[str] = []
    for order_spec in node.order_by:
        order_col = _render_column_ref(ctx, order_spec.column, from_clause)
        direction = order_spec.direction.upper() if order_spec.direction else "ASC"
        order_exprs.append(f"{order_col} {direction}")
    if not order_exprs:
        order_exprs.append("1")

    window_parts: List[str] = []
    if partition_exprs:
        window_parts.append(f"PARTITION BY {', '.join(partition_exprs)}")
    window_parts.append(f"ORDER BY {', '.join(order_exprs)}")
    window_clause = " ".join(window_parts)

    rank_expr = f"ROW_NUMBER() OVER ({window_clause})"
    select_items.append(f"{rank_expr} AS {_quote_identifier(node.rank_column)}")

    select_clause = ",\n    ".join(select_items)
    select_sql = f"SELECT\n    {select_clause}\nFROM {from_clause}"

    if node.threshold is not None:
        inner_sql = _indent_sql(select_sql)
        return (
            "SELECT * FROM (\n"
            f"{inner_sql}\n"
            ") AS ranked\n"
            f"WHERE {_quote_identifier(node.rank_column)} <= {node.threshold}"
        )

    return select_sql


def _render_calculation(ctx: RenderContext, node: Node) -> str:
    """Render a calculation node (fallback for unsupported node types)."""

    if not node.inputs:
        ctx.warnings.append(f"Calculation {node.node_id} has no inputs")
        return "SELECT 1 AS placeholder"

    input_id = node.inputs[0].lstrip("#")
    from_clause = _render_from(ctx, input_id)

    columns: List[str] = []
    for mapping in node.mappings:
        col_expr = _render_expression(ctx, mapping.expression, from_clause)
        columns.append(f"{col_expr} AS {_quote_identifier(mapping.target_name)}")

    if not columns:
        columns = ["*"]

    select_clause = ",\n    ".join(columns)
    where_clause = _render_filters(ctx, node.filters, from_clause)

    # BUG-022: Clean up parameter conditions for HANA mode
    if ctx.database_mode == DatabaseMode.HANA and where_clause:
        where_clause = _cleanup_hana_parameter_conditions(where_clause)
        # After cleanup, check if WHERE clause is empty or just empty parens
        where_clause_stripped = where_clause.strip()
        if where_clause_stripped in ('', '()'):
            where_clause = ''

    sql = f"SELECT\n    {select_clause}\nFROM {from_clause}"
    if where_clause:
        sql += f"\nWHERE {where_clause}"

    return sql


def _indent_sql(sql: str, indent: str = "  ") -> str:
    return "\n".join(f"{indent}{line}" for line in sql.splitlines())


def _render_from(ctx: RenderContext, input_id: str) -> str:
    """Render FROM clause for a data source or CTE."""

    if input_id in ctx.scenario.data_sources:
        ds = ctx.scenario.data_sources[input_id]

        # BUG-025: CALCULATION_VIEW references need package path in HANA mode
        # Regular tables: SAPABAP1."TABLE_NAME"
        # Calculation views: "_SYS_BIC"."Package.Path/CV_NAME"
        from ..domain.models import DataSourceType
        from ..domain.types import DatabaseMode

        if ctx.database_mode == DatabaseMode.HANA and ds.source_type == DataSourceType.CALCULATION_VIEW:
            # Calculation view reference - use _SYS_BIC with package path
            cv_name = ds.object_name
            
            # BUG-025: For entity-based CV references, schema_name contains the package path
            # Example: schema_name="Macabi_BI.Eligibility", object_name="CV_MD_EYPOSPER"
            if ds.schema_name and "." in ds.schema_name:
                # Use schema_name as package path (from entity parsing)
                package = ds.schema_name
            else:
                # Fall back to package mapper for data source-based CVs
                from ..package_mapper import get_package
                package = get_package(cv_name)
            
            if package:
                view_name_with_package = f"{package}/{cv_name}"
                return f'"_SYS_BIC".{_quote_identifier(view_name_with_package)}'
            else:
                # Fallback if package not found - use _SYS_BIC without package
                ctx.warnings.append(f"Package not found for CV {cv_name}, using _SYS_BIC without path")
                return f'"_SYS_BIC".{_quote_identifier(cv_name)}'

        # BUG-025: Fallback check for CV references that weren't marked as CALCULATION_VIEW
        # If object name starts with "CV_" in HANA mode, treat as calculation view
        if ctx.database_mode == DatabaseMode.HANA and ds.object_name.startswith("CV_"):
            cv_name = ds.object_name

            # Check if schema_name has package path format
            if ds.schema_name and "." in ds.schema_name:
                # Use schema_name as package path
                package = ds.schema_name
            else:
                # Fall back to package mapper
                from ..package_mapper import get_package
                package = get_package(cv_name)

            if package:
                view_name_with_package = f"{package}/{cv_name}"
                # BUG-030: Package paths contain "." which is NOT a schema separator
                # Don't use _quote_identifier() which would split on "."
                # Example: "Macabi_BI.Eligibility/CV_MD_EYPOSPER" must be quoted as ONE identifier
                return f'"_SYS_BIC"."{view_name_with_package}"'
            else:
                # Fallback if package not found
                ctx.warnings.append(f"Package not found for CV {cv_name}, using _SYS_BIC without path")
                # BUG-030: Directly quote the CV name as well
                return f'"_SYS_BIC"."{cv_name}"'

        # Regular table or view
        schema = ctx.resolve_schema(ds.schema_name)
        if schema:
            return f"{_quote_identifier(schema)}.{_quote_identifier(ds.object_name)}"
        return _quote_identifier(ds.object_name)

    # BUG-025 PART 2: Handle external CV references in node IDs
    # Pattern: #/0/Star Join/Package.Subpackage::CV_NAME or #/0/Package.Subpackage::CV_NAME
    # The #/0/ prefix is XML metadata (external reference, resourceUri type) - must be stripped
    # Example: "#/0/Macabi_BI.Eligibility::CV_MD_EYPOSPER" → "_SYS_BIC"."Macabi_BI.Eligibility/CV_MD_EYPOSPER"
    from ..domain.types import DatabaseMode
    if ctx.database_mode == DatabaseMode.HANA and "::" in input_id and "CV_" in input_id:
        import re
        # Match pattern: optional #/0/ prefix, then Package.Path::CV_NAME
        cv_match = re.search(r'(?:#/0/(?:Star Join/)?)?([A-Za-z0-9_\.]+)::([A-Za-z0-9_]+)$', input_id)
        if cv_match:
            package_path = cv_match.group(1)  # e.g., "Macabi_BI.Eligibility"
            cv_name = cv_match.group(2)        # e.g., "CV_MD_EYPOSPER"

            # Convert to HANA _SYS_BIC format: "Package.Subpackage/CV_NAME"
            hana_path = package_path + "/" + cv_name
            return f'"_SYS_BIC".{_quote_identifier(hana_path)}'

    if input_id in ctx.cte_aliases:
        return ctx.cte_aliases[input_id]

    return ctx.get_cte_alias(input_id)


def _render_expression(ctx: RenderContext, expr: Expression, table_alias: Optional[str] = None) -> str:
    """Render an expression to SQL."""

    if expr.expression_type == ExpressionType.COLUMN:
        return _render_column_ref(ctx, expr.value, table_alias)
    if expr.expression_type == ExpressionType.LITERAL:
        return _render_literal(expr.value, expr.data_type)
    if expr.expression_type == ExpressionType.RAW:
        translated = translate_raw_formula(expr.value, ctx)
        if translated != expr.value:
            return translated
        result = _substitute_placeholders(expr.value, ctx)
        # BUG-027: Qualify bare column names in RAW expressions when table_alias provided
        # Example: In JOIN calculated column, "CALDAY" becomes ambiguous
        # Should be qualified as "left_alias"."CALDAY" to avoid ambiguity
        if table_alias and result.strip('"').isidentifier() and not '(' in result:
            # Simple column name (no function calls) - qualify it
            return f"{table_alias}.{result}"
        return result
    if expr.expression_type == ExpressionType.FUNCTION:
        return _render_function(ctx, expr, table_alias)

    ctx.warnings.append(f"Unsupported expression type: {expr.expression_type}")
    return "NULL"


def _render_column_ref(ctx: RenderContext, column_name: str, table_alias: Optional[str] = None) -> str:
    """Render a column reference."""

    if table_alias:
        return f"{table_alias}.{_quote_identifier(column_name)}"
    return _quote_identifier(column_name)


def _render_literal(value: str, data_type: Optional[object] = None) -> str:
    """Render a literal value."""

    # BUG-026: Values with leading zeros are string codes (01, 001), not numbers
    # Must quote them to avoid HANA type conversion errors on string columns
    # Example: CODAPL = 01 should be CODAPL = '01'
    has_leading_zero = value.isdigit() and len(value) > 1 and value[0] == '0'

    if not has_leading_zero and (value.isdigit() or (value.startswith("-") and value[1:].isdigit())):
        return value
    if data_type and hasattr(data_type, "type"):
        from ..domain.types import SnowflakeType

        if data_type.type == SnowflakeType.DATE:
            if len(value) == 8 and value.isdigit():
                return f"TO_DATE('{value}', 'YYYYMMDD')"
            return f"'{value}'::DATE"
        if data_type.type == SnowflakeType.TIMESTAMP_NTZ:
            return f"'{value}'::TIMESTAMP_NTZ"

    return f"'{value.replace(chr(39), chr(39) + chr(39))}'"


def _render_function(ctx: RenderContext, expr: Expression, table_alias: Optional[str] = None) -> str:
    """Render a function call expression."""

    func_name = expr.value.upper()
    args = expr.arguments or []

    class FuncContext:
        def __init__(self, ctx, table_alias):
            self.ctx = ctx
            self.table_alias = table_alias
            self.client = ctx.client
            self.language = ctx.language

        def _render_expression(self, expr, alias):
            return _render_expression(self.ctx, expr, alias or self.table_alias)

    func_ctx = FuncContext(ctx, table_alias)
    translated = translate_hana_function(func_name, args, func_ctx)
    if translated:
        return translated

    arg_strs = [_render_expression(ctx, arg, table_alias) for arg in args]
    return f"{func_name}({', '.join(arg_strs)})"


def _negate_operator(op: str) -> str:
    """Negate a comparison operator for including=False filters (BUG-034).

    When a filter has including="false", the operator must be negated:
    - = becomes <>
    - <> becomes =
    - > becomes <=
    - >= becomes <
    - < becomes >=
    - <= becomes >
    - IN becomes NOT IN
    - NOT IN becomes IN
    - LIKE becomes NOT LIKE
    - BETWEEN becomes NOT BETWEEN
    """
    negation_map = {
        "=": "<>",
        "<>": "=",
        "!=": "=",
        ">": "<=",
        ">=": "<",
        "<": ">=",
        "<=": ">",
        "IN": "NOT IN",
        "NOT IN": "IN",
        "LIKE": "NOT LIKE",
        "NOT LIKE": "LIKE",
        "BETWEEN": "NOT BETWEEN",
        "NOT BETWEEN": "BETWEEN",
    }
    # Handle case-insensitive matching
    op_upper = op.upper()
    if op_upper in negation_map:
        return negation_map[op_upper]
    # If operator not in map, prefix with NOT (fallback)
    return f"NOT {op}"


def _render_filters(ctx: RenderContext, filters: List[Predicate], table_alias: Optional[str] = None) -> str:
    """Render WHERE clause from filters."""

    if not filters:
        return ""

    conditions: List[str] = []
    for pred in filters:
        if pred.kind == PredicateKind.COMPARISON:
            left = _render_expression(ctx, pred.left, table_alias)
            op = pred.operator or "="

            # BUG-034: Handle including=False by negating the operator
            # When including="false" in XML, the filter should EXCLUDE matching values
            if not pred.including:
                op = _negate_operator(op)

            if pred.right:
                right = _render_expression(ctx, pred.right, table_alias)
                conditions.append(f"{left} {op} {right}")
        elif pred.kind == PredicateKind.IS_NULL:
            left = _render_expression(ctx, pred.left, table_alias)
            conditions.append(f"{left} IS NULL")
        elif pred.kind == PredicateKind.RAW:
            raw_expr = _render_expression(ctx, pred.left, table_alias)
            if raw_expr:
                conditions.append(f"({raw_expr})")
        else:
            ctx.warnings.append(f"Unsupported predicate kind: {pred.kind}")

    return " AND ".join(conditions) if conditions else ""


def _map_join_type_to_sql(join_type: JoinType) -> str:
    """Map JoinType enum to SQL JOIN keyword."""

    mapping = {
        JoinType.INNER: "INNER",
        JoinType.LEFT_OUTER: "LEFT OUTER",
        JoinType.RIGHT_OUTER: "RIGHT OUTER",
        JoinType.FULL_OUTER: "FULL OUTER",
    }
    return mapping.get(join_type, "INNER")


def _render_currency_conversion(
    ctx: RenderContext,
    amount_expr: str,
    source_currency_expr: str,
    target_currency_expr: str,
    reference_date_expr: str,
    rate_type: str = "M",
) -> str:
    """Render currency conversion using UDF or table join."""

    if ctx.currency_udf:
        schema_prefix = f"{ctx.currency_schema}." if ctx.currency_schema else ""
        return f"{schema_prefix}{ctx.currency_udf}({amount_expr}, {source_currency_expr}, {target_currency_expr}, {reference_date_expr}, '{rate_type}', '{ctx.client}')"

    if ctx.currency_table:
        schema_prefix = f"{ctx.currency_schema}." if ctx.currency_schema else ""
        ctx.warnings.append("Currency conversion via table join not yet implemented; using UDF placeholder")
        return f"-- TODO: Currency conversion for {amount_expr} from {source_currency_expr} to {target_currency_expr}"

    ctx.warnings.append("Currency conversion requested but no UDF or table configured")
    return amount_expr


def _substitute_placeholders(text: str, ctx: RenderContext) -> str:
    """Replace $$client$$ and $$language$$ placeholders."""

    result = text.replace("$$client$$", ctx.client)
    result = result.replace("$$language$$", ctx.language)
    return result


def _cleanup_hana_parameter_conditions(where_clause: str) -> str:
    """Clean up always-true parameter conditions in HANA mode WHERE clauses.
    
    Removes patterns like:
    - ('' = '' OR column = '')
    - ('' = '0' OR column >= DATE(''))
    """
    import re
    
    result = where_clause
    
    # Remove ('' = 'X' OR ... ) patterns with balanced paren matching
    # Strategy: Find all ('' = ... OR ...) patterns and remove them
    max_iterations = 20
    
    for _ in range(max_iterations):
        # Find ('' = pattern or ('''' = pattern (escaped quote) - BUG-020 fix
        match = re.search(r"\((?:''|'''')\s*=\s*'[^']*'\s+OR\s+", result, re.IGNORECASE)
        if not match:
            break
        
        clause_start = match.start()
        # Find the matching closing paren
        depth = 1  # We're past the opening (
        i = match.end()
        in_quote = False
        
        while i < len(result) and depth > 0:
            c = result[i]
            if c in ('"', "'") and (i == 0 or result[i-1] != '\\'):
                in_quote = not in_quote
            if not in_quote:
                if c == '(':
                    depth += 1
                elif c == ')':
                    depth -= 1
            i += 1
        
        if depth == 0:
            # Found matching closing paren
            clause_end = i
            
            # Check for AND before the clause
            before = result[:clause_start]
            and_before_match = re.search(r'\s+AND\s*$', before, re.IGNORECASE)
            if and_before_match:
                # Remove the AND before
                start = clause_start - len(and_before_match.group(0))
            else:
                start = clause_start
            
            # Check for AND after the clause
            after = result[clause_end:]
            and_after_match = re.match(r'\s+AND\s+', after, re.IGNORECASE)
            if and_after_match:
                # Remove the AND after
                end = clause_end + and_after_match.end()
            else:
                end = clause_end
            
            result = result[:start] + result[end:]
        else:
            break
    
    # Uppercase all AND keywords (HANA prefers uppercase)
    result = re.sub(r'\band\b', 'AND', result, flags=re.IGNORECASE)
    
    # Fix NOW() function - ensure uppercase with parentheses
    result = re.sub(r'\bnow\b(?!\()', 'NOW()', result, flags=re.IGNORECASE)
    result = re.sub(r'\bnow\(\)', 'NOW()', result, flags=re.IGNORECASE)
    
    # Fix spacing issues in CASE WHEN: ''= '' → '' = ''
    result = re.sub(r"''\s*=\s*''", "'' = ''", result)
    
    # Move trailing AND to beginning of next line (HANA prefers this style)
    # Pattern: condition) AND\n    next → condition)\n    AND next
    result = re.sub(r'\)\s+AND\s*\n\s+', ')\n    AND ', result)
    
    # Clean up double AND
    result = re.sub(r'\s+AND\s+AND\s+', ' AND ', result, flags=re.IGNORECASE)
    
    # Clean up orphaned AND only at absolute start/end, not end of lines
    result = re.sub(r'^\s*AND\s+', '', result, flags=re.IGNORECASE)
    result = re.sub(r'\s+AND\s*$', '', result, flags=re.IGNORECASE)
    
    # Clean up orphaned closing parens - pattern: condition and\n\n    )
    # Match AND (case insensitive, word boundary) followed by whitespace and )
    # Handles both " AND\n    )" and "'Z112T'and\n    )" patterns
    result = re.sub(r'\band\s*[\n\r\s]*\)', ')', result, flags=re.IGNORECASE)
    
    # Clean up orphaned opening-closing paren pairs: )(
    result = re.sub(r'\)\s*\(', ') AND (', result)
    
    # Clean up malformed DATE() fragments from parameter substitution
    # Pattern: ) >= DATE('') )) or ) <= DATE('')) )
    # Match: ) followed by comparison followed by DATE('') followed by any closing parens
    result = re.sub(r'\)\s*[<>=!]+\s*DATE\s*\(\s*\'\'\s*\)\s*\)', ')', result)
    result = re.sub(r'\s+[<>=!]+\s*DATE\s*\(\s*\'\'\s*\)\s*\)', ')', result)
    
    # Clean up specific malformed patterns (not all double parens - breaks CASE END END))
    # Only remove )) when followed by comparison operator (orphaned from DATE cleanup)
    result = re.sub(r'\)\s*\)\s*[<>=]', ') ', result)
    
    # Clean up remaining nested empty patterns: (('' = 0) OR ...)
    result = re.sub(r'\(\s*\(\s*\'\'\s*=\s*[^)]*\)\s*\)', '', result)
    
    # Clean up AND followed by empty pattern
    result = re.sub(r'\s+AND\s+\(\s*\)', '', result, flags=re.IGNORECASE)

    # BUG-019: Simplify CASE WHEN with constant true conditions in REGEXP_LIKE
    # Pattern: REGEXP_LIKE(column, CASE WHEN '''' = '' THEN '*' ELSE ... END)
    # Since '''' (single quote) != '' (empty string), this is always false,
    # but '' = '' is always true. Need to simplify to just '*'
    # Also handle '' = '' pattern (always true)

    # Step 1: Simplify CASE WHEN '' = '' THEN value ELSE ... END to just value
    # This handles the always-true condition
    # Use a more robust pattern that handles any ELSE clause content
    def simplify_case_when(match):
        """Simplify CASE WHEN constant_true_condition to just the THEN value."""
        return f"'{match.group(1)}'"

    # Match CASE WHEN with any ELSE clause content (including column references)
    result = re.sub(
        r"CASE\s+WHEN\s+(?:''|'''')\s*=\s*''\s+THEN\s+'([^']*)'\s+ELSE\s+.*?END",
        simplify_case_when,
        result,
        flags=re.IGNORECASE | re.DOTALL
    )

    # Step 2: Remove REGEXP_LIKE(column, '*') entirely - matches everything, pointless filter
    # Pattern: REGEXP_LIKE(column, '*') AND ... or ... AND REGEXP_LIKE(column, '*')
    result = re.sub(
        r"REGEXP_LIKE\s*\([^,]+,\s*'\*'\s*\)\s+AND\s+",
        "",
        result,
        flags=re.IGNORECASE
    )
    result = re.sub(
        r"\s+AND\s+REGEXP_LIKE\s*\([^,]+,\s*'\*'\s*\)",
        "",
        result,
        flags=re.IGNORECASE
    )

    # Step 3: Remove entire WHERE clauses with only wildcard REGEXP_LIKE
    # Pattern: WHERE (REGEXP_LIKE(..., '*'))
    # Use DOTALL to handle multiline patterns
    result = re.sub(
        r"WHERE\s*\(\s*REGEXP_LIKE\s*\([^)]+,\s*'\*'\s*\)\s*\)",
        "",
        result,
        flags=re.IGNORECASE | re.DOTALL
    )

    # Step 4: Remove entire WHERE clauses that become empty after cleanup
    # Pattern: WHERE ()
    result = re.sub(r'WHERE\s*\(\s*\)', '', result, flags=re.IGNORECASE)

    # BUG-021: Remove empty string IN numeric patterns that cause HANA type conversion errors
    # Error: SAP DBTech JDBC: [339]: invalid number: not a valid number string '' at implicit type conversion
    # Pattern: ('' IN (0) OR column IN (...)) → simplify to just second part
    # Also: '' IN (numeric_value) → remove entirely

    # Step 1: Remove ('' IN (number) OR ... ) patterns - keep only the second part
    # Match: ('' IN (digit) OR something)
    result = re.sub(
        r"\(\s*''\s+IN\s+\(\s*\d+\s*\)\s+OR\s+([^)]+)\)",
        r"(\1)",
        result,
        flags=re.IGNORECASE
    )

    # Step 2: Remove standalone '' IN (number) patterns with surrounding AND
    # Pattern: AND '' IN (0) AND → AND
    result = re.sub(
        r"\s+AND\s+''\s+IN\s+\(\s*\d+\s*\)\s+AND\s+",
        " AND ",
        result,
        flags=re.IGNORECASE
    )

    # Step 3: Remove '' IN (number) at start: ('' IN (0) AND ...)
    result = re.sub(
        r"\(\s*''\s+IN\s+\(\s*\d+\s*\)\s+AND\s+",
        "(",
        result,
        flags=re.IGNORECASE
    )

    # Step 4: Remove '' IN (number) at end: (... AND '' IN (0))
    result = re.sub(
        r"\s+AND\s+''\s+IN\s+\(\s*\d+\s*\)\s*\)",
        ")",
        result,
        flags=re.IGNORECASE
    )

    # BUG-022: Remove empty WHERE clauses that result from parameter cleanup
    # Pattern: WHERE () or WHERE ( ) (with optional whitespace)
    # This can occur when all conditions inside WHERE are cleaned up by BUG-021 fixes
    # Error: SAP DBTech JDBC: [257]: sql syntax error: incorrect syntax near ")"
    result = re.sub(
        r'\bWHERE\s+\(\s*\)',
        '',
        result,
        flags=re.IGNORECASE
    )

    # BUG-026: Remove conditions with unsubstituted $$parameter$$ placeholders
    # These are parameter placeholders from the XML that weren't substituted with actual values
    # Pattern 1: ("COLUMN" = $$PARAM$$) or ($$PARAM$$) = 'value' → remove entire clause
    # Pattern 2: standalone ($$PARAM$$) expression → remove
    # Strategy: Remove any conditions containing $$...$$

    # Remove OR/AND clauses containing $$parameter$$ patterns with balanced parentheses
    max_param_iterations = 20
    for _ in range(max_param_iterations):
        # Find patterns with $$...$$
        param_match = re.search(r'\$\$[^$]+\$\$', result)
        if not param_match:
            break

        # Find the enclosing parenthesized clause
        param_pos = param_match.start()

        # Search backwards for opening paren
        clause_start = param_pos
        depth = 0
        for i in range(param_pos - 1, -1, -1):
            if result[i] == ')':
                depth += 1
            elif result[i] == '(':
                if depth == 0:
                    clause_start = i
                    break
                depth -= 1

        # Search forward for closing paren
        clause_end = param_pos
        depth = 0
        in_quote = False
        for i in range(param_pos, len(result)):
            c = result[i]
            if c in ('"', "'") and (i == 0 or result[i-1] != '\\'):
                in_quote = not in_quote
            if not in_quote:
                if c == '(':
                    depth += 1
                elif c == ')':
                    if depth == 0:
                        clause_end = i + 1
                        break
                    depth -= 1

        # Check for AND/OR before/after the clause to remove cleanly
        before = result[:clause_start]
        after = result[clause_end:]

        # Check for operator before
        and_or_before = re.search(r'\s+(AND|OR)\s*$', before, re.IGNORECASE)
        if and_or_before:
            start = clause_start - len(and_or_before.group(0))
        else:
            start = clause_start

        # Check for operator after
        and_or_after = re.match(r'\s+(AND|OR)\s+', after, re.IGNORECASE)
        if and_or_after:
            end = clause_end + and_or_after.end()
        else:
            end = clause_end

        result = result[:start] + result[end:]

    # Clean up any remaining $$parameter$$ patterns that weren't in parentheses
    result = re.sub(r'\$\$[^$]+\$\$', '', result)

    # BUG-026 ADDITIONAL CLEANUP: Fix malformed patterns left after parameter removal

    # Pattern 1: Remove orphaned IN keyword followed by comparison operator
    # Example: "CALMONTH" IN  = '000000' → "CALMONTH" = '000000'
    # This happens when IN $$PARAM$$ gets param removed, leaving IN  =
    result = re.sub(r'\bIN\s+(?==)', '', result, flags=re.IGNORECASE)

    # Pattern 2: Remove TO_DATE/DATE comparisons with NULL
    # Example: TO_DATE("CALDAY") >= NULL → (remove entire expression)
    # This happens when TO_DATE($$PARAM$$) gets param removed leaving NULL
    result = re.sub(
        r'(?:TO_DATE|DATE)\s*\([^)]+\)\s*(?:>=|<=|>|<|=|!=)\s*NULL',
        '',
        result,
        flags=re.IGNORECASE
    )

    # Pattern 3: Clean up orphaned OR/AND before closing paren
    # Example: (condition OR ) → (condition)
    result = re.sub(r'\s+(?:OR|AND)\s*\)', ')', result, flags=re.IGNORECASE)

    # Pattern 4: Clean up double opening parens with no content
    # Example: (( OR → (
    result = re.sub(r'\(\s*\(\s*(?:OR|AND)\s+', '(', result, flags=re.IGNORECASE)

    # Pattern 5: Remove empty IN clauses
    # Example: "COLUMN" IN ('') or ('') → remove
    result = re.sub(
        r'"\w+"\s+IN\s+\(\'\'?\)\s+(?:or|OR)\s+\(\'\'?\)',
        '',
        result
    )

    # Pattern 6: Remove malformed comparisons with missing left operand
    # Example: ( = '00000000') → remove
    # Example: AND ( = 'value') → remove
    # This happens when parameter cleanup removes column name but leaves comparison
    result = re.sub(
        r'\s*(?:AND|OR)?\s*\(\s*=\s*[\'"][^\'"]*[\'"]\s*\)',
        '',
        result,
        flags=re.IGNORECASE
    )

    # Pattern 7: Remove empty parentheses with just operators
    # Example: (AND ) or (OR ) → remove
    result = re.sub(r'\(\s*(?:AND|OR)\s*\)', '', result, flags=re.IGNORECASE)

    # Pattern 8: Remove comparisons with empty string literal as left operand
    # Example: ('') = '00000000' → remove
    # Example: or ('') = 'value' → remove
    # Example: ( '''' = '') → remove (SQL escaped empty string)
    # This happens when $PARAM$ is replaced with '' leaving ('') = 'value'
    result = re.sub(
        r'\s*(?:AND|OR)?\s*\(\s*[\'"]+\s*=\s*[\'"]+\s*\)',
        '',
        result,
        flags=re.IGNORECASE
    )

    # Pattern 9: Remove "COLUMN" IN ('') or patterns
    # Example: "JOB" IN ('') or → remove
    result = re.sub(
        r'"\w+"\s+IN\s+\([\'"][\'"]?\)\s+(?:or|OR|and|AND)',
        '',
        result,
        flags=re.IGNORECASE
    )

    # Pattern 10: Remove empty WHERE clauses with just nested parentheses
    # Example: WHERE (( )) → remove entirely
    # Example: WHERE (( ) → remove entirely
    result = re.sub(
        r'WHERE\s+\(\(\s*\)\s*\)',
        '',
        result,
        flags=re.IGNORECASE
    )

    # Pattern 11: Remove empty WHERE clauses after all cleanup
    # Example: WHERE () → remove
    result = re.sub(
        r'WHERE\s+\(\s*\)',
        '',
        result,
        flags=re.IGNORECASE
    )

    # Final cleanup: remove malformed WHERE clauses after parameter removal
    # Pattern: WHERE ((...) AND/OR) - trailing operator with no following condition
    result = re.sub(r'WHERE\s+\(\s*\(.*?\)\s+(?:AND|OR)\s*\)', '', result, flags=re.IGNORECASE)

    # Remove unbalanced closing parentheses at end of WHERE clauses
    # Pattern: ...condition)) ) - extra closing parens
    result = re.sub(r'\)\s*\)+(?=\s*(?:FROM|GROUP|ORDER|LIMIT|$))', ')', result, flags=re.IGNORECASE)

    # Pattern 12: Balance parentheses in WHERE condition
    # NOTE: This function receives WHERE condition WITHOUT the "WHERE" keyword
    # Example input: "(("CALMONTH" = '000000')"  ← missing closing paren
    # Example output: "(("CALMONTH" = '000000'))" ← balanced
    open_count = result.count('(')
    close_count = result.count(')')

    if open_count > close_count:
        # Add missing closing parens at the end
        result = result + (')' * (open_count - close_count))
    elif close_count > open_count:
        # Remove extra closing parens from the end
        excess = close_count - open_count
        for _ in range(excess):
            result = result.rstrip()
            if result.endswith(')'):
                result = result[:-1]

    return result


def _quote_identifier_part(name: str) -> str:
    """Quote a single identifier component if needed."""

    if not name:
        return '""'

    sanitized = name
    if name and name[0].isalpha() and name.replace("_", "").isalnum():
        return sanitized.upper()
    return f'"{name}"'


def _quote_identifier(name: str) -> str:
    """Quote an identifier, preserving schema qualification."""

    if "." in name:
        schema_part, object_part = name.split(".", 1)
        return f"{_quote_identifier_part(schema_part)}.{_quote_identifier_part(object_part)}"
    return _quote_identifier_part(name)


def _assemble_sql(
    ctes: List[str], 
    final_select: str, 
    warnings: List[str], 
    view_name: Optional[str] = None,
    database_mode: DatabaseMode = DatabaseMode.SNOWFLAKE,
    scenario: Optional[Scenario] = None
) -> str:
    """Assemble final SQL with CTEs, warnings, and optional CREATE VIEW."""

    lines: List[str] = []

    if warnings:
        lines.append("-- Warnings:")
        for warning in warnings:
            lines.append(f"--   {warning}")
        lines.append("")

    if view_name:
        # Generate mode-specific VIEW statement with parameters
        view_statement = _generate_view_statement(view_name, database_mode, scenario)
        lines.append(view_statement)
    
    if ctes:
        lines.append("WITH")
        lines.append(",\n".join(ctes))
        lines.append("")

    lines.append(final_select)

    return "\n".join(lines)


def _generate_view_statement(view_name: str, mode: DatabaseMode, scenario: Optional[Scenario] = None) -> str:
    """Generate CREATE VIEW statement for target database with parameters if needed."""
    # BUG-029 FIX (SURGICAL): Always quote view names in DROP/CREATE VIEW statements
    # Unlike _quote_identifier() which preserves case-insensitivity for column names,
    # view names in DDL statements must be explicitly quoted to avoid HANA [321] errors
    # Example: "_SYS_BIC".CV_ELIG_TRANS_01 → "_SYS_BIC"."CV_ELIG_TRANS_01"
    if "." in view_name:
        # Schema-qualified name: quote each part separately
        parts = view_name.split(".")
        quoted_name = ".".join(f'"{part}"' for part in parts)
    else:
        # Simple view name: quote it
        quoted_name = f'"{view_name}"'
    
    if mode == DatabaseMode.SNOWFLAKE:
        return f"CREATE OR REPLACE VIEW {quoted_name} AS"
    elif mode == DatabaseMode.HANA:
        # ====================================================================
        # ⚠️ CRITICAL SECTION - VALIDATED IN HANA STUDIO (commit 4eff5fb)
        # ====================================================================
        # DO NOT CHANGE WITHOUT:
        # 1. Reading GOLDEN_COMMIT.yaml for last validated state
        # 2. Reading FIXES_AFTER_COMMIT_4eff5fb.md for bug fix history
        # 3. Testing in actual HANA Studio with ALL validated XMLs (see GOLDEN_COMMIT.yaml)
        # 4. Updating GOLDEN_COMMIT.yaml after successful HANA validation
        #
        # KNOWN WRONG APPROACH: CREATE OR REPLACE VIEW
        # - Tested in HANA Studio: DOES NOT WORK
        # - Error: "cannot use duplicate view name"
        # - Web search results claiming HANA supports it are WRONG for our use case
        # - Incident: SESSION 7 (2025-11-18) - see FIXES_AFTER_COMMIT_4eff5fb.md
        #
        # VALIDATED WORKING APPROACH: DROP VIEW ... CASCADE; CREATE VIEW
        # - Tested: 5/5 XMLs passing in HANA Studio (2025-11-17)
        # - Execution times: 29ms - 211ms (all successful)
        # - See: Target (SQL Scripts)/VALIDATED/ for golden SQL copies
        # ====================================================================

        # HANA SQL views don't support parameterized syntax like calculation views
        # Parameters are substituted with default values instead
        # HANA doesn't support IF EXISTS in DROP VIEW - use CASCADE to drop view and dependencies
        return f"DROP VIEW {quoted_name} CASCADE;\nCREATE VIEW {quoted_name} AS"
    else:
        # Default to Snowflake syntax
        return f"CREATE OR REPLACE VIEW {quoted_name} AS"


def _map_hana_datatype(datatype: Optional[str]) -> str:
    """Map data type string to HANA type."""
    if not datatype:
        return "NVARCHAR(100)"
    
    dt_upper = datatype.upper()
    
    # If already has length, return as-is
    if '(' in dt_upper:
        return datatype
    
    # Add default lengths
    type_defaults = {
        "NVARCHAR": "NVARCHAR(100)",
        "VARCHAR": "VARCHAR(100)",
        "INTEGER": "INTEGER",
        "DECIMAL": "DECIMAL(15,2)",
        "DATE": "DATE",
        "TIMESTAMP": "TIMESTAMP",
    }
    
    return type_defaults.get(dt_upper, f"{dt_upper}(100)")


__all__ = ["render_scenario"]

