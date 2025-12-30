"""SQL validation module for ensuring generated SQL is production-ready."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from ..domain import Scenario
from ..domain.types import DatabaseMode, HanaVersion
from .renderer import RenderContext


class ValidationSeverity(Enum):
    """Severity level of a validation issue."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """Represents a single validation issue found in SQL."""

    severity: ValidationSeverity
    message: str
    code: str
    line_number: Optional[int] = None
    column_number: Optional[int] = None

    def __str__(self) -> str:
        """String representation of the issue."""
        location = ""
        if self.line_number is not None:
            location = f" (line {self.line_number}"
            if self.column_number is not None:
                location += f", column {self.column_number}"
            location += ")"
        return f"[{self.severity.value.upper()}] {self.code}: {self.message}{location}"


@dataclass
class ValidationResult:
    """Result of SQL validation."""

    is_valid: bool
    errors: List[ValidationIssue]
    warnings: List[ValidationIssue]
    info: List[ValidationIssue]

    def __init__(self):
        """Initialize empty validation result."""
        self.is_valid = True
        self.errors = []
        self.warnings = []
        self.info = []

    @property
    def has_errors(self) -> bool:
        """Check if validation result contains any errors."""
        return len(self.errors) > 0

    @property
    def has_issues(self) -> bool:
        """Check if validation result contains any issues (errors, warnings, or info)."""
        return len(self.errors) > 0 or len(self.warnings) > 0 or len(self.info) > 0

    def add_error(self, message: str, code: str, line_number: Optional[int] = None) -> None:
        """Add an error to the validation result."""
        self.errors.append(ValidationIssue(ValidationSeverity.ERROR, message, code, line_number))
        self.is_valid = False

    def add_warning(self, message: str, code: str, line_number: Optional[int] = None) -> None:
        """Add a warning to the validation result."""
        self.warnings.append(ValidationIssue(ValidationSeverity.WARNING, message, code, line_number))

    def add_info(self, message: str, code: str, line_number: Optional[int] = None) -> None:
        """Add an informational message to the validation result."""
        self.info.append(ValidationIssue(ValidationSeverity.INFO, message, code, line_number))

    def merge(self, other: ValidationResult) -> None:
        """Merge another validation result into this one."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.info.extend(other.info)
        if other.has_errors:
            self.is_valid = False


def validate_sql_structure(sql: str) -> ValidationResult:
    """
    Validate basic SQL structure and syntax.

    Args:
        sql: SQL string to validate

    Returns:
        ValidationResult with any issues found
    """
    result = ValidationResult()

    if not sql or not sql.strip():
        result.add_error("SQL is empty", "EMPTY_SQL")
        return result

    sql_lines = sql.split("\n")
    sql_upper = sql.upper()

    # Check for SELECT statement
    if "SELECT" not in sql_upper:
        result.add_error("SQL does not contain a SELECT statement", "NO_SELECT", 1)

    # Check for balanced parentheses
    open_parens = sql.count("(")
    close_parens = sql.count(")")
    if open_parens != close_parens:
        result.add_error(
            f"Unbalanced parentheses: {open_parens} opening, {close_parens} closing",
            "UNBALANCED_PARENTHESES",
        )

    # Check for balanced quotes (basic check)
    single_quotes = sql.count("'") - sql.count("''") * 2  # Account for escaped quotes
    if single_quotes % 2 != 0:
        result.add_warning("Possible unbalanced single quotes", "UNBALANCED_QUOTES")

    # Check CTE structure
    if "WITH" in sql_upper:
        # Check for AS clauses in CTEs
        cte_pattern = r"(\w+)\s+AS\s*\("
        cte_matches = re.findall(cte_pattern, sql, re.IGNORECASE)
        if not cte_matches:
            result.add_warning("WITH clause found but no CTEs with AS detected", "INVALID_CTE_STRUCTURE")

        # Check for duplicate CTE names
        cte_names = [name.upper() for name in cte_matches]
        seen = set()
        for i, name in enumerate(cte_names):
            if name in seen:
                result.add_error(f"Duplicate CTE name: {name}", "DUPLICATE_CTE", i + 1)
            seen.add(name)

        # Check for final SELECT after CTEs
        with_index = sql_upper.find("WITH")
        select_after_with = sql_upper.find("SELECT", with_index + 4)
        if select_after_with == -1:
            result.add_error("WITH clause found but no SELECT statement after CTEs", "NO_SELECT_AFTER_CTE")

    # Check for proper statement structure
    if sql_upper.count("SELECT") == 0:
        result.add_error("No SELECT statement found", "NO_SELECT_STATEMENT")

    return result


