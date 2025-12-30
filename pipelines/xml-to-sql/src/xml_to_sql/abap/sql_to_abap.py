"""
SQL to Pure ABAP Converter

Converts SQL with CTE structure (generated from XML) to Pure ABAP code.
This approach provides cleaner conversion than XML→ABAP because:
1. SQL has explicit JOIN conditions
2. SQL has explicit WHERE clauses
3. Data flow is linear and clear

Pipeline:
  XML → SQL (existing renderer) → Pure ABAP (this module)

Or direct:
  SQL file → Pure ABAP (this module)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple, Set


class CTEType(Enum):
    """Type of CTE in the SQL."""
    BASE_TABLE = "base"      # SELECT FROM actual table
    JOIN = "join"            # JOIN between CTEs
    UNION = "union"          # UNION of CTEs
    FILTER = "filter"        # SELECT FROM CTE with WHERE


# ==============================================================================
# BUSINESS FILTERS - Apply at SELECT level to reduce data volume
# Discovered from Session 16 TIME_OUT analysis (2400s dump on full table scans)
# ==============================================================================
BUSINESS_FILTERS = {
    # BW metadata tables - objvers='A' for active version
    'ROOSOURCE': ["objvers = 'A'", "type <> 'HIER'"],
    'ROOSFIELD': ["objvers = 'A'"],
    'RSDIOBJ': ["objvers = 'A'"],
    'RSDIOBJT': ["objvers = 'A'"],

    # Text tables - language filter (English)
    'ROOSOURCET': ["langu = 'E'"],
    'DD03T': ["ddlanguage = 'E'"],
    'DD04T': ["ddlanguage = 'E'"],

    # DD03L - exclude technical include fields
    'DD03L': ["fieldname NOT LIKE '.INCLUDE%'", "fieldname NOT LIKE 'INCLU-%'"],
}


@dataclass
class SQLColumn:
    """Represents a column in SELECT."""
    source: str          # Table/CTE alias
    name: str            # Column name
    alias: Optional[str] = None  # AS alias


@dataclass
class JoinCondition:
    """Represents a JOIN ON condition."""
    left_table: str
    left_column: str
    right_table: str
    right_column: str


@dataclass
class WhereCondition:
    """Represents a WHERE condition."""
    column: str
    operator: str        # =, <>, IN, NOT IN, etc.
    value: str           # Literal value or list
    table_alias: Optional[str] = None


@dataclass
class ParsedCTE:
    """Parsed CTE definition."""
    name: str
    cte_type: CTEType = CTEType.BASE_TABLE  # Default, will be set during parsing
    columns: List[SQLColumn] = field(default_factory=list)

    # For BASE_TABLE type
    source_table: Optional[str] = None
    source_schema: Optional[str] = None
    where_conditions: List[WhereCondition] = field(default_factory=list)

    # For JOIN type
    left_input: Optional[str] = None
    right_input: Optional[str] = None
    join_type: str = "INNER"
    join_conditions: List[JoinCondition] = field(default_factory=list)

    # For UNION type
    union_inputs: List[str] = field(default_factory=list)
    union_all: bool = True

    # For FILTER type (SELECT FROM CTE WHERE)
    filter_input: Optional[str] = None


@dataclass
class ParsedSQL:
    """Complete parsed SQL structure."""
    ctes: Dict[str, ParsedCTE] = field(default_factory=dict)
    final_columns: List[str] = field(default_factory=list)
    final_cte: Optional[str] = None
    execution_order: List[str] = field(default_factory=list)


def parse_sql(sql: str) -> ParsedSQL:
    """
    Parse SQL with CTE structure into structured format.

    Args:
        sql: SQL string with WITH...AS structure

    Returns:
        ParsedSQL with all CTEs and relationships
    """
    result = ParsedSQL()

    # BUG-038: Strip SQL comments before processing
    # Comments at the beginning (-- ...) prevent detection of DROP VIEW/CREATE VIEW
    lines = sql.strip().split('\n')
    non_comment_lines = []
    for line in lines:
        stripped = line.strip()
        # Skip pure comment lines and empty lines
        if stripped.startswith('--') or stripped == '':
            continue
        # Handle inline comments (remove everything after --)
        if '--' in stripped:
            stripped = stripped[:stripped.index('--')].strip()
        if stripped:
            non_comment_lines.append(stripped)
    sql = ' '.join(non_comment_lines)

    # Normalize whitespace
    sql = re.sub(r'\s+', ' ', sql.strip())

    # Handle CREATE VIEW ... AS WITH ... pattern
    # Also handle DROP VIEW statements at the beginning
    sql_upper = sql.upper()

    # Skip DROP VIEW statement if present
    if sql_upper.startswith('DROP VIEW'):
        # Find end of DROP statement (semicolon)
        drop_end = sql.find(';')
        if drop_end != -1:
            sql = sql[drop_end + 1:].strip()
            sql_upper = sql.upper()

    # Handle CREATE VIEW ... AS pattern
    if sql_upper.startswith('CREATE VIEW'):
        # Find "AS" followed by "WITH"
        as_with_match = re.search(r'\bAS\s+WITH\b', sql, re.IGNORECASE)
        if as_with_match:
            # Extract just the WITH part
            sql = sql[as_with_match.start() + 2:].strip()  # Skip "AS"
            sql_upper = sql.upper()

    # Check for WITH clause
    if not sql_upper.startswith('WITH'):
        # Simple SELECT without CTEs - not supported for Pure ABAP
        raise ValueError("SQL must have WITH clause with CTEs for Pure ABAP conversion")

    # Split into CTE definitions and final SELECT
    # Find the last SELECT that's not inside a CTE
    cte_section, final_select = _split_ctes_and_final(sql)

    # Parse each CTE
    # BUG-039 FIX: Lowercase CTE keys for consistent lookup
    # Input references (union_inputs, left_input, right_input, filter_input) are all lowercased
    # So CTE keys must also be lowercased to match
    cte_defs = _extract_cte_definitions(cte_section)
    for cte_name, cte_body in cte_defs:
        parsed_cte = _parse_cte_body(cte_name, cte_body)
        result.ctes[cte_name.lower()] = parsed_cte

    # Parse final SELECT
    result.final_columns, result.final_cte = _parse_final_select(final_select)

    # Determine execution order (topological sort)
    result.execution_order = _determine_execution_order(result.ctes)

    return result


def _split_ctes_and_final(sql: str) -> Tuple[str, str]:
    """Split SQL into CTE section and final SELECT."""
    # Find the final SELECT (not inside parentheses)
    depth = 0
    last_select_pos = -1

    i = 0
    while i < len(sql):
        if sql[i] == '(':
            depth += 1
        elif sql[i] == ')':
            depth -= 1
        elif depth == 0 and sql[i:i+6].upper() == 'SELECT':
            last_select_pos = i
        i += 1

    if last_select_pos == -1:
        raise ValueError("No final SELECT found in SQL")

    cte_section = sql[:last_select_pos].strip()
    final_select = sql[last_select_pos:].strip()

    # Remove trailing comma from CTE section if present
    if cte_section.endswith(','):
        cte_section = cte_section[:-1].strip()

    return cte_section, final_select


def _extract_cte_definitions(cte_section: str) -> List[Tuple[str, str]]:
    """Extract individual CTE definitions from WITH clause."""
    # Remove leading WITH
    cte_section = re.sub(r'^WITH\s+', '', cte_section, flags=re.IGNORECASE)

    ctes = []
    depth = 0
    current_name = ""
    current_body_start = -1
    i = 0

    while i < len(cte_section):
        char = cte_section[i]

        if char == '(':
            if depth == 0:
                # Start of CTE body
                current_body_start = i + 1
            depth += 1
        elif char == ')':
            depth -= 1
            if depth == 0:
                # End of CTE body
                body = cte_section[current_body_start:i].strip()
                ctes.append((current_name.strip(), body))
                current_name = ""
                current_body_start = -1
        elif depth == 0:
            # Outside parentheses - look for CTE name
            if cte_section[i:i+2].upper() == 'AS':
                # Found AS keyword, name is what we've accumulated
                i += 1  # Skip 'AS'
            elif char == ',':
                # Separator between CTEs
                pass
            else:
                if current_body_start == -1:
                    current_name += char
        i += 1

    return ctes


def _parse_cte_body(cte_name: str, body: str) -> ParsedCTE:
    """Parse a single CTE body."""
    cte = ParsedCTE(name=cte_name.lower())

    # Detect CTE type by analyzing the FROM clause
    body_upper = body.upper()

    # Check for UNION
    if ' UNION ' in body_upper:
        cte.cte_type = CTEType.UNION
        _parse_union_cte(cte, body)
        return cte

    # Check for JOIN
    if ' JOIN ' in body_upper:
        cte.cte_type = CTEType.JOIN
        _parse_join_cte(cte, body)
        return cte

    # Check if FROM references a table or CTE
    from_match = re.search(r'FROM\s+(\w+)\.(\w+)', body, re.IGNORECASE)
    if from_match:
        # FROM schema.table - base table
        cte.cte_type = CTEType.BASE_TABLE
        cte.source_schema = from_match.group(1)
        cte.source_table = from_match.group(2)
        _parse_base_cte(cte, body)
    else:
        # FROM cte_name - filter on CTE
        from_match = re.search(r'FROM\s+(\w+)', body, re.IGNORECASE)
        if from_match:
            cte.cte_type = CTEType.FILTER
            cte.filter_input = from_match.group(1).lower()
            _parse_filter_cte(cte, body)

    return cte


def _parse_base_cte(cte: ParsedCTE, body: str) -> None:
    """Parse a base table CTE (SELECT FROM schema.table)."""
    # Extract columns from SELECT
    select_match = re.search(r'SELECT\s+(.*?)\s+FROM', body, re.IGNORECASE | re.DOTALL)
    if select_match:
        columns_str = select_match.group(1)
        cte.columns = _parse_columns(columns_str, cte.source_table)

    # Extract WHERE conditions
    where_match = re.search(r'WHERE\s+(.*?)$', body, re.IGNORECASE | re.DOTALL)
    if where_match:
        cte.where_conditions = _parse_where(where_match.group(1))


def _parse_join_cte(cte: ParsedCTE, body: str) -> None:
    """Parse a JOIN CTE."""
    # Extract columns from SELECT
    select_match = re.search(r'SELECT\s+(.*?)\s+FROM', body, re.IGNORECASE | re.DOTALL)
    if select_match:
        columns_str = select_match.group(1)
        cte.columns = _parse_columns(columns_str)

    # Extract FROM and JOIN parts
    # Pattern: FROM left_cte AS alias [INNER|LEFT OUTER|RIGHT OUTER|FULL] JOIN right_cte AS alias ON conditions
    # Note: Must handle "LEFT OUTER JOIN", "RIGHT OUTER JOIN" etc.
    join_match = re.search(
        r'FROM\s+(\w+)\s+AS\s+(\w+)\s+(INNER|LEFT(?:\s+OUTER)?|RIGHT(?:\s+OUTER)?|FULL(?:\s+OUTER)?|CROSS)?\s*JOIN\s+(\w+)\s+AS\s+(\w+)\s+ON\s+(.*?)(?:$|WHERE)',
        body,
        re.IGNORECASE | re.DOTALL
    )

    if join_match:
        cte.left_input = join_match.group(1).lower()
        cte.right_input = join_match.group(4).lower()
        # Normalize join type: "LEFT OUTER" -> "LEFT", etc.
        join_type_raw = (join_match.group(3) or "INNER").upper()
        if "LEFT" in join_type_raw:
            cte.join_type = "LEFT"
        elif "RIGHT" in join_type_raw:
            cte.join_type = "RIGHT"
        elif "FULL" in join_type_raw:
            cte.join_type = "FULL"
        elif "CROSS" in join_type_raw:
            cte.join_type = "CROSS"
        else:
            cte.join_type = "INNER"
        on_clause = join_match.group(6).strip()
        cte.join_conditions = _parse_join_conditions(on_clause)


def _parse_union_cte(cte: ParsedCTE, body: str) -> None:
    """Parse a UNION CTE."""
    # Check if UNION ALL
    cte.union_all = 'UNION ALL' in body.upper()

    # Split by UNION
    parts = re.split(r'\s+UNION\s+(?:ALL\s+)?', body, flags=re.IGNORECASE)

    for part in parts:
        # Extract the FROM CTE name
        from_match = re.search(r'FROM\s+(\w+)', part, re.IGNORECASE)
        if from_match:
            cte.union_inputs.append(from_match.group(1).lower())

    # Get columns from first part
    select_match = re.search(r'SELECT\s+(.*?)\s+FROM', parts[0], re.IGNORECASE | re.DOTALL)
    if select_match:
        cte.columns = _parse_columns(select_match.group(1))


def _parse_filter_cte(cte: ParsedCTE, body: str) -> None:
    """Parse a filter CTE (SELECT FROM another_cte WHERE)."""
    # Extract columns
    select_match = re.search(r'SELECT\s+(.*?)\s+FROM', body, re.IGNORECASE | re.DOTALL)
    if select_match:
        cte.columns = _parse_columns(select_match.group(1))

    # Extract WHERE
    where_match = re.search(r'WHERE\s+(.*?)$', body, re.IGNORECASE | re.DOTALL)
    if where_match:
        cte.where_conditions = _parse_where(where_match.group(1))


def _parse_columns(columns_str: str, default_source: str = None) -> List[SQLColumn]:
    """Parse column list from SELECT clause."""
    columns = []

    # Split by comma, handling nested parentheses
    parts = _split_by_comma(columns_str)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Pattern 1: schema.table.column AS alias (three-part name)
        col_match = re.match(r'(\w+)\.(\w+)\.(\w+)(?:\s+AS\s+(\w+))?', part, re.IGNORECASE)
        if col_match:
            columns.append(SQLColumn(
                source=f"{col_match.group(1)}.{col_match.group(2)}",  # schema.table
                name=col_match.group(3),  # column
                alias=col_match.group(4)  # alias
            ))
            continue

        # Pattern 2: source.column AS alias (two-part name)
        col_match = re.match(r'(\w+)\.(\w+)(?:\s+AS\s+(\w+))?', part, re.IGNORECASE)
        if col_match:
            columns.append(SQLColumn(
                source=col_match.group(1),
                name=col_match.group(2),
                alias=col_match.group(3)
            ))
            continue

        # ABAP-001 FIX: Pattern 2b: Expression/function AS alias (e.g., TO_VARCHAR(...) AS FROMDATE)
        # Also handles arithmetic expressions like DATUM+ZEIT AS EXECUTED_ON
        # Also handles literal constants like 1 AS NUM_EXECUTIONS
        # Must check BEFORE simple column pattern because regex would match only first part
        is_expression = '(' in part or '+' in part or '*' in part or '/' in part
        # Check for numeric literal: starts with digit
        is_literal = part.strip()[0].isdigit() if part.strip() else False
        if is_expression or is_literal:
            # This is a calculated column (function call or arithmetic expression)
            expr_match = re.search(r'\s+AS\s+(\w+)\s*$', part, re.IGNORECASE)
            if expr_match:
                alias = expr_match.group(1)
                columns.append(SQLColumn(
                    source="",  # Empty source = calculated column, use TYPE string
                    name=alias,  # Use alias as the name
                    alias=alias
                ))
            else:
                # Expression without alias - try to extract function name or skip
                func_match = re.match(r'(\w+)\s*\(', part)
                if func_match:
                    columns.append(SQLColumn(
                        source="",  # Calculated column
                        name=func_match.group(1),
                        alias=None
                    ))
            continue

        # Pattern 3: Simple column name
        alias_match = re.match(r'(\w+)(?:\s+AS\s+(\w+))?', part, re.IGNORECASE)
        if alias_match:
            columns.append(SQLColumn(
                source=default_source or "",
                name=alias_match.group(1),
                alias=alias_match.group(2)
            ))

    return columns


def _parse_where(where_str: str) -> List[WhereCondition]:
    """Parse WHERE clause into conditions."""
    conditions = []

    # Split by AND (simple approach - doesn't handle OR or nested)
    parts = re.split(r'\s+AND\s+', where_str, flags=re.IGNORECASE)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Pattern: table.column = 'value' or table.column <> 'value'
        cond_match = re.match(
            r"(\w+)\.(\w+)\s*(=|<>|!=|IN|NOT\s+IN)\s*(.+)",
            part,
            re.IGNORECASE
        )
        if cond_match:
            conditions.append(WhereCondition(
                table_alias=cond_match.group(1),
                column=cond_match.group(2),
                operator=cond_match.group(3).upper(),
                value=cond_match.group(4).strip()
            ))
        else:
            # Try without table alias
            cond_match = re.match(
                r"(\w+)\s*(=|<>|!=|IN|NOT\s+IN)\s*(.+)",
                part,
                re.IGNORECASE
            )
            if cond_match:
                conditions.append(WhereCondition(
                    column=cond_match.group(1),
                    operator=cond_match.group(2).upper(),
                    value=cond_match.group(3).strip()
                ))

    return conditions


def _parse_join_conditions(on_clause: str) -> List[JoinCondition]:
    """Parse JOIN ON conditions."""
    conditions = []

    # Split by AND
    parts = re.split(r'\s+AND\s+', on_clause, flags=re.IGNORECASE)

    for part in parts:
        part = part.strip()
        # Pattern: left.col = right.col
        match = re.match(r'(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)', part)
        if match:
            conditions.append(JoinCondition(
                left_table=match.group(1),
                left_column=match.group(2),
                right_table=match.group(3),
                right_column=match.group(4)
            ))

    return conditions


def _parse_final_select(select_sql: str) -> Tuple[List[str], str]:
    """Parse the final SELECT statement."""
    columns = []
    from_cte = None

    # Extract columns
    select_match = re.search(r'SELECT\s+(.*?)\s+FROM', select_sql, re.IGNORECASE | re.DOTALL)
    if select_match:
        col_str = select_match.group(1)
        for col in col_str.split(','):
            col = col.strip()
            if col:
                columns.append(col)

    # Extract FROM CTE
    from_match = re.search(r'FROM\s+(\w+)', select_sql, re.IGNORECASE)
    if from_match:
        from_cte = from_match.group(1).lower()

    return columns, from_cte


def _split_by_comma(s: str) -> List[str]:
    """Split string by comma, respecting parentheses."""
    parts = []
    depth = 0
    current = ""

    for char in s:
        if char == '(':
            depth += 1
            current += char
        elif char == ')':
            depth -= 1
            current += char
        elif char == ',' and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += char

    if current:
        parts.append(current)

    return parts


def _determine_execution_order(ctes: Dict[str, ParsedCTE]) -> List[str]:
    """Determine CTE execution order using topological sort."""
    # Build dependency graph
    dependencies: Dict[str, Set[str]] = {}

    for name, cte in ctes.items():
        deps = set()

        if cte.cte_type == CTEType.JOIN:
            if cte.left_input:
                deps.add(cte.left_input)
            if cte.right_input:
                deps.add(cte.right_input)
        elif cte.cte_type == CTEType.FILTER:
            if cte.filter_input:
                deps.add(cte.filter_input)
        elif cte.cte_type == CTEType.UNION:
            deps.update(cte.union_inputs)

        dependencies[name] = deps

    # Topological sort
    order = []
    visited = set()
    temp_visited = set()

    def visit(name: str):
        if name in temp_visited:
            raise ValueError(f"Circular dependency detected: {name}")
        if name in visited:
            return

        temp_visited.add(name)

        if name in dependencies:
            for dep in dependencies[name]:
                if dep in ctes:  # Only visit if it's a CTE (not a base table)
                    visit(dep)

        temp_visited.remove(name)
        visited.add(name)
        order.append(name)

    for name in ctes:
        if name not in visited:
            visit(name)

    return order


def generate_pure_abap_from_sql(
    sql: str,
    scenario_id: str = "CONVERTED",
    schema_mapping: Optional[Dict[str, str]] = None
) -> str:
    """
    Generate Pure ABAP from SQL with CTE structure.

    Args:
        sql: SQL string with WITH...AS CTEs
        scenario_id: Name for the generated report
        schema_mapping: Optional schema name overrides

    Returns:
        Complete ABAP Report source code
    """
    # Parse SQL
    parsed = parse_sql(sql)

    # Generate ABAP
    return _generate_abap_program(parsed, scenario_id, schema_mapping or {})


def _generate_abap_program(
    parsed: ParsedSQL,
    scenario_id: str,
    schema_mapping: Dict[str, str]
) -> str:
    """Generate complete ABAP program from parsed SQL."""

    program_name = f"Z_PURE_{_sanitize_name(scenario_id, 20)}".upper()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Collect all tables and their columns
    table_info = _collect_table_info(parsed)

    # Generate type definitions
    type_defs = _gen_type_definitions(parsed, table_info)

    # Generate data declarations
    data_decls = _gen_data_declarations(parsed, table_info)

    # Generate fetch logic with FOR ALL ENTRIES
    fetch_code = _gen_fetch_code(parsed, table_info, schema_mapping)

    # Generate export code
    export_code = _gen_export_code(parsed)

    abap_code = f'''*&---------------------------------------------------------------------*
*& Report {program_name}
*&---------------------------------------------------------------------*
*& Generated by XML2SQL Converter - Pure ABAP Mode (SQL Pipeline)
*& Timestamp: {timestamp}
*& Source: {scenario_id}
*&
*& This program uses native ABAP SELECT statements with FOR ALL ENTRIES.
*& Properly handles JOINs through sequential fetches.
*& Works on ANY SAP system regardless of database backend.
*&---------------------------------------------------------------------*
REPORT {program_name.lower()}.

*----------------------------------------------------------------------*
* Selection Screen
*----------------------------------------------------------------------*
SELECTION-SCREEN BEGIN OF BLOCK b1 WITH FRAME TITLE TEXT-001.
  PARAMETERS:
    p_path   TYPE string DEFAULT 'C:\\temp\\{scenario_id.lower()}.csv' LOWER CASE,
    p_gui    TYPE abap_bool AS CHECKBOX DEFAULT abap_true,
    p_head   TYPE abap_bool AS CHECKBOX DEFAULT abap_true,
    p_delim  TYPE c LENGTH 1 DEFAULT ','.
SELECTION-SCREEN END OF BLOCK b1.

*----------------------------------------------------------------------*
* Type Definitions
*----------------------------------------------------------------------*
{type_defs}

*----------------------------------------------------------------------*
* Data Declarations
*----------------------------------------------------------------------*
{data_decls}

DATA: lt_csv    TYPE TABLE OF string,
      lv_line   TYPE string,
      lv_count  TYPE i.

*----------------------------------------------------------------------*
* Main Processing
*----------------------------------------------------------------------*
START-OF-SELECTION.

  WRITE: / 'Starting data retrieval...'.
  WRITE: / 'Scenario:', '{scenario_id}'.

  PERFORM fetch_data.
  PERFORM export_csv.

  WRITE: / 'Export completed.'.
  WRITE: / 'Records:', lv_count.
  WRITE: / 'File:', p_path.

*&---------------------------------------------------------------------*
*& Form FETCH_DATA
*&---------------------------------------------------------------------*
FORM fetch_data.
{fetch_code}
ENDFORM.

*&---------------------------------------------------------------------*
*& Form EXPORT_CSV
*&---------------------------------------------------------------------*
FORM export_csv.
  DATA: lv_sep TYPE string.
  lv_sep = p_delim.

{export_code}

  IF p_gui = abap_true.
    PERFORM download_gui.
  ELSE.
    PERFORM download_server.
  ENDIF.
ENDFORM.

*&---------------------------------------------------------------------*
*& Form DOWNLOAD_GUI
*&---------------------------------------------------------------------*
FORM download_gui.
  DATA: lv_fullpath TYPE string.
  lv_fullpath = p_path.

  CALL FUNCTION 'GUI_DOWNLOAD'
    EXPORTING
      filename              = lv_fullpath
      filetype              = 'ASC'
      codepage              = '4103'  " UTF-8 for Unicode/Hebrew support
      write_field_separator = space
    TABLES
      data_tab              = lt_csv
    EXCEPTIONS
      OTHERS                = 99.

  IF sy-subrc <> 0.
    WRITE: / 'Error during GUI download. RC:', sy-subrc.
  ELSE.
    WRITE: / 'File downloaded to:', lv_fullpath.
  ENDIF.
ENDFORM.

*&---------------------------------------------------------------------*
*& Form DOWNLOAD_SERVER
*&---------------------------------------------------------------------*
FORM download_server.
  DATA: lv_filename TYPE string.
  lv_filename = p_path.

  OPEN DATASET lv_filename FOR OUTPUT IN TEXT MODE ENCODING UTF-8.

  IF sy-subrc <> 0.
    WRITE: / 'Error opening file:', lv_filename.
    RETURN.
  ENDIF.

  LOOP AT lt_csv INTO lv_line.
    TRANSFER lv_line TO lv_filename.
  ENDLOOP.

  CLOSE DATASET lv_filename.
  WRITE: / 'File saved to server:', lv_filename.
ENDFORM.
'''

    return abap_code


def _sanitize_name(name: str, max_len: int = 30) -> str:
    """Sanitize name for ABAP identifier."""
    clean = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    if clean and not clean[0].isalpha():
        clean = 'X_' + clean
    return clean[:max_len].upper()


def _collect_table_info(parsed: ParsedSQL) -> Dict[str, Dict[str, List[str]]]:
    """Collect table names and their columns from parsed SQL.

    ABAP-001 FIX: Separate real table columns from calculated columns.
    Returns dict: {table: {'real': [col1, col2], 'calculated': [calc1, calc2]}}
    """
    info = {}

    for name, cte in parsed.ctes.items():
        if cte.cte_type == CTEType.BASE_TABLE and cte.source_table:
            table = cte.source_table.upper()
            real_cols = []
            calc_cols = []
            for c in cte.columns:
                col_name = c.alias or c.name
                # ABAP-001: Empty source means calculated column
                if c.source == "":
                    calc_cols.append(col_name)
                else:
                    real_cols.append(col_name)
            info[table] = {'real': real_cols, 'calculated': calc_cols}

    return info


def _gen_type_definitions(parsed: ParsedSQL, table_info: Dict[str, Dict[str, List[str]]]) -> str:
    """Generate TYPES declarations using dictionary type references.

    ABAP-001 FIX: Uses TABLE-FIELD for real columns, TYPE string for calculated.
    Uses TABLE-FIELD syntax to ensure FOR ALL ENTRIES works correctly
    (fields must have matching types).
    """
    lines = []

    # Type for each base table - use dictionary references for real columns
    for table, col_info in table_info.items():
        struct_name = f"ty_{_sanitize_name(table, 26)}".lower()
        table_lower = table.lower()
        lines.append(f"TYPES: BEGIN OF {struct_name},")
        # Real columns use TYPE table-field
        for col in col_info['real']:
            lines.append(f"         {col.lower()} TYPE {table_lower}-{col.lower()},")
        # ABAP-001: Calculated columns use TYPE string
        for col in col_info['calculated']:
            lines.append(f"         {col.lower()} TYPE string,  \" calculated column")
        lines.append(f"       END OF {struct_name}.")
        lines.append("")

    # Generate types for intermediate CTEs (UNIONs, FILTERs, JOINs between CTEs)
    # These need their own types since they may have columns from multiple sources
    intermediate_ctes = _get_intermediate_ctes(parsed)
    for cte_name, cte in intermediate_ctes.items():
        struct_name = f"ty_{_sanitize_name(cte_name, 26)}".lower()
        lines.append(f"TYPES: BEGIN OF {struct_name},")
        for col in cte.columns:
            col_name = (col.alias or col.name).lower()
            # Try to find source table for this column
            source_table = _find_column_source_in_cte(parsed, cte, col_name)
            if source_table:
                lines.append(f"         {col_name} TYPE {source_table.lower()}-{col_name},")
            else:
                # Fallback to string if source unknown
                lines.append(f"         {col_name} TYPE string,")
        lines.append(f"       END OF {struct_name}.")
        lines.append("")

    # Type for final result - needs to use string since columns come from multiple tables
    # Or we could pick the first source table for each column
    if parsed.final_columns:
        lines.append("TYPES: BEGIN OF ty_result,")
        for col in parsed.final_columns:
            # For result type, we need to find the source table for this column
            source_table = _find_column_source(parsed, col)
            if source_table:
                lines.append(f"         {col.lower()} TYPE {source_table.lower()}-{col.lower()},")
            else:
                # Fallback to string if source unknown
                lines.append(f"         {col.lower()} TYPE string,")
        lines.append("       END OF ty_result.")
        lines.append("")

    return "\n".join(lines)


def _get_intermediate_ctes(parsed: ParsedSQL) -> Dict[str, ParsedCTE]:
    """Get CTEs that need intermediate internal tables.

    SESSION 17 CHANGE: Minimize intermediate tables while preserving UNION/FILTER functionality.
    - UNION and FILTER CTEs always need intermediate tables
    - JOINs that are inputs to UNION/FILTER need intermediate tables
    - JOINs that lead to final result are assembled directly (no lt_join_N)
    This follows the FOR ALL ENTRIES pattern documented in PURE_ABAP_RULES.md.
    """
    result = {}

    # First pass: find all CTEs that are inputs to UNION or FILTER
    # These CTEs MUST have intermediate tables because UNION/FILTER reference them
    required_inputs: Set[str] = set()
    for name, cte in parsed.ctes.items():
        if cte.cte_type == CTEType.UNION:
            required_inputs.update(cte.union_inputs)
        elif cte.cte_type == CTEType.FILTER:
            if cte.filter_input:
                required_inputs.add(cte.filter_input)

    # Second pass: add UNION, FILTER, and their required inputs
    for name, cte in parsed.ctes.items():
        if cte.cte_type == CTEType.UNION:
            result[name] = cte
        elif cte.cte_type == CTEType.FILTER:
            result[name] = cte
        elif name in required_inputs:
            # This CTE is an input to UNION/FILTER - needs intermediate table
            result[name] = cte

    # Third pass: recursively add JOINs that are inputs to already-included CTEs
    # This handles chains like: join_2 -> join_3 -> filter
    changed = True
    while changed:
        changed = False
        # Create snapshot to avoid modifying dict during iteration
        current_names = list(result.keys())
        for name in current_names:
            cte = result[name]
            if cte.cte_type == CTEType.JOIN:
                if cte.left_input and cte.left_input not in result:
                    left_cte = parsed.ctes.get(cte.left_input)
                    if left_cte and left_cte.cte_type == CTEType.JOIN:
                        result[cte.left_input] = left_cte
                        changed = True
                if cte.right_input and cte.right_input not in result:
                    right_cte = parsed.ctes.get(cte.right_input)
                    if right_cte and right_cte.cte_type == CTEType.JOIN:
                        result[cte.right_input] = right_cte
                        changed = True

    return result


def _find_column_source_in_cte(parsed: ParsedSQL, cte: ParsedCTE, col_name: str) -> Optional[str]:
    """Find the source table for a column in a specific CTE by tracing inputs."""
    col_upper = col_name.upper()

    if cte.cte_type == CTEType.UNION:
        # Trace through first union input
        if cte.union_inputs:
            input_cte = parsed.ctes.get(cte.union_inputs[0])
            if input_cte:
                return _find_column_source_in_cte(parsed, input_cte, col_name)
    elif cte.cte_type == CTEType.FILTER:
        # Trace through filter input
        if cte.filter_input:
            input_cte = parsed.ctes.get(cte.filter_input)
            if input_cte:
                return _find_column_source_in_cte(parsed, input_cte, col_name)
    elif cte.cte_type == CTEType.JOIN:
        # Check left then right input
        if cte.left_input:
            left_cte = parsed.ctes.get(cte.left_input)
            if left_cte:
                result = _find_column_source_in_cte(parsed, left_cte, col_name)
                if result:
                    return result
        if cte.right_input:
            right_cte = parsed.ctes.get(cte.right_input)
            if right_cte:
                result = _find_column_source_in_cte(parsed, right_cte, col_name)
                if result:
                    return result
    elif cte.cte_type == CTEType.BASE_TABLE:
        # Check if this base table has the column
        for col in cte.columns:
            if col.name.upper() == col_upper or (col.alias and col.alias.upper() == col_upper):
                # ABAP-001 FIX: Don't return source for calculated columns (empty source)
                if col.source == "":
                    return None  # Calculated column - use TYPE string
                return cte.source_table

    return None


def _find_column_source(parsed: ParsedSQL, col_name: str) -> Optional[str]:
    """Find the source table for a column in the final result."""
    col_upper = col_name.upper()

    # Search through base table CTEs
    for cte_name, cte in parsed.ctes.items():
        if cte.cte_type == CTEType.BASE_TABLE and cte.source_table:
            for col in cte.columns:
                if (col.alias and col.alias.upper() == col_upper) or col.name.upper() == col_upper:
                    # ABAP-001 FIX: Don't return source for calculated columns (empty source)
                    if col.source == "":
                        return None  # Calculated column - use TYPE string
                    return cte.source_table

    return None


def _find_table_with_column(parsed: ParsedSQL, col_name: str, candidate_tables: Set[str]) -> Optional[str]:
    """ABAP-002 FIX: Find which table from candidates has a specific column.

    Args:
        parsed: Parsed SQL structure
        col_name: Column name to search for (uppercase)
        candidate_tables: Set of table names to search in

    Returns:
        Table name that has the column, or None
    """
    col_upper = col_name.upper()

    for cte_name, cte in parsed.ctes.items():
        if cte.cte_type == CTEType.BASE_TABLE and cte.source_table:
            table = cte.source_table.upper()
            if table in candidate_tables:
                # Check if this table has the column
                for col in cte.columns:
                    if col.name.upper() == col_upper or (col.alias and col.alias.upper() == col_upper):
                        # Don't return if it's a calculated column
                        if col.source != "":
                            return table

    return None


def _build_fae_dependency_map(parsed: ParsedSQL) -> Dict[str, Tuple[str, List[Tuple[str, str]]]]:
    """Build FOR ALL ENTRIES dependency map from JOIN CTEs.

    Analyzes JOIN CTEs to determine which table should be used as FOR ALL ENTRIES
    source for each base table, and which columns to use in the WHERE clause.

    Returns:
        Dict mapping table_name -> (source_table, [(target_col, source_col), ...])
        Example: {'DD03L': ('ROOSOURCE', [('tabname', 'exstruct')])}
                 means: SELECT FROM dd03l FOR ALL ENTRIES IN lt_roosource WHERE tabname = lt_roosource-exstruct
    """
    fae_map: Dict[str, Tuple[str, List[Tuple[str, str]]]] = {}

    # Build a map: CTE name -> source table name
    cte_to_table: Dict[str, str] = {}
    for cte_name, cte in parsed.ctes.items():
        if cte.cte_type == CTEType.BASE_TABLE and cte.source_table:
            cte_to_table[cte_name] = cte.source_table.upper()

    # First base table in execution order is the driving table (no FAE needed)
    driving_table = None
    for cte_name in parsed.execution_order:
        cte = parsed.ctes[cte_name]
        if cte.cte_type == CTEType.BASE_TABLE and cte.source_table:
            driving_table = cte.source_table.upper()
            break

    if not driving_table:
        return fae_map

    # Analyze JOIN CTEs to find dependencies
    # Track which tables we've resolved FAE sources for
    resolved_tables: Set[str] = {driving_table}

    # Process JOINs in execution order to build dependency chain
    for cte_name in parsed.execution_order:
        cte = parsed.ctes[cte_name]
        if cte.cte_type != CTEType.JOIN:
            continue

        # Get left and right CTEs
        left_cte = parsed.ctes.get(cte.left_input)
        right_cte = parsed.ctes.get(cte.right_input)

        if not left_cte or not right_cte:
            continue

        # Determine source tables for left and right
        left_table = None
        right_table = None

        if left_cte.cte_type == CTEType.BASE_TABLE and left_cte.source_table:
            left_table = left_cte.source_table.upper()
        elif cte.left_input in cte_to_table:
            left_table = cte_to_table[cte.left_input]

        if right_cte.cte_type == CTEType.BASE_TABLE and right_cte.source_table:
            right_table = right_cte.source_table.upper()
        elif cte.right_input in cte_to_table:
            right_table = cte_to_table[cte.right_input]

        # If right table is not yet resolved, find FAE source from left side
        if right_table and right_table not in resolved_tables:
            # Find the source table from the resolved left side
            fae_source = None
            if left_table and left_table in resolved_tables:
                fae_source = left_table
            else:
                # ABAP-002 FIX: Left side is a JOIN CTE - find table that has the join column
                # We need to trace back to find which source table provides the left join column
                if cte.join_conditions:
                    left_col = cte.join_conditions[0].left_column.upper()
                    # Find which resolved table has this column
                    fae_source = _find_table_with_column(parsed, left_col, resolved_tables)
                if not fae_source:
                    # Fallback to any resolved table (may fail)
                    for resolved in resolved_tables:
                        fae_source = resolved
                        break

            if fae_source:
                # Extract join columns: which column from right matches which from left
                join_cols: List[Tuple[str, str]] = []
                for jc in cte.join_conditions:
                    # right_column is the target (DD03L.tabname)
                    # left_column is the source (ROOSOURCE.exstruct)
                    join_cols.append((jc.right_column.upper(), jc.left_column.upper()))

                if join_cols:
                    fae_map[right_table] = (fae_source, join_cols)
                    resolved_tables.add(right_table)

        # If left table is not yet resolved (rare case), check if right side helps
        if left_table and left_table not in resolved_tables:
            if right_table and right_table in resolved_tables:
                join_cols: List[Tuple[str, str]] = []
                for jc in cte.join_conditions:
                    join_cols.append((jc.left_column.upper(), jc.right_column.upper()))

                if join_cols:
                    fae_map[left_table] = (right_table, join_cols)
                    resolved_tables.add(left_table)

    return fae_map


def _sort_base_tables_by_fae_dependency(
    parsed: ParsedSQL,
    fae_map: Dict[str, Tuple[str, List[Tuple[str, str]]]]
) -> List[str]:
    """Sort base table CTEs by FOR ALL ENTRIES dependency order.

    Ensures that tables are fetched in the correct order:
    1. Driving table first (no FAE dependency)
    2. Tables whose FAE source is already fetched
    3. Repeat until all tables are processed

    Returns:
        List of CTE names in FAE-correct order
    """
    # Get all base table CTEs with their source table names
    base_ctes: Dict[str, str] = {}  # cte_name -> table_name
    for cte_name in parsed.execution_order:
        cte = parsed.ctes[cte_name]
        if cte.cte_type == CTEType.BASE_TABLE and cte.source_table:
            base_ctes[cte_name] = cte.source_table.upper()

    # Build reverse map: table_name -> cte_name
    table_to_cte: Dict[str, str] = {v: k for k, v in base_ctes.items()}

    # Sort by dependency
    sorted_ctes: List[str] = []
    fetched_tables: Set[str] = set()

    # Keep looping until all CTEs are sorted
    remaining = set(base_ctes.keys())
    max_iterations = len(remaining) + 1

    for _ in range(max_iterations):
        if not remaining:
            break

        # Find CTEs that can be fetched (FAE source already fetched, or no FAE)
        to_add: List[str] = []
        for cte_name in list(remaining):
            table = base_ctes[cte_name]
            if table in fae_map:
                fae_source, _ = fae_map[table]
                if fae_source in fetched_tables:
                    to_add.append(cte_name)
            else:
                # No FAE dependency - this is a driving table
                to_add.append(cte_name)

        if not to_add:
            # Circular dependency or all remaining need FAE sources not yet fetched
            # Fall back to original order for remaining
            for cte_name in parsed.execution_order:
                if cte_name in remaining:
                    to_add.append(cte_name)
            sorted_ctes.extend(to_add)
            break

        for cte_name in to_add:
            sorted_ctes.append(cte_name)
            fetched_tables.add(base_ctes[cte_name])
            remaining.discard(cte_name)

    return sorted_ctes


def _gen_data_declarations(parsed: ParsedSQL, table_info: Dict[str, Dict[str, List[str]]]) -> str:
    """Generate DATA declarations."""
    lines = []

    # Internal tables for each base table
    for table in table_info:
        struct_name = f"ty_{_sanitize_name(table, 26)}".lower()
        lt_name = f"lt_{_sanitize_name(table, 26)}".lower()
        ls_name = f"ls_{_sanitize_name(table, 26)}".lower()
        lines.append(f"DATA: {lt_name} TYPE TABLE OF {struct_name},")
        lines.append(f"      {ls_name} TYPE {struct_name}.")
        lines.append("")

    # Internal tables for intermediate CTEs (UNIONs, FILTERs, complex JOINs)
    intermediate_ctes = _get_intermediate_ctes(parsed)
    for cte_name in intermediate_ctes:
        struct_name = f"ty_{_sanitize_name(cte_name, 26)}".lower()
        lt_name = f"lt_{_sanitize_name(cte_name, 26)}".lower()
        ls_name = f"ls_{_sanitize_name(cte_name, 26)}".lower()
        lines.append(f"DATA: {lt_name} TYPE TABLE OF {struct_name},")
        lines.append(f"      {ls_name} TYPE {struct_name}.")
        lines.append("")

    # Final result table
    if parsed.final_columns:
        lines.append("DATA: lt_result TYPE TABLE OF ty_result,")
        lines.append("      ls_result TYPE ty_result.")
        lines.append("")

    return "\n".join(lines)


def _gen_fetch_code(
    parsed: ParsedSQL,
    table_info: Dict[str, Dict[str, List[str]]],
    schema_mapping: Dict[str, str]
) -> str:
    """Generate ABAP SELECT statements and CTE assembly code.

    FOR ALL ENTRIES strategy (Session 16 TIME_OUT fix):
    1. Identify driving table (first base table) - fetch with business filters
    2. Chain FOR ALL ENTRIES for related tables based on JOIN dependencies
    3. Process UNION/FILTER CTEs
    4. Build final result with direct assembly

    This prevents full table scans that caused 2400s TIMEOUT dumps.
    """
    lines = []

    # Build FOR ALL ENTRIES dependency map from JOIN CTEs
    fae_map = _build_fae_dependency_map(parsed)

    # Identify driving table (first base table in execution order)
    driving_table = None
    for cte_name in parsed.execution_order:
        cte = parsed.ctes[cte_name]
        if cte.cte_type == CTEType.BASE_TABLE and cte.source_table:
            driving_table = cte.source_table.upper()
            break

    # Step 1: Fetch all base tables with FOR ALL ENTRIES pattern
    lines.append("  \" ============================================")
    lines.append("  \" Step 1: Fetch base tables with FOR ALL ENTRIES")
    lines.append("  \" (Prevents full table scans - Session 16 TIME_OUT fix)")
    lines.append("  \" ============================================")
    lines.append("")

    # Sort base tables by FAE dependency order (ensures source tables are fetched first)
    sorted_base_ctes = _sort_base_tables_by_fae_dependency(parsed, fae_map)

    for cte_name in sorted_base_ctes:
        cte = parsed.ctes[cte_name]
        if cte.cte_type == CTEType.BASE_TABLE and cte.source_table:
            table = cte.source_table.upper()
            lt_name = f"lt_{_sanitize_name(table, 26)}".lower()

            # ABAP-001: Only include real columns (not calculated) in SELECT
            cols = " ".join(c.name.upper() for c in cte.columns if c.source != "")
            lines.append(f"  \" Base table: {table} (CTE: {cte_name})")

            # Collect WHERE conditions from SQL + business filters
            where_parts: List[str] = []

            # Add SQL WHERE conditions if any
            if cte.where_conditions:
                for wc in cte.where_conditions:
                    where_parts.append(f"{wc.column.upper()} {wc.operator} {wc.value}")

            # Add business filters for known tables
            if table in BUSINESS_FILTERS:
                for bf in BUSINESS_FILTERS[table]:
                    if bf not in where_parts:  # Avoid duplicates
                        where_parts.append(bf)

            # Check if this table needs FOR ALL ENTRIES
            if table in fae_map:
                fae_source, fae_cols = fae_map[table]
                lt_source = f"lt_{_sanitize_name(fae_source, 26)}".lower()

                # FOR ALL ENTRIES requires non-empty source table
                lines.append(f"  IF {lt_source} IS NOT INITIAL.")
                lines.append(f"    SELECT {cols}")
                lines.append(f"      INTO TABLE {lt_name}")
                lines.append(f"      FROM {table.lower()} FOR ALL ENTRIES IN {lt_source}")

                # Build WHERE clause: FAE join columns + business filters
                fae_where_parts: List[str] = []
                for target_col, source_col in fae_cols:
                    fae_where_parts.append(f"{target_col.lower()} = {lt_source}-{source_col.lower()}")

                # Add business filters
                fae_where_parts.extend(where_parts)

                if fae_where_parts:
                    lines.append(f"      WHERE {fae_where_parts[0]}")
                    for wp in fae_where_parts[1:]:
                        lines.append(f"        AND {wp}")
                    lines[-1] += "."
                else:
                    lines[-1] += "."

                lines.append(f"  ENDIF.")
            else:
                # Driving table or table without FAE dependency - direct SELECT
                lines.append(f"  SELECT {cols}")
                lines.append(f"    INTO TABLE {lt_name}")
                lines.append(f"    FROM {table.lower()}")

                if where_parts:
                    lines.append(f"    WHERE {where_parts[0]}")
                    for wp in where_parts[1:]:
                        lines.append(f"      AND {wp}")
                    lines[-1] += "."
                else:
                    lines[-1] += "."

            lines.append("")
            lines.append(f"  WRITE: / 'Rows from {table}:', lines( {lt_name} ).")
            lines.append("")

    # Step 2: Sort tables for binary search (for JOINs)
    lines.append("  \" ============================================")
    lines.append("  \" Step 2: Sort tables for efficient lookup")
    lines.append("  \" ============================================")
    lines.append("")

    sort_info = _collect_sort_keys(parsed)
    for table_or_cte, keys in sort_info.items():
        lt_name = f"lt_{_sanitize_name(table_or_cte, 26)}".lower()
        sort_keys = " ".join(k.lower() for k in keys)
        lines.append(f"  SORT {lt_name} BY {sort_keys}.")

    lines.append("")

    # Step 3: Process intermediate CTEs in order
    lines.append("  \" ============================================")
    lines.append("  \" Step 3: Process intermediate CTEs")
    lines.append("  \" ============================================")
    lines.append("")

    for cte_name in parsed.execution_order:
        cte = parsed.ctes[cte_name]

        if cte.cte_type == CTEType.UNION:
            lines.append(f"  \" UNION: {cte_name}")
            union_code = _gen_union_assembly(parsed, cte_name, cte)
            lines.append(union_code)
            lines.append("")

        elif cte.cte_type == CTEType.FILTER:
            lines.append(f"  \" FILTER: {cte_name}")
            filter_code = _gen_filter_assembly(parsed, cte_name, cte)
            lines.append(filter_code)
            lines.append("")

        elif cte.cte_type == CTEType.JOIN:
            # Check if this JOIN needs an intermediate internal table
            intermediate_ctes = _get_intermediate_ctes(parsed)
            if cte_name in intermediate_ctes:
                lines.append(f"  \" JOIN: {cte_name}")
                join_code = _gen_intermediate_join(parsed, cte_name, cte)
                lines.append(join_code)
                lines.append("")

    # Step 4: Build final result
    lines.append("  \" ============================================")
    lines.append("  \" Step 4: Build final result")
    lines.append("  \" ============================================")
    lines.append("")

    final_code = _gen_final_result(parsed)
    lines.append(final_code)

    lines.append("")
    lines.append("  WRITE: / 'Result rows:', lines( lt_result ).")
    lines.append("")

    return "\n".join(lines)


def _collect_sort_keys(parsed: ParsedSQL) -> Dict[str, List[str]]:
    """Collect sort keys for all tables/CTEs that will be used in JOINs."""
    sort_keys: Dict[str, List[str]] = {}

    for cte_name in parsed.execution_order:
        cte = parsed.ctes[cte_name]
        if cte.cte_type != CTEType.JOIN:
            continue

        # The right side of a JOIN needs to be sorted for BINARY SEARCH
        right_cte = parsed.ctes.get(cte.right_input)
        if not right_cte:
            continue

        # Determine the table/CTE name to sort
        if right_cte.cte_type == CTEType.BASE_TABLE and right_cte.source_table:
            sort_target = right_cte.source_table.upper()
        else:
            sort_target = cte.right_input.upper()

        # Collect join keys for the right side
        sort_cols = []
        for jc in cte.join_conditions:
            right_col = jc.right_column.upper()
            if right_col not in sort_cols:
                sort_cols.append(right_col)

        if sort_target not in sort_keys:
            sort_keys[sort_target] = sort_cols
        else:
            for col in sort_cols:
                if col not in sort_keys[sort_target]:
                    sort_keys[sort_target].append(col)

    return sort_keys


def _gen_union_assembly(parsed: ParsedSQL, cte_name: str, cte: ParsedCTE) -> str:
    """Generate ABAP code for UNION CTE using APPEND LINES OF."""
    lines = []
    lt_target = f"lt_{_sanitize_name(cte_name, 26)}".lower()
    ls_target = f"ls_{_sanitize_name(cte_name, 26)}".lower()

    for i, input_name in enumerate(cte.union_inputs):
        input_cte = parsed.ctes.get(input_name)
        if not input_cte:
            lines.append(f"  \" Warning: UNION input {input_name} not found")
            continue

        # Determine source table name
        if input_cte.cte_type == CTEType.BASE_TABLE and input_cte.source_table:
            lt_source = f"lt_{_sanitize_name(input_cte.source_table, 26)}".lower()
            ls_source = f"ls_{_sanitize_name(input_cte.source_table, 26)}".lower()
        else:
            lt_source = f"lt_{_sanitize_name(input_name, 26)}".lower()
            ls_source = f"ls_{_sanitize_name(input_name, 26)}".lower()

        # For UNION, we need to map columns from source to target
        # since column names may differ (e.g., CHANM -> IOBJNM)
        lines.append(f"  LOOP AT {lt_source} INTO {ls_source}.")
        lines.append(f"    CLEAR {ls_target}.")

        # Map columns based on position in UNION
        for col_idx, col in enumerate(cte.columns):
            target_col = (col.alias or col.name).lower()
            # Get source column from input CTE at same position
            if input_cte.columns and col_idx < len(input_cte.columns):
                source_col = (input_cte.columns[col_idx].alias or input_cte.columns[col_idx].name).lower()
            else:
                source_col = target_col
            lines.append(f"    {ls_target}-{target_col} = {ls_source}-{source_col}.")

        lines.append(f"    APPEND {ls_target} TO {lt_target}.")
        lines.append(f"  ENDLOOP.")
        lines.append("")

    lines.append(f"  WRITE: / 'Rows in {cte_name}:', lines( {lt_target} ).")

    return "\n".join(lines)


def _gen_filter_assembly(parsed: ParsedSQL, cte_name: str, cte: ParsedCTE) -> str:
    """Generate ABAP code for FILTER CTE using LOOP...WHERE."""
    lines = []
    lt_target = f"lt_{_sanitize_name(cte_name, 26)}".lower()
    ls_target = f"ls_{_sanitize_name(cte_name, 26)}".lower()

    input_cte = parsed.ctes.get(cte.filter_input)
    if not input_cte:
        return f"  \" Error: Filter input {cte.filter_input} not found"

    # Determine source table name
    if input_cte.cte_type == CTEType.BASE_TABLE and input_cte.source_table:
        lt_source = f"lt_{_sanitize_name(input_cte.source_table, 26)}".lower()
        ls_source = f"ls_{_sanitize_name(input_cte.source_table, 26)}".lower()
    else:
        lt_source = f"lt_{_sanitize_name(cte.filter_input, 26)}".lower()
        ls_source = f"ls_{_sanitize_name(cte.filter_input, 26)}".lower()

    # Build WHERE condition for LOOP
    where_parts = []
    for wc in cte.where_conditions:
        col = wc.column.lower()
        op = wc.operator
        val = wc.value

        # Convert SQL operators to ABAP
        if op == "=":
            where_parts.append(f"{ls_source}-{col} = {val}")
        elif op in ("<>", "!="):
            where_parts.append(f"{ls_source}-{col} <> {val}")
        elif op == "IN":
            # For IN, we need special handling
            where_parts.append(f"{ls_source}-{col} IN {val}")
        elif op == "NOT IN":
            where_parts.append(f"NOT {ls_source}-{col} IN {val}")
        else:
            where_parts.append(f"{ls_source}-{col} {op} {val}")

    # Generate LOOP with inline WHERE check (more compatible than LOOP...WHERE)
    lines.append(f"  LOOP AT {lt_source} INTO {ls_source}.")

    if where_parts:
        # Use IF instead of WHERE for better compatibility
        where_condition = " AND ".join(where_parts)
        lines.append(f"    IF {where_condition}.")
        lines.append(f"      CLEAR {ls_target}.")

        for col in cte.columns:
            col_name = (col.alias or col.name).lower()
            lines.append(f"      {ls_target}-{col_name} = {ls_source}-{col_name}.")

        lines.append(f"      APPEND {ls_target} TO {lt_target}.")
        lines.append(f"    ENDIF.")
    else:
        lines.append(f"    CLEAR {ls_target}.")
        for col in cte.columns:
            col_name = (col.alias or col.name).lower()
            lines.append(f"    {ls_target}-{col_name} = {ls_source}-{col_name}.")
        lines.append(f"    APPEND {ls_target} TO {lt_target}.")

    lines.append(f"  ENDLOOP.")
    lines.append(f"  WRITE: / 'Rows in {cte_name}:', lines( {lt_target} ).")

    return "\n".join(lines)


def _gen_intermediate_join(parsed: ParsedSQL, cte_name: str, cte: ParsedCTE) -> str:
    """Generate ABAP code for JOIN that involves intermediate CTEs.

    Uses LOOP AT ... WHERE for efficient indexed lookup (O(log n) instead of O(n)).
    The table must be sorted by the join key columns for optimal performance.
    Handles 1:N JOINs correctly - returns ALL matching records.
    """
    lines = []
    lt_target = f"lt_{_sanitize_name(cte_name, 26)}".lower()
    ls_target = f"ls_{_sanitize_name(cte_name, 26)}".lower()

    left_cte = parsed.ctes.get(cte.left_input)
    right_cte = parsed.ctes.get(cte.right_input)

    if not left_cte or not right_cte:
        return f"  \" Error: JOIN inputs not found"

    # Determine left source
    if left_cte.cte_type == CTEType.BASE_TABLE and left_cte.source_table:
        lt_left = f"lt_{_sanitize_name(left_cte.source_table, 26)}".lower()
        ls_left = f"ls_{_sanitize_name(left_cte.source_table, 26)}".lower()
    else:
        lt_left = f"lt_{_sanitize_name(cte.left_input, 26)}".lower()
        ls_left = f"ls_{_sanitize_name(cte.left_input, 26)}".lower()

    # Determine right source
    if right_cte.cte_type == CTEType.BASE_TABLE and right_cte.source_table:
        lt_right = f"lt_{_sanitize_name(right_cte.source_table, 26)}".lower()
        ls_right = f"ls_{_sanitize_name(right_cte.source_table, 26)}".lower()
    else:
        lt_right = f"lt_{_sanitize_name(cte.right_input, 26)}".lower()
        ls_right = f"ls_{_sanitize_name(cte.right_input, 26)}".lower()

    # Build WHERE clause for LOOP AT (field = value format, no struct prefix on left)
    # This uses the SORT key for efficient O(log n) lookup
    where_parts = []
    for jc in cte.join_conditions:
        right_col = jc.right_column.lower()
        left_col = jc.left_column.lower()
        where_parts.append(f"{right_col} = {ls_left}-{left_col}")

    where_clause = " AND ".join(where_parts)

    # Use LOOP AT ... WHERE for efficient indexed lookup (leverages SORT)
    lines.append(f"  LOOP AT {lt_left} INTO {ls_left}.")

    if cte.join_type == "INNER":
        # INNER JOIN: Only include rows with matches
        # LOOP AT ... WHERE uses index for O(log n) lookup per iteration
        lines.append(f"    LOOP AT {lt_right} INTO {ls_right} WHERE {where_clause}.")
        lines.append(f"      CLEAR {ls_target}.")

        # Map columns to target
        for col in cte.columns:
            col_name = (col.alias or col.name).lower()
            if _cte_has_column(left_cte, col_name):
                lines.append(f"      {ls_target}-{col_name} = {ls_left}-{col_name}.")
            elif _cte_has_column(right_cte, col_name):
                lines.append(f"      {ls_target}-{col_name} = {ls_right}-{col_name}.")
            else:
                lines.append(f"      {ls_target}-{col_name} = {ls_left}-{col_name}. \" fallback")

        lines.append(f"      APPEND {ls_target} TO {lt_target}.")
        lines.append(f"    ENDLOOP.")
    else:
        # LEFT OUTER JOIN: Include all left rows, with NULLs for non-matches
        lines.append(f"    DATA: lv_found TYPE abap_bool VALUE abap_false.")
        lines.append(f"    LOOP AT {lt_right} INTO {ls_right} WHERE {where_clause}.")
        lines.append(f"      lv_found = abap_true.")
        lines.append(f"      CLEAR {ls_target}.")

        for col in cte.columns:
            col_name = (col.alias or col.name).lower()
            if _cte_has_column(left_cte, col_name):
                lines.append(f"      {ls_target}-{col_name} = {ls_left}-{col_name}.")
            elif _cte_has_column(right_cte, col_name):
                lines.append(f"      {ls_target}-{col_name} = {ls_right}-{col_name}.")
            else:
                lines.append(f"      {ls_target}-{col_name} = {ls_left}-{col_name}. \" fallback")

        lines.append(f"      APPEND {ls_target} TO {lt_target}.")
        lines.append(f"    ENDLOOP.")

        # For LEFT JOIN: add row with NULLs if no match found
        lines.append(f"    IF lv_found = abap_false.")
        lines.append(f"      CLEAR {ls_target}.")
        for col in cte.columns:
            col_name = (col.alias or col.name).lower()
            if _cte_has_column(left_cte, col_name):
                lines.append(f"      {ls_target}-{col_name} = {ls_left}-{col_name}.")
            else:
                lines.append(f"      {ls_target}-{col_name} = ''. \" NULL from right side")
        lines.append(f"      APPEND {ls_target} TO {lt_target}.")
        lines.append(f"    ENDIF.")

    lines.append(f"  ENDLOOP.")
    lines.append(f"  WRITE: / 'Rows in {cte_name}:', lines( {lt_target} ).")

    return "\n".join(lines)


def _cte_has_column(cte: ParsedCTE, col_name: str) -> bool:
    """Check if a CTE has a column with the given name."""
    col_upper = col_name.upper()
    for col in cte.columns:
        if col.name.upper() == col_upper or (col.alias and col.alias.upper() == col_upper):
            return True
    return False


def _gen_final_result(parsed: ParsedSQL) -> str:
    """Generate code to populate lt_result from final CTE.

    SESSION 17 CHANGE: Implements direct result assembly pattern.
    - For UNION/FILTER CTEs: Copy from their intermediate tables
    - For JOIN/BASE_TABLE CTEs: Build directly using nested loops and READ TABLE
    """
    lines = []

    if not parsed.final_cte:
        return "  \" Error: No final CTE found"

    final_cte = parsed.ctes.get(parsed.final_cte)
    if not final_cte:
        return f"  \" Error: Final CTE {parsed.final_cte} not found"

    # Check if final CTE has an intermediate table (UNION or FILTER)
    intermediate_ctes = _get_intermediate_ctes(parsed)

    if parsed.final_cte in intermediate_ctes or final_cte.cte_type == CTEType.BASE_TABLE:
        # Has intermediate table or is base table - simple copy
        if final_cte.cte_type == CTEType.BASE_TABLE and final_cte.source_table:
            lt_source = f"lt_{_sanitize_name(final_cte.source_table, 26)}".lower()
            ls_source = f"ls_{_sanitize_name(final_cte.source_table, 26)}".lower()
        else:
            lt_source = f"lt_{_sanitize_name(parsed.final_cte, 26)}".lower()
            ls_source = f"ls_{_sanitize_name(parsed.final_cte, 26)}".lower()

        lines.append(f"  LOOP AT {lt_source} INTO {ls_source}.")
        lines.append(f"    CLEAR ls_result.")

        for col in parsed.final_columns:
            col_lower = col.lower()
            lines.append(f"    ls_result-{col_lower} = {ls_source}-{col_lower}.")

        lines.append(f"    APPEND ls_result TO lt_result.")
        lines.append(f"  ENDLOOP.")
    else:
        # JOIN CTE without intermediate table - use direct assembly
        lines.append("  \" Direct result assembly (no intermediate join tables)")
        direct_code = _gen_direct_result_assembly(parsed, parsed.final_cte, final_cte)
        lines.append(direct_code)

    return "\n".join(lines)


def _gen_direct_result_assembly(parsed: ParsedSQL, cte_name: str, cte: ParsedCTE) -> str:
    """Generate direct result assembly code for JOIN CTEs.

    Uses READ TABLE BINARY SEARCH for 1:1 lookups and nested LOOP for 1:N.
    Builds result directly without intermediate lt_join_N tables.
    """
    lines = []

    if cte.cte_type != CTEType.JOIN:
        return f"  \" Error: Expected JOIN CTE, got {cte.cte_type}"

    # Find the driving table by tracing back through left inputs
    driving_table, join_chain = _trace_join_chain(parsed, cte_name)

    if not driving_table:
        return "  \" Error: Could not find driving table"

    # Get driving table info
    driving_cte = None
    for cte_n, cte_obj in parsed.ctes.items():
        if cte_obj.cte_type == CTEType.BASE_TABLE and cte_obj.source_table:
            if cte_obj.source_table.upper() == driving_table.upper():
                driving_cte = cte_obj
                break

    if not driving_cte:
        return f"  \" Error: Driving table CTE not found for {driving_table}"

    lt_driving = f"lt_{_sanitize_name(driving_table, 26)}".lower()
    ls_driving = f"ls_{_sanitize_name(driving_table, 26)}".lower()

    # Start with driving table loop
    lines.append(f"  LOOP AT {lt_driving} INTO {ls_driving}.")
    lines.append(f"    CLEAR ls_result.")

    # Build column mapping: which column comes from which table
    column_sources = _build_column_source_map(parsed, parsed.final_columns)

    # Assign columns from driving table
    for col in parsed.final_columns:
        col_lower = col.lower()
        source_table = column_sources.get(col.upper())
        if source_table and source_table.upper() == driving_table.upper():
            lines.append(f"    ls_result-{col_lower} = {ls_driving}-{col_lower}.")

    # Process each join in the chain
    indent = "    "
    for join_info in join_chain:
        right_table = join_info['right_table']
        join_type = join_info['join_type']
        join_conditions = join_info['conditions']

        lt_right = f"lt_{_sanitize_name(right_table, 26)}".lower()
        ls_right = f"ls_{_sanitize_name(right_table, 26)}".lower()

        # Build READ TABLE key from join conditions
        key_parts = []
        for target_col, source_col, source_table in join_conditions:
            ls_source = f"ls_{_sanitize_name(source_table, 26)}".lower()
            key_parts.append(f"{target_col.lower()} = {ls_source}-{source_col.lower()}")

        if len(key_parts) == 1:
            # Single key - use WITH KEY ... BINARY SEARCH
            lines.append(f"{indent}READ TABLE {lt_right} INTO {ls_right}")
            lines.append(f"{indent}  WITH KEY {key_parts[0]} BINARY SEARCH.")
            lines.append(f"{indent}IF sy-subrc = 0.")

            # Assign columns from this table
            for col in parsed.final_columns:
                col_lower = col.lower()
                source_table = column_sources.get(col.upper())
                if source_table and source_table.upper() == right_table.upper():
                    lines.append(f"{indent}  ls_result-{col_lower} = {ls_right}-{col_lower}.")

            if join_type == "LEFT":
                lines.append(f"{indent}ENDIF.")
            else:
                # For INNER JOIN, only append result if found
                indent = indent + "  "
        else:
            # Multiple keys - use LOOP AT ... WHERE
            where_clause = " AND ".join(key_parts)
            lines.append(f"{indent}LOOP AT {lt_right} INTO {ls_right} WHERE {where_clause}.")

            # Assign columns from this table
            for col in parsed.final_columns:
                col_lower = col.lower()
                source_table = column_sources.get(col.upper())
                if source_table and source_table.upper() == right_table.upper():
                    lines.append(f"{indent}  ls_result-{col_lower} = {ls_right}-{col_lower}.")

    # Append result
    lines.append(f"{indent}APPEND ls_result TO lt_result.")

    # Close all loops
    for join_info in reversed(join_chain):
        if len(join_info['conditions']) > 1:
            lines.append(f"{indent[:-2]}ENDLOOP.")
            indent = indent[:-2]
        elif join_info['join_type'] != "LEFT":
            indent = indent[:-2]
            lines.append(f"{indent}ENDIF.")

    lines.append(f"  ENDLOOP.")

    return "\n".join(lines)


def _trace_join_chain(parsed: ParsedSQL, cte_name: str) -> Tuple[Optional[str], List[Dict]]:
    """Trace back through JOIN chain to find driving table and all joins.

    Returns:
        (driving_table_name, [{'right_table': ..., 'join_type': ..., 'conditions': [...]}])
    """
    join_chain = []
    current_cte_name = cte_name

    while True:
        current_cte = parsed.ctes.get(current_cte_name)
        if not current_cte:
            break

        if current_cte.cte_type == CTEType.BASE_TABLE:
            # Found the driving table
            return current_cte.source_table, list(reversed(join_chain))

        if current_cte.cte_type != CTEType.JOIN:
            # Hit a UNION or FILTER - use its output as driving
            return current_cte_name, list(reversed(join_chain))

        # Get right side info
        right_cte = parsed.ctes.get(current_cte.right_input)
        if right_cte and right_cte.cte_type == CTEType.BASE_TABLE:
            right_table = right_cte.source_table
        else:
            right_table = current_cte.right_input

        # Build join conditions with source info
        conditions = []
        left_cte = parsed.ctes.get(current_cte.left_input)
        for jc in current_cte.join_conditions:
            # Find source table for left column
            if left_cte and left_cte.cte_type == CTEType.BASE_TABLE:
                source_table = left_cte.source_table
            else:
                source_table = _find_column_source(parsed, jc.left_column) or "UNKNOWN"
            conditions.append((jc.right_column, jc.left_column, source_table))

        join_chain.append({
            'right_table': right_table,
            'join_type': current_cte.join_type,
            'conditions': conditions
        })

        # Move to left input
        current_cte_name = current_cte.left_input

    return None, []


def _build_column_source_map(parsed: ParsedSQL, columns: List[str]) -> Dict[str, str]:
    """Build a map of column name -> source table name."""
    result = {}
    for col in columns:
        source = _find_column_source(parsed, col)
        if source:
            result[col.upper()] = source
    return result


def _find_base_table_for_column(ctes: Dict[str, ParsedCTE], col_name: str) -> Optional[str]:
    """Find which base table contains a given column."""
    col_upper = col_name.upper()

    for cte_name, cte in ctes.items():
        if cte.cte_type == CTEType.BASE_TABLE and cte.source_table:
            for col in cte.columns:
                if col.name.upper() == col_upper or (col.alias and col.alias.upper() == col_upper):
                    return cte.source_table

    return None


def _gen_export_code(parsed: ParsedSQL) -> str:
    """Generate CSV export code for final result."""
    lines = []

    # Header
    if parsed.final_columns:
        lines.append("  \" Generate header")
        lines.append("  IF p_head = abap_true.")
        lines.append("    CLEAR lv_line.")
        lines.append(f"    lv_line = '{parsed.final_columns[0].upper()}'.")
        for col in parsed.final_columns[1:]:
            lines.append(f"    CONCATENATE lv_line lv_sep '{col.upper()}' INTO lv_line.")
        lines.append("    APPEND lv_line TO lt_csv.")
        lines.append("  ENDIF.")
        lines.append("")

    # Data rows - export from lt_result
    lines.append("  \" Export data rows")
    lines.append("  LOOP AT lt_result INTO ls_result.")
    lines.append("    CLEAR lv_line.")

    if parsed.final_columns:
        lines.append(f"    lv_line = ls_result-{parsed.final_columns[0].lower()}.")
        for col in parsed.final_columns[1:]:
            lines.append(f"    CONCATENATE lv_line lv_sep ls_result-{col.lower()} INTO lv_line.")

    lines.append("    APPEND lv_line TO lt_csv.")
    lines.append("  ENDLOOP.")
    lines.append("")
    lines.append("  lv_count = lines( lt_csv ).")

    return "\n".join(lines)


# Public API
__all__ = [
    "parse_sql",
    "generate_pure_abap_from_sql",
    "ParsedSQL",
    "ParsedCTE",
    "CTEType",
]