def validate_query_completeness(
    scenario: Scenario, sql: str, ctx: RenderContext
) -> ValidationResult:
    """
    Validate that all references in SQL are complete and valid.

    Args:
        scenario: Scenario IR object
        sql: Generated SQL string
        ctx: Render context used during generation

    Returns:
        ValidationResult with any issues found
    """
    result = ValidationResult()

    # Extract CTE names from SQL
    cte_pattern = r"(\w+)\s+AS\s*\("
    cte_names_in_sql = set(re.findall(cte_pattern, sql, re.IGNORECASE))
    cte_names_in_sql = {name.upper() for name in cte_names_in_sql}

    # Also get CTE aliases from context (these are the actual CTE names used)
    cte_aliases_from_ctx = {alias.upper() for alias in ctx.cte_aliases.values()}
    all_cte_names = cte_names_in_sql | cte_aliases_from_ctx

    # Check that all referenced nodes exist
    for node_id in ctx.cte_aliases.keys():
        if node_id not in scenario.nodes and node_id not in scenario.data_sources:
            result.add_error(f"Node {node_id} referenced but not found in scenario", "MISSING_NODE")

    # Check CTE references in FROM/JOIN clauses
    from_pattern = r"FROM\s+(\w+)"
    join_pattern = r"JOIN\s+(\w+)"
    referenced_ctes = set()
    for match in re.finditer(from_pattern, sql, re.IGNORECASE):
        ref_name = match.group(1).upper()
        # Skip if it's a schema.table reference
        if "." not in ref_name:
            referenced_ctes.add(ref_name)
    for match in re.finditer(join_pattern, sql, re.IGNORECASE):
        ref_name = match.group(1).upper()
        # Skip if it's a schema.table reference
        if "." not in ref_name:
            referenced_ctes.add(ref_name)

    # Check if referenced CTEs are defined
    for ref_cte in referenced_ctes:
        if ref_cte not in all_cte_names:
            # Check if it's a data source object name
            is_data_source = any(
                ds.object_name.upper() == ref_cte for ds in scenario.data_sources.values()
            )
            if not is_data_source:
                result.add_warning(f"CTE {ref_cte} referenced in FROM/JOIN but not defined", "UNDEFINED_CTE_REFERENCE")

    # Check data source references
    for ds_id, data_source in scenario.data_sources.items():
        if not data_source.schema_name or not data_source.schema_name.strip():
            result.add_warning(f"Data source {ds_id} has empty schema name", "EMPTY_SCHEMA_NAME")
        if not data_source.object_name or not data_source.object_name.strip():
            result.add_warning(f"Data source {ds_id} has empty object name", "EMPTY_OBJECT_NAME")

    # Check final node exists (only if we have nodes)
    if len(scenario.nodes) > 0:
        final_node_id = None
        for node_id in scenario.nodes.keys():
            # Find the node that's not referenced as input by other nodes
            is_final = True
            for other_node in scenario.nodes.values():
                if hasattr(other_node, 'inputs') and node_id in other_node.inputs:
                    is_final = False
                    break
            if is_final:
                final_node_id = node_id
                break

        if not final_node_id:
            result.add_warning("Could not determine final node in scenario", "NO_FINAL_NODE")

    return result


# Snowflake reserved keywords
SNOWFLAKE_RESERVED_KEYWORDS = {
    'ACCOUNT', 'ADMIN', 'ALL', 'ALTER', 'AND', 'ANY', 'AS', 'BETWEEN',
    'BY', 'CASE', 'CAST', 'CHECK', 'COLUMN', 'CONNECT', 'CONNECTION',
    'CONSTRAINT', 'CREATE', 'CROSS', 'CURRENT', 'CURRENT_DATE',
    'CURRENT_TIME', 'CURRENT_TIMESTAMP', 'CURRENT_USER', 'DATABASE',
    'DELETE', 'DISTINCT', 'DROP', 'ELSE', 'END', 'EXISTS', 'FALSE',
    'FOLLOWING', 'FOR', 'FOREIGN', 'FROM', 'FULL', 'FUNCTION', 'GRANT',
    'GROUP', 'GROUPING', 'HAVING', 'ILIKE', 'IN', 'INNER', 'INSERT',
    'INTERSECT', 'INTO', 'IS', 'ISSUE', 'JOIN', 'LATERAL', 'LEFT',
    'LIKE', 'LOCALTIME', 'LOCALTIMESTAMP', 'MINUS', 'NATURAL', 'NOT',
    'NULL', 'NULLS', 'OF', 'ON', 'OR', 'ORDER', 'ORGANIZATION',
    'OUTER', 'OVER', 'PARTITION', 'PRECEDING', 'PRIMARY', 'QUALIFY',
    'REFERENCES', 'REVOKE', 'RIGHT', 'RLIKE', 'ROW', 'ROWS', 'SAMPLE',
    'SCHEMA', 'SELECT', 'SET', 'SOME', 'START', 'TABLE', 'TABLESAMPLE',
    'THEN', 'TO', 'TRIGGER', 'TRUE', 'TRY_CAST', 'UNION', 'UNIQUE',
    'UPDATE', 'USING', 'VALUES', 'VIEW', 'WHEN', 'WHENEVER', 'WHERE', 'WITH'
}


def validate_performance(sql: str, scenario: Scenario) -> ValidationResult:
    """
    Validate SQL for performance issues.

    Args:
        sql: SQL string to validate
        scenario: Scenario IR object for context

    Returns:
        ValidationResult with performance warnings
    """
    result = ValidationResult()
    sql_upper = sql.upper()

    # Check for cartesian products (ON 1=1)
    if re.search(r'ON\s+1\s*=\s*1', sql_upper):
        result.add_warning(
            "Cartesian product detected (JOIN ON 1=1) - may cause large result sets",
            "CARTESIAN_PRODUCT"
        )

    # Check for SELECT * usage
    select_star_pattern = r'SELECT\s+\*'
    if re.search(select_star_pattern, sql_upper):
        # Check if logical model provides column list
        if scenario.logical_model and scenario.logical_model.attributes:
            result.add_warning(
                "SELECT * used when explicit column list is available - consider using explicit columns",
                "SELECT_STAR_USAGE"
            )
        else:
            result.add_info(
                "SELECT * used - consider explicit column list for better performance",
                "SELECT_STAR_USAGE"
            )

    # Check for missing WHERE clauses on large tables
    # This is a heuristic - if we have FROM but no WHERE, warn
    from_count = len(re.findall(r'\bFROM\b', sql_upper))
    where_count = len(re.findall(r'\bWHERE\b', sql_upper))
    if from_count > 0 and where_count == 0:
        result.add_info(
            "No WHERE clause found - consider adding filters for better performance",
            "MISSING_WHERE_CLAUSE"
        )

    # Check for aggregation without GROUP BY
    agg_functions = ['COUNT', 'SUM', 'AVG', 'MAX', 'MIN', 'STDDEV', 'VARIANCE']
    has_agg = any(re.search(rf'\b{func}\s*\(', sql_upper) for func in agg_functions)
    has_group_by = 'GROUP BY' in sql_upper
    if has_agg and not has_group_by:
        # Check if it's a scalar aggregation (single row result)
        # This is usually OK, but warn if there are multiple FROM/JOIN
        if from_count > 1:
            result.add_warning(
                "Aggregation functions used without GROUP BY on multiple tables - verify correctness",
                "AGGREGATION_WITHOUT_GROUPBY"
            )

    return result


def validate_snowflake_specific(sql: str) -> ValidationResult:
    """
    Validate Snowflake-specific syntax and features.

    Args:
        sql: SQL string to validate

    Returns:
        ValidationResult with Snowflake-specific issues
    """
    result = ValidationResult()
    sql_upper = sql.upper()

    # 1. Identifier Validation
    # Check for unquoted reserved keywords used as identifiers
    # We need to be smart about this - only flag keywords that are actually used as identifiers,
    # not when they appear in SQL keyword positions
    
    # Patterns that indicate identifier usage (not SQL keywords):
    # Exclude common SQL keyword contexts to avoid false positives
    identifier_contexts = [
        r'SELECT\s+([A-Z_][A-Z0-9_]*)\s+AS',  # Column AS alias
        r'SELECT\s+([A-Z_][A-Z0-9_]*)\s*,',   # Column in SELECT list
        r'SELECT\s+([A-Z_][A-Z0-9_]*)\s+FROM',  # Column before FROM
        r'FROM\s+([A-Z_][A-Z0-9_]*)\s+(?:WHERE|JOIN|GROUP|ORDER|$)',  # Table name
        r'JOIN\s+([A-Z_][A-Z0-9_]*)\s+(?:ON|WHERE|$)',  # Table in JOIN
        r'AS\s+([A-Z_][A-Z0-9_]*)\s*(?:,|\(|$)',  # Alias after AS
        r'GROUP\s+BY\s+([A-Z_][A-Z0-9_]*)\s*(?:,|$)',  # Column in GROUP BY
        r'ORDER\s+BY\s+([A-Z_][A-Z0-9_]*)\s*(?:,|$)',  # Column in ORDER BY
        r'WHERE\s+([A-Z_][A-Z0-9_]*)\s*[=<>!]',  # Column in WHERE (but not IS NULL)
        r'\.([A-Z_][A-Z0-9_]*)\s*(?:,|$|AS|FROM|WHERE|JOIN|GROUP|ORDER)',  # Column after table.
        r'\.([A-Z_][A-Z0-9_]*)\s*[=<>!]',  # Column after table. in condition
    ]
    
    # Keywords that should never be flagged (common SQL patterns)
    excluded_keywords = {'NULL', 'TRUE', 'FALSE', 'CURRENT_DATE', 'CURRENT_TIME', 'CURRENT_TIMESTAMP'}
    
    found_identifiers = set()
    for pattern in identifier_contexts:
        for match in re.finditer(pattern, sql_upper):
            identifier = match.group(1)
            # Skip excluded keywords and check if it's actually a reserved keyword
            if identifier not in excluded_keywords and identifier in SNOWFLAKE_RESERVED_KEYWORDS:
                # Additional check: skip if it's in a context like "IS NULL", "IS NOT NULL", etc.
                context_before = sql_upper[max(0, match.start()-10):match.start()]
                if not re.search(r'\b(IS|IS\s+NOT)\s+$', context_before):
                    found_identifiers.add(identifier)
    
    # Also check CTE names (after WITH ... AS)
    cte_pattern = r'WITH\s+([A-Z_][A-Z0-9_]*)\s+AS\s*\('
    for match in re.finditer(cte_pattern, sql_upper):
        identifier = match.group(1)
        if identifier in SNOWFLAKE_RESERVED_KEYWORDS:
            found_identifiers.add(identifier)
    
    # Report warnings for found identifiers
    for identifier in found_identifiers:
        result.add_warning(
            f"Reserved keyword '{identifier}' used as identifier - should be quoted",
            "RESERVED_KEYWORD_AS_IDENTIFIER"
        )

    # Check identifier length (unquoted identifiers max 255 chars)
    long_identifier_pattern = r'\b([A-Z_][A-Z0-9_]{255,})\b'
    if re.search(long_identifier_pattern, sql_upper):
        result.add_warning(
            "Unquoted identifier exceeds 255 characters - should be quoted",
            "IDENTIFIER_TOO_LONG"
        )

    # 2. Schema/Table Naming
    # Check for unqualified table references
    from_pattern = r'FROM\s+([A-Z_][A-Z0-9_]*)'
    for match in re.finditer(from_pattern, sql_upper):
        table_name = match.group(1)
        # Skip if it's a CTE or reserved word
        if table_name not in SNOWFLAKE_RESERVED_KEYWORDS and '.' not in match.group(0):
            result.add_info(
                f"Unqualified table reference '{table_name}' - consider using schema.table format",
                "UNQUALIFIED_TABLE_REFERENCE"
            )

    # 3. Snowflake Function Syntax
    # Check IFF() function (3 parameters)
    iff_pattern = r'IFF\s*\([^)]*\)'
    for match in re.finditer(iff_pattern, sql, re.IGNORECASE):
        params = match.group(0).count(',')
        if params != 2:  # IFF(condition, then, else) = 2 commas
            result.add_warning(
                f"IFF() function should have 3 parameters (condition, then, else)",
                "INVALID_IFF_SYNTAX"
            )

    # Check string concatenation (should use ||, not +)
    # Look for string + string patterns (but not numeric addition)
    string_concat_pattern = r"(['\"][^'\"]*['\"])\s*\+\s*(['\"][^'\"]*['\"])"
    if re.search(string_concat_pattern, sql):
        result.add_warning(
            "String concatenation using '+' operator - should use '||' in Snowflake",
            "STRING_CONCAT_PLUS"
        )

    # Check for HANA IF() function (should be IFF())
    hana_if_pattern = r'\bIF\s*\([^)]+,\s*[^)]+,\s*[^)]+\)'
    if re.search(hana_if_pattern, sql, re.IGNORECASE):
        result.add_warning(
            "HANA IF() function detected - should be translated to IFF() for Snowflake",
            "HANA_IF_NOT_TRANSLATED"
        )

    # 4. Data Type Validation
    # Check type casting syntax (::TYPE)
    type_cast_pattern = r'::\s*[A-Z_][A-Z0-9_]*'
    # This is valid Snowflake syntax, so we just verify it's used correctly
    # Check for invalid type names (basic check)
    invalid_types = ['CHAR', 'VARCHAR']  # Should have length
    for match in re.finditer(type_cast_pattern, sql_upper):
        type_name = match.group(0)[2:].strip()
        if type_name in invalid_types and '(' not in match.group(0):
            result.add_warning(
                f"Type casting to {type_name} without length specification",
                "TYPE_CAST_WITHOUT_LENGTH"
            )

    # Check boolean values (should be TRUE/FALSE, not 1/0)
    boolean_pattern = r'\b(1|0)\s*(?:=|\!=|<>)\s*(?:TRUE|FALSE)'
    if re.search(boolean_pattern, sql_upper):
        result.add_warning(
            "Boolean comparison with numeric values - use TRUE/FALSE instead of 1/0",
            "BOOLEAN_NUMERIC_COMPARISON"
        )

    # 5. CTE and Query Structure
    # Check CTE count (Snowflake limit is 100)
    cte_pattern = r'(\w+)\s+AS\s*\('
    cte_count = len(re.findall(cte_pattern, sql, re.IGNORECASE))
    if cte_count > 100:
        result.add_error(
            f"CTE count ({cte_count}) exceeds Snowflake limit of 100",
            "CTE_COUNT_EXCEEDED"
        )
    elif cte_count > 20:
        result.add_warning(
            f"High CTE count ({cte_count}) - consider breaking into views for better maintainability",
            "HIGH_CTE_COUNT"
        )

    # Check for recursive CTEs
    if 'RECURSIVE' in sql_upper and 'WITH' in sql_upper:
        # Validate recursive CTE structure
        if not re.search(r'WITH\s+RECURSIVE', sql_upper):
            result.add_warning(
                "RECURSIVE keyword found but not in WITH RECURSIVE clause",
                "INVALID_RECURSIVE_CTE"
            )

    # 6. View Creation Syntax
    if 'CREATE' in sql_upper and 'VIEW' in sql_upper:
        view_pattern = r'CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+(\w+)'
        view_match = re.search(view_pattern, sql_upper)
        if view_match:
            view_name = view_match.group(1)
            if view_name.upper() in SNOWFLAKE_RESERVED_KEYWORDS:
                result.add_error(
                    f"View name '{view_name}' is a reserved keyword - must be quoted",
                    "VIEW_NAME_RESERVED_KEYWORD"
                )

    # 7. JOIN Syntax
    # Check JOIN types
    join_types = ['INNER', 'LEFT', 'RIGHT', 'FULL', 'OUTER', 'CROSS']
    for join_type in join_types:
        join_pattern = rf'\b{join_type}\s+JOIN'
        if re.search(join_pattern, sql_upper):
            # Validate ON clause exists (except for CROSS JOIN)
            if join_type != 'CROSS':
                # Check if ON clause follows
                join_matches = list(re.finditer(join_pattern, sql_upper))
                for join_match in join_matches:
                    after_join = sql_upper[join_match.end():join_match.end()+50]
                    if 'ON' not in after_join:
                        result.add_warning(
                            f"{join_type} JOIN without ON clause",
                            "JOIN_WITHOUT_ON"
                        )

    # Check for LATERAL joins
    if 'LATERAL' in sql_upper:
        if not re.search(r'LATERAL\s+(?:FLATTEN|TABLE)', sql_upper):
            result.add_info(
                "LATERAL keyword found - ensure proper usage with FLATTEN or TABLE functions",
                "LATERAL_JOIN_USAGE"
            )

    # 8. HANA to Snowflake Compatibility
    # Already checked IF() -> IFF() above
    # Check for other HANA-specific patterns
    hana_patterns = [
        (r'\bSUBSTRING\s*\(', "SUBSTRING() function - verify parameter count (Snowflake uses 1-based indexing)"),
        (r'\bTO_DATE\s*\([^)]*\)', "TO_DATE() function - verify date format string"),
    ]
    for pattern, message in hana_patterns:
        if re.search(pattern, sql, re.IGNORECASE):
            result.add_info(message, "HANA_FUNCTION_CHECK")

    # 9. Reserved Keywords (already checked in identifier validation)

    # 10. SQL Statement Validation
    # Check for DDL/DML mixed with SELECT
    ddl_keywords = ['CREATE', 'ALTER', 'DROP', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE']
    has_select = 'SELECT' in sql_upper
    has_ddl = any(keyword in sql_upper for keyword in ddl_keywords)
    if has_select and has_ddl:
        result.add_warning(
            "DDL/DML statements mixed with SELECT - ensure proper statement separation",
            "MIXED_STATEMENT_TYPES"
        )

    # 11. Performance-Specific Checks
    # Check for SAMPLE clause
    if 'SAMPLE' in sql_upper:
        sample_pattern = r'SAMPLE\s+(?:ROW|BLOCK|SYSTEM)\s*\([^)]+\)'
        if not re.search(sample_pattern, sql_upper):
            result.add_warning(
                "SAMPLE clause found - verify syntax (SAMPLE ROW/BLOCK/SYSTEM)",
                "SAMPLE_CLAUSE_SYNTAX"
            )

    # Check for QUALIFY clause (Snowflake-specific)
    if 'QUALIFY' in sql_upper:
        if 'ROW_NUMBER' not in sql_upper and 'RANK' not in sql_upper:
            result.add_info(
                "QUALIFY clause found - typically used with window functions",
                "QUALIFY_CLAUSE_USAGE"
            )

    return result


def analyze_query_complexity(sql: str, scenario: Scenario) -> ValidationResult:
    """
    Analyze query complexity and provide recommendations.

    Args:
        sql: SQL string to analyze
        scenario: Scenario IR object for context

    Returns:
        ValidationResult with complexity warnings
    """
    result = ValidationResult()

    # Count CTEs
    cte_pattern = r'(\w+)\s+AS\s*\('
    cte_count = len(re.findall(cte_pattern, sql, re.IGNORECASE))
    if cte_count > 20:
        result.add_warning(
            f"High CTE count ({cte_count}) - consider breaking into views for better maintainability",
            "HIGH_CTE_COUNT"
        )
    elif cte_count > 10:
        result.add_info(
            f"Moderate CTE count ({cte_count}) - query may benefit from view decomposition",
            "MODERATE_CTE_COUNT"
        )

    # Count JOINs
    join_count = len(re.findall(r'\bJOIN\b', sql.upper()))
    if join_count > 10:
        result.add_warning(
            f"High JOIN count ({join_count}) - consider query optimization",
            "HIGH_JOIN_COUNT"
        )
    elif join_count > 5:
        result.add_info(
            f"Moderate JOIN count ({join_count}) - verify query performance",
            "MODERATE_JOIN_COUNT"
        )

    # Count subqueries (nested SELECT)
    subquery_pattern = r'\(\s*SELECT\s+'
    subquery_count = len(re.findall(subquery_pattern, sql.upper()))
    if subquery_count > 5:
        result.add_warning(
            f"High subquery count ({subquery_count}) - consider using CTEs or joins",
            "HIGH_SUBQUERY_COUNT"
        )

    # Count nodes in scenario
    node_count = len(scenario.nodes)
    if node_count > 15:
        result.add_info(
            f"Complex scenario with {node_count} nodes - verify conversion correctness",
            "COMPLEX_SCENARIO"
        )

    return result


def validate_column_references(
    sql: str, scenario: Scenario, schema_metadata: Optional[Dict] = None
) -> ValidationResult:
    """
    Validate column references against schema metadata (Phase 3 - Optional).

    Args:
        sql: SQL string to validate
        scenario: Scenario IR object for context
        schema_metadata: Optional schema metadata dictionary with table/column info

    Returns:
        ValidationResult with column reference issues
    """
    result = ValidationResult()

    # Phase 3: Column reference validation requires schema metadata
    # This is an optional feature that requires Snowflake connection
    if not schema_metadata:
        # No metadata available - skip validation
        return result

    # Placeholder for column reference validation
    # In full implementation, this would:
    # 1. Parse SQL to extract table.column references
    # 2. Check each column exists in schema_metadata
    # 3. Validate column types for compatibility
    # 4. Check aggregation compatibility

    return result


def validate_expressions(scenario: Scenario) -> ValidationResult:
    """
    Validate expression syntax and type safety (Phase 3 - Optional).

    Args:
        scenario: Scenario IR object containing expressions to validate

    Returns:
        ValidationResult with expression validation issues
    """
    result = ValidationResult()

    # Phase 3: Expression validation
    # Validate calculated attribute expressions
    for node_id, node in scenario.nodes.items():
        # Validate calculated attributes
        for calc_name, calc_attr in node.calculated_attributes.items():
            # Basic syntax check - expression should not be empty
            # CalculatedAttribute has an expression field (Expression object)
            if not calc_attr.expression or not calc_attr.expression.value or not calc_attr.expression.value.strip():
                result.add_warning(
                    f"Empty calculated attribute expression in node {node_id}: {calc_name}",
                    "EMPTY_CALCULATED_ATTRIBUTE"
                )

        # Validate filter predicates
        # Predicate objects have 'left' and optionally 'right' Expression fields, not 'expression'
        for idx, predicate in enumerate(node.filters):
            if not predicate.left or not predicate.left.value or not predicate.left.value.strip():
                result.add_warning(
                    f"Filter predicate {idx} in node {node_id} has empty left expression",
                    "EMPTY_FILTER_PREDICATE"
                )
            # For comparison predicates, right should also be present
            if predicate.kind.value == "COMPARISON" and (not predicate.right or not predicate.right.value or not predicate.right.value.strip()):
                result.add_warning(
                    f"Comparison filter predicate {idx} in node {node_id} has empty right expression",
                    "INCOMPLETE_COMPARISON_PREDICATE"
                )

    return result


def test_sql_execution(sql: str, connection: Optional[object] = None) -> ValidationResult:
    """
    Test SQL execution with EXPLAIN PLAN or dry run (Phase 3 - Optional).

    Args:
        sql: SQL string to test
        connection: Optional database connection for execution testing

    Returns:
        ValidationResult with execution test issues
    """
    result = ValidationResult()

    # Phase 3: SQL execution testing requires database connection
    # This is an optional feature
    if not connection:
        # No connection available - skip testing
        return result

    # Placeholder for SQL execution testing
    # In full implementation, this would:
    # 1. Execute EXPLAIN PLAN to validate syntax
    # 2. Run with LIMIT 0 for dry run
    # 3. Check for runtime errors
    # 4. Validate result structure

    return result


def validate_sql(
    sql: str,
    mode: DatabaseMode,
    scenario: Scenario,
    hana_version: Optional[HanaVersion] = None,
    ctx: Optional[RenderContext] = None
) -> ValidationResult:
    """Validate SQL based on target database mode and version.
    
    This is the main validation dispatcher that routes to mode-specific validators.
    
    Args:
        sql: SQL string to validate
        mode: Target database mode (Snowflake/HANA)
        scenario: Scenario being validated
        hana_version: HANA version for HANA-specific validation
        ctx: Optional render context for additional context
    
    Returns:
        ValidationResult with all validation issues
    """
    if mode == DatabaseMode.HANA:
        return validate_hana_sql(sql, scenario, hana_version)
    elif mode == DatabaseMode.SNOWFLAKE:
        # Use existing Snowflake validation functions
        result = ValidationResult()
        
        # Run all Snowflake-specific validations
        structure_result = validate_sql_structure(sql)
        result.merge(structure_result)
        
        if ctx:
            completeness_result = validate_query_completeness(scenario, sql, ctx)
            result.merge(completeness_result)
        
        performance_result = validate_performance(sql, scenario)
        result.merge(performance_result)
        
        snowflake_result = validate_snowflake_specific(sql)
        result.merge(snowflake_result)
        
        complexity_result = analyze_query_complexity(sql, scenario)
        result.merge(complexity_result)
        
        return result
    else:
        # Unknown mode - return generic structure validation
        return validate_sql_structure(sql)


def validate_hana_sql(
    sql: str,
    scenario: Scenario,
    hana_version: Optional[HanaVersion] = None
) -> ValidationResult:
    """Validate SQL for SAP HANA with version-specific checks.
    
    Args:
        sql: SQL string to validate
        scenario: Scenario being validated
        hana_version: HANA version for version-specific validation
    
    Returns:
        ValidationResult with HANA-specific validation issues
    """
    result = ValidationResult()
    
    # 1. Basic structure validation (common for all databases)
    structure_result = validate_sql_structure(sql)
    result.merge(structure_result)
    
    # 2. HANA-specific syntax checks
    
    # Check for IFF (should be IF in HANA)
    if re.search(r'\bIFF\s*\(', sql, re.IGNORECASE):
        result.add_error(
            "IFF() function is not supported in HANA - should be IF()",
            "HANA_INVALID_IFF_FUNCTION"
        )
    
    # Check for Snowflake-specific || concatenation
    # Note: HANA supports || but + is more common, so this is a warning
    if ' || ' in sql:
        result.add_warning(
            "String concatenation using '||' detected - HANA typically uses '+' operator",
            "HANA_CONCAT_SYNTAX"
        )
    
    # Check for CREATE OR REPLACE VIEW (not supported in older HANA)
    if re.search(r'CREATE\s+OR\s+REPLACE\s+VIEW', sql, re.IGNORECASE):
        result.add_warning(
            "CREATE OR REPLACE VIEW not supported in all HANA versions - may need to DROP VIEW first",
            "HANA_CREATE_OR_REPLACE"
        )
    
    # Check for NUMBER data type (should be DECIMAL in HANA)
    if re.search(r'\bNUMBER\s*\(', sql, re.IGNORECASE):
        result.add_warning(
            "NUMBER data type is Snowflake-specific - HANA uses DECIMAL",
            "HANA_NUMBER_TYPE"
        )
    
    # Check for TIMESTAMP_NTZ (should be TIMESTAMP in HANA)
    if re.search(r'\bTIMESTAMP_NTZ\b', sql, re.IGNORECASE):
        result.add_warning(
            "TIMESTAMP_NTZ is Snowflake-specific - HANA uses TIMESTAMP",
            "HANA_TIMESTAMP_TYPE"
        )
    
    # 3. Version-specific feature validation
    if hana_version:
        version_result = _validate_hana_version_features(sql, hana_version)
        result.merge(version_result)
    
    # 4. Performance validation (same for all modes)
    performance_result = validate_performance(sql, scenario)
    result.merge(performance_result)
    
    # 5. Query complexity (informational, same for all modes)
    complexity_result = analyze_query_complexity(sql, scenario)
    result.merge(complexity_result)
    
    return result


def _validate_hana_version_features(sql: str, version: HanaVersion) -> ValidationResult:
    """Check if SQL uses features available in target HANA version.
    
    Args:
        sql: SQL string to validate
        version: Target HANA version
    
    Returns:
        ValidationResult with version-specific issues
    """
    result = ValidationResult()
    
    # Features requiring HANA 2.0 SPS01+
    if version < HanaVersion.HANA_2_0_SPS01:
        if re.search(r'\bINTERSECT\b', sql, re.IGNORECASE):
            result.add_error(
                f"INTERSECT operator requires HANA 2.0 SPS01+ (current: {version.value})",
                "HANA_VERSION_INTERSECT"
            )
        if re.search(r'\bEXCEPT\b|\bMINUS\b', sql, re.IGNORECASE):
            result.add_error(
                f"EXCEPT/MINUS operator requires HANA 2.0 SPS01+ (current: {version.value})",
                "HANA_VERSION_MINUS"
            )
    
    # Features requiring HANA 2.0 SPS03+
    if version < HanaVersion.HANA_2_0_SPS03:
        # Window functions with IGNORE NULLS
        if re.search(r'IGNORE\s+NULLS', sql, re.IGNORECASE):
            result.add_warning(
                f"IGNORE NULLS in window functions may not be supported in HANA < 2.0 SPS03 (current: {version.value})",
                "HANA_VERSION_IGNORE_NULLS"
            )
    
    # Features requiring minimum HANA 1.0
    if version < HanaVersion.HANA_1_0:
        if re.search(r'\bADD_MONTHS\s*\(', sql, re.IGNORECASE):
            result.add_error(
                f"ADD_MONTHS function not available in HANA < 1.0 (current: {version.value})",
                "HANA_VERSION_ADD_MONTHS"
            )
    
    return result

