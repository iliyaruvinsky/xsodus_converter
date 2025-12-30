"""
Pure ABAP Generator

Generates native ABAP code using SELECT statements instead of EXEC SQL.
This approach works on ANY SAP system regardless of database backend.

Key features:
- Uses SAP dictionary tables directly (MARA, VBAK, etc.)
- Uses FOR ALL ENTRIES pattern for JOIN simulation
- Generates internal tables and work areas
- Produces portable ABAP code without database-specific SQL
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any

from ..domain.models import (
    Scenario,
    DataSource,
    Node,
    NodeKind,
    JoinNode,
    JoinType,
    AggregationNode,
    Expression,
    ExpressionType,
    Attribute,
    AttributeMapping,
)
from ..domain.types import DataTypeSpec


class AbapDataType(str, Enum):
    """ABAP data types."""
    CHAR = "c"
    NUMC = "n"
    INTEGER = "i"
    PACKED = "p"
    FLOAT = "f"
    DATE = "d"
    TIME = "t"
    STRING = "string"
    XSTRING = "xstring"
    RAW = "x"


@dataclass
class AbapField:
    """Represents an ABAP field/column."""
    name: str
    abap_type: str  # Full type declaration (e.g., "TYPE c LENGTH 10")
    original_name: str  # Original SQL column name
    description: Optional[str] = None


@dataclass
class AbapTableDef:
    """Represents an ABAP internal table definition."""
    name: str
    struct_name: str
    fields: List[AbapField] = field(default_factory=list)
    source_table: Optional[str] = None  # SAP dictionary table name


@dataclass
class SelectStatement:
    """Represents an ABAP SELECT statement."""
    fields: List[str]
    from_table: str
    where_conditions: List[str] = field(default_factory=list)
    for_all_entries: Optional[str] = None  # Internal table name for FAE
    into_table: str = ""
    order_by: List[str] = field(default_factory=list)


def map_sql_type_to_abap(data_type: Optional[DataTypeSpec]) -> str:
    """
    Map SQL/HANA data types to ABAP data types.

    Args:
        data_type: SQL data type specification

    Returns:
        ABAP type declaration string
    """
    if not data_type:
        return "TYPE string"

    type_name = (data_type.type_name or "").upper()
    length = data_type.length
    scale = data_type.scale

    # String types
    if type_name in ("VARCHAR", "NVARCHAR", "CHAR", "NCHAR"):
        if length and length <= 262143:  # Max CHAR length in ABAP
            return f"TYPE c LENGTH {length}"
        return "TYPE string"

    if type_name in ("CLOB", "NCLOB", "TEXT"):
        return "TYPE string"

    # Numeric types
    if type_name in ("INTEGER", "INT", "INT4", "SMALLINT", "TINYINT"):
        return "TYPE i"

    if type_name in ("BIGINT", "INT8"):
        return "TYPE int8"

    if type_name in ("DECIMAL", "NUMERIC", "DEC"):
        if length and scale:
            return f"TYPE p LENGTH {min(length, 16)} DECIMALS {scale}"
        elif length:
            return f"TYPE p LENGTH {min(length, 16)} DECIMALS 0"
        return "TYPE p LENGTH 8 DECIMALS 2"

    if type_name in ("FLOAT", "DOUBLE", "REAL"):
        return "TYPE f"

    # Date/Time types
    if type_name == "DATE":
        return "TYPE d"

    if type_name == "TIME":
        return "TYPE t"

    if type_name in ("TIMESTAMP", "DATETIME"):
        return "TYPE timestamp"

    # Binary types
    if type_name in ("VARBINARY", "BINARY", "BLOB"):
        if length:
            return f"TYPE x LENGTH {length}"
        return "TYPE xstring"

    # Boolean
    if type_name in ("BOOLEAN", "BOOL"):
        return "TYPE abap_bool"

    # Default to string
    return "TYPE string"


def sanitize_abap_name(name: str, max_length: int = 30) -> str:
    """
    Convert a name to valid ABAP identifier.

    Args:
        name: Original name
        max_length: Maximum allowed length

    Returns:
        Valid ABAP identifier
    """
    # Remove invalid characters
    clean = re.sub(r'[^a-zA-Z0-9_]', '_', name)

    # Ensure starts with letter
    if clean and not clean[0].isalpha():
        clean = 'F_' + clean

    # Truncate
    if len(clean) > max_length:
        clean = clean[:max_length]

    # Default if empty
    if not clean:
        clean = 'FIELD'

    return clean.upper()


def extract_table_name_from_schema(source: DataSource) -> str:
    """
    Extract SAP dictionary table name from data source.

    Converts schema.object patterns to dictionary table references.
    E.g., "SAPABAP1"."MARA" -> MARA
          "_SYS_BIC"."package/CV_NAME" -> (returns None, not a dictionary table)

    Args:
        source: DataSource from IR

    Returns:
        Table name or empty string if not a dictionary table
    """
    schema = source.schema_name.strip('"').upper()
    table = source.object_name.strip('"')

    # Skip calculation view references
    if schema == "_SYS_BIC" or "/" in table:
        return ""

    # Skip known non-dictionary schemas
    if schema in ("_SYS_BIC", "_SYS_REPO"):
        return ""

    # Return just the table name for dictionary tables
    return table.upper()


def analyze_scenario_tables(scenario: Scenario) -> Dict[str, AbapTableDef]:
    """
    Analyze scenario to identify dictionary tables and their structures.

    Args:
        scenario: Parsed IR scenario

    Returns:
        Dict mapping table names to their ABAP definitions
    """
    tables: Dict[str, AbapTableDef] = {}

    for source_id, source in scenario.data_sources.items():
        table_name = extract_table_name_from_schema(source)
        if not table_name:
            continue

        # Create ABAP table definition
        fields = []

        # BUG FIX: source.columns is often empty when allViewAttributes="true"
        # Instead, derive columns from node mappings that reference this source
        if source.columns:
            # Use explicit columns if available
            for col_name, attr in source.columns.items():
                abap_type = map_sql_type_to_abap(attr.data_type)
                field = AbapField(
                    name=sanitize_abap_name(col_name),
                    abap_type=abap_type,
                    original_name=col_name,
                    description=attr.description,
                )
                fields.append(field)
        else:
            # Derive columns from node mappings that use this data source
            seen_cols = set()
            for node_id, node in scenario.nodes.items():
                if source_id in node.inputs:
                    for mapping in node.mappings:
                        if mapping.expression.expression_type == ExpressionType.COLUMN:
                            col_name = mapping.expression.value.strip('"')
                            if col_name not in seen_cols:
                                seen_cols.add(col_name)
                                # Default to string type since we don't have metadata
                                field = AbapField(
                                    name=sanitize_abap_name(col_name),
                                    abap_type="TYPE string",
                                    original_name=col_name,
                                    description=None,
                                )
                                fields.append(field)

        struct_name = f"TY_{sanitize_abap_name(table_name, 26)}"
        tables[source_id] = AbapTableDef(
            name=f"LT_{sanitize_abap_name(table_name, 26)}",
            struct_name=struct_name,
            fields=fields,
            source_table=table_name,
        )

    return tables


def generate_select_for_node(
    node: Node,
    table_defs: Dict[str, AbapTableDef],
    scenario: Scenario
) -> Optional[SelectStatement]:
    """
    Generate SELECT statement for a node.

    Args:
        node: IR node (Projection, Join, etc.)
        table_defs: Dictionary of table definitions
        scenario: Parent scenario

    Returns:
        SelectStatement or None if not applicable
    """
    if node.kind == NodeKind.PROJECTION:
        return _generate_projection_select(node, table_defs, scenario)
    elif node.kind == NodeKind.JOIN and isinstance(node, JoinNode):
        return _generate_join_select(node, table_defs, scenario)
    elif node.kind == NodeKind.AGGREGATION and isinstance(node, AggregationNode):
        return _generate_aggregation_select(node, table_defs, scenario)

    return None


def _generate_projection_select(
    node: Node,
    table_defs: Dict[str, AbapTableDef],
    scenario: Scenario
) -> Optional[SelectStatement]:
    """Generate SELECT for a projection node."""
    if not node.inputs:
        return None

    # Get source table
    source_id = node.inputs[0]
    if source_id not in scenario.data_sources:
        return None

    source = scenario.data_sources[source_id]
    table_name = extract_table_name_from_schema(source)
    if not table_name:
        return None

    # Build field list from mappings
    fields = []
    for mapping in node.mappings:
        if mapping.expression.expression_type == ExpressionType.COLUMN:
            col_name = mapping.expression.value.strip('"')
            alias = sanitize_abap_name(mapping.target_name)
            if col_name.upper() != alias:
                fields.append(f"{col_name} AS {alias}")
            else:
                fields.append(col_name)

    if not fields:
        fields = ["*"]

    # Build WHERE conditions from filters
    where_conditions = []
    for pred in node.filters:
        condition = _predicate_to_abap_condition(pred)
        if condition:
            where_conditions.append(condition)

    return SelectStatement(
        fields=fields,
        from_table=table_name,
        where_conditions=where_conditions,
        into_table=f"LT_{sanitize_abap_name(table_name, 26)}",
    )


def _generate_join_select(
    node: JoinNode,
    table_defs: Dict[str, AbapTableDef],
    scenario: Scenario
) -> Optional[SelectStatement]:
    """
    Generate SELECT with FOR ALL ENTRIES for a join node.

    FOR ALL ENTRIES simulates JOINs in ABAP:
    1. First SELECT from primary table into LT_PRIMARY
    2. Then SELECT from secondary table FOR ALL ENTRIES IN LT_PRIMARY
       WHERE secondary.key = LT_PRIMARY-key
    """
    if len(node.inputs) < 2:
        return None

    # Get primary (left) and secondary (right) tables
    left_id = node.inputs[0]
    right_id = node.inputs[1]

    if right_id not in scenario.data_sources:
        return None

    right_source = scenario.data_sources[right_id]
    right_table = extract_table_name_from_schema(right_source)
    if not right_table:
        return None

    # Build field list
    fields = []
    for mapping in node.mappings:
        if mapping.expression.expression_type == ExpressionType.COLUMN:
            fields.append(mapping.expression.value.strip('"'))

    if not fields:
        fields = ["*"]

    # Build FOR ALL ENTRIES conditions from join conditions
    fae_conditions = []
    for cond in node.conditions:
        left_col = cond.left.value.strip('"')
        right_col = cond.right.value.strip('"')
        # FAE condition: secondary.col = lt_primary-col
        fae_conditions.append(f"{right_col} = LT_PRIMARY-{sanitize_abap_name(left_col)}")

    return SelectStatement(
        fields=fields,
        from_table=right_table,
        where_conditions=fae_conditions,
        for_all_entries="LT_PRIMARY",
        into_table=f"LT_{sanitize_abap_name(right_table, 26)}",
    )


def _generate_aggregation_select(
    node: AggregationNode,
    table_defs: Dict[str, AbapTableDef],
    scenario: Scenario
) -> Optional[SelectStatement]:
    """
    Generate SELECT for aggregation.

    Note: ABAP SELECT supports some aggregations directly.
    """
    if not node.inputs:
        return None

    source_id = node.inputs[0]
    if source_id not in scenario.data_sources:
        return None

    source = scenario.data_sources[source_id]
    table_name = extract_table_name_from_schema(source)
    if not table_name:
        return None

    # Build field list with GROUP BY columns and aggregations
    fields = list(node.group_by)

    for agg in node.aggregations:
        func = agg.function.upper()
        col = agg.expression.value.strip('"')
        alias = sanitize_abap_name(agg.target_name)

        if func in ("SUM", "COUNT", "MIN", "MAX", "AVG"):
            fields.append(f"{func}( {col} ) AS {alias}")
        else:
            fields.append(col)

    return SelectStatement(
        fields=fields,
        from_table=table_name,
        into_table=f"LT_{sanitize_abap_name(table_name, 26)}_AGG",
        order_by=list(node.group_by),
    )


def _predicate_to_abap_condition(pred: Any) -> str:
    """Convert a predicate to ABAP WHERE condition."""
    from ..domain.models import PredicateKind

    if pred.kind == PredicateKind.COMPARISON:
        left = pred.left.value.strip('"')
        # BUG FIX: Quote string literals in WHERE conditions
        # Check if right side is a LITERAL expression and quote it
        if pred.right:
            right_val = pred.right.value.strip('"')
            # If it's a literal (non-numeric), wrap in single quotes
            if pred.right.expression_type == ExpressionType.LITERAL:
                # Don't double-quote if already quoted
                if not (right_val.startswith("'") and right_val.endswith("'")):
                    right_val = f"'{right_val}'"
            right = right_val
        else:
            right = "''"
        op = pred.operator or "="
        return f"{left} {op} {right}"

    elif pred.kind == PredicateKind.IS_NULL:
        left = pred.left.value.strip('"')
        return f"{left} IS INITIAL"

    elif pred.kind == PredicateKind.RAW:
        return pred.left.value

    return ""


def generate_pure_abap_report(
    scenario: Scenario,
    output_fields: Optional[List[str]] = None
) -> str:
    """
    Generate a complete Pure ABAP Report from an IR Scenario.

    This creates native ABAP code without EXEC SQL blocks.

    Args:
        scenario: Parsed IR scenario
        output_fields: Optional list of fields to include in output

    Returns:
        Complete ABAP Report source code
    """
    scenario_id = sanitize_abap_name(scenario.metadata.scenario_id, 20)
    program_name = f"Z_PURE_{scenario_id}".upper()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Analyze tables
    table_defs = analyze_scenario_tables(scenario)

    # Generate SELECT statements for each node
    select_statements: List[SelectStatement] = []
    for node_id, node in scenario.nodes.items():
        stmt = generate_select_for_node(node, table_defs, scenario)
        if stmt:
            select_statements.append(stmt)

    # Generate type definitions
    type_defs = _generate_type_definitions(table_defs)

    # Generate data declarations
    data_decls = _generate_data_declarations(table_defs)

    # Generate SELECT statements code
    select_code = _generate_select_code(select_statements)

    # BUG-039 FIX: Generate CSV export code that actually exports data
    export_code = _generate_export_code(table_defs)

    # Build the complete ABAP program
    abap_code = f'''*&---------------------------------------------------------------------*
*& Report {program_name}
*&---------------------------------------------------------------------*
*& Generated by XML2SQL Converter - Pure ABAP Mode
*& Timestamp: {timestamp}
*& Source Scenario: {scenario.metadata.scenario_id}
*&
*& This program uses native ABAP SELECT statements.
*& Works on ANY SAP system regardless of database backend.
*& NO EXEC SQL - fully portable ABAP code.
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
* Text Elements (define in SE38 -> Goto -> Text Elements)
*----------------------------------------------------------------------*
* TEXT-001: Export Settings

*----------------------------------------------------------------------*
* Main Processing
*----------------------------------------------------------------------*
START-OF-SELECTION.

  WRITE: / 'Starting data retrieval...'.
  WRITE: / 'Scenario:', '{scenario.metadata.scenario_id}'.

  " Step 1: Fetch data using native ABAP SELECT
  PERFORM fetch_data.

  " Step 2: Export to CSV
  PERFORM export_csv.

  WRITE: / 'Export completed.'.
  WRITE: / 'Records:', lv_count.
  WRITE: / 'File:', p_path.

*&---------------------------------------------------------------------*
*& Form FETCH_DATA
*&---------------------------------------------------------------------*
FORM fetch_data.
{select_code}
ENDFORM.

*&---------------------------------------------------------------------*
*& Form EXPORT_CSV
*&---------------------------------------------------------------------*
FORM export_csv.
  DATA: lv_sep TYPE string.

  lv_sep = p_delim.

{export_code}

  " Export based on selection
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
      filename                = lv_fullpath
      filetype                = 'ASC'
      codepage                = '4110'
      write_field_separator   = space
    TABLES
      data_tab                = lt_csv
    EXCEPTIONS
      OTHERS                  = 99.

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


def _generate_type_definitions(table_defs: Dict[str, AbapTableDef]) -> str:
    """Generate TYPES declarations for all tables."""
    lines = []

    for source_id, table_def in table_defs.items():
        lines.append(f"TYPES: BEGIN OF {table_def.struct_name.lower()},")
        for fld in table_def.fields:
            lines.append(f"         {fld.name.lower()} {fld.abap_type},")
        lines.append(f"       END OF {table_def.struct_name.lower()}.")
        lines.append("")

    return "\n".join(lines)


def _generate_data_declarations(table_defs: Dict[str, AbapTableDef]) -> str:
    """Generate DATA declarations for internal tables."""
    lines = []

    for source_id, table_def in table_defs.items():
        lines.append(f"DATA: {table_def.name.lower()} TYPE TABLE OF {table_def.struct_name.lower()},")
        ws_name = table_def.name.lower().replace("lt_", "ls_")
        lines.append(f"      {ws_name} TYPE {table_def.struct_name.lower()}.")
        lines.append("")

    return "\n".join(lines)


def _generate_select_code(statements: List[SelectStatement]) -> str:
    """Generate ABAP SELECT statements using OLD Open SQL syntax for maximum compatibility."""
    lines = []

    for i, stmt in enumerate(statements):
        lines.append(f"  \" SELECT {i + 1}: From {stmt.from_table}")

        # BUG-038 FIX: Use consistent OLD Open SQL syntax (pre-7.40)
        # - Space-separated fields (no commas)
        # - INTO TABLE immediately after SELECT fields
        # - FROM comes after INTO TABLE
        # - No @ prefix for host variables
        # This ensures compatibility with ALL SAP releases
        fields_str = " ".join(stmt.fields)

        lines.append(f"  SELECT {fields_str}")
        lines.append(f"    INTO TABLE {stmt.into_table.lower()}")
        lines.append(f"    FROM {stmt.from_table.lower()}")

        # FOR ALL ENTRIES
        if stmt.for_all_entries:
            lines.append(f"    FOR ALL ENTRIES IN {stmt.for_all_entries.lower()}")

        # WHERE conditions - append period to last condition
        if stmt.where_conditions:
            if len(stmt.where_conditions) == 1:
                lines.append(f"    WHERE {stmt.where_conditions[0]}.")
            else:
                lines.append(f"    WHERE {stmt.where_conditions[0]}")
                for cond in stmt.where_conditions[1:-1]:
                    lines.append(f"      AND {cond}")
                # Last condition gets the period
                lines.append(f"      AND {stmt.where_conditions[-1]}.")
        else:
            # No WHERE, append period to FROM
            lines[-1] = lines[-1] + "."
        lines.append("")

        # Row count
        lines.append(f"  lv_count = lv_count + lines( {stmt.into_table.lower()} ).")
        lines.append(f"  WRITE: / 'Rows from {stmt.from_table}:', lines( {stmt.into_table.lower()} ).")
        lines.append("")

    if not statements:
        lines.append("  \" No direct dictionary table access detected.")
        lines.append("  \" This scenario may reference calculation views that cannot be")
        lines.append("  \" directly converted to pure ABAP SELECT statements.")
        lines.append("  \" Consider using the SQL-in-ABAP mode instead.")

    return "\n".join(lines)


def _generate_export_code(table_defs: Dict[str, AbapTableDef]) -> str:
    """
    BUG-039 FIX: Generate CSV export ABAP code that actually exports data.

    Creates ABAP code to:
    1. Build a header row from field names
    2. Loop through each internal table
    3. Concatenate field values with delimiter
    4. Append each row to lt_csv
    """
    lines = []

    if not table_defs:
        lines.append("  \" No tables to export")
        return "\n".join(lines)

    # Collect all field names for header
    all_field_names = []
    for source_id, table_def in table_defs.items():
        for fld in table_def.fields:
            # Include table prefix to avoid confusion in multi-table exports
            header_name = f"{table_def.source_table}_{fld.original_name}"
            all_field_names.append(header_name)

    # Generate header row
    lines.append("  \" Add header row if requested")
    lines.append("  IF p_head = abap_true.")
    lines.append("    CLEAR lv_line.")

    if all_field_names:
        # Build header using CONCATENATE
        # Split into chunks to avoid very long lines
        header_chunks = [all_field_names[i:i+10] for i in range(0, len(all_field_names), 10)]

        if len(header_chunks) == 1 and len(header_chunks[0]) <= 5:
            # Simple case: few fields, use single CONCATENATE
            field_list = "' lv_sep '".join(f"'{name}'" for name in all_field_names)
            lines.append(f"    CONCATENATE {field_list} INTO lv_line.")
        else:
            # Multiple fields: build header incrementally
            lines.append(f"    lv_line = '{all_field_names[0]}'.")
            for name in all_field_names[1:]:
                lines.append(f"    CONCATENATE lv_line lv_sep '{name}' INTO lv_line.")
    else:
        lines.append("    lv_line = 'NO_DATA'.")

    lines.append("    APPEND lv_line TO lt_csv.")
    lines.append("  ENDIF.")
    lines.append("")

    # Generate data row export for each table
    for source_id, table_def in table_defs.items():
        if not table_def.fields:
            continue

        ws_name = table_def.name.lower().replace("lt_", "ls_")

        lines.append(f"  \" Export data from {table_def.source_table}")
        lines.append(f"  LOOP AT {table_def.name.lower()} INTO {ws_name}.")
        lines.append("    CLEAR lv_line.")

        # Build CSV row using CONCATENATE
        # First field
        first_field = table_def.fields[0].name.lower()
        lines.append(f"    lv_line = {ws_name}-{first_field}.")

        # Subsequent fields
        for fld in table_def.fields[1:]:
            field_name = fld.name.lower()
            lines.append(f"    CONCATENATE lv_line lv_sep {ws_name}-{field_name} INTO lv_line.")

        lines.append("    APPEND lv_line TO lt_csv.")
        lines.append("  ENDLOOP.")
        lines.append("")

    return "\n".join(lines)


# Public API
__all__ = [
    "generate_pure_abap_report",
    "map_sql_type_to_abap",
    "sanitize_abap_name",
    "analyze_scenario_tables",
    "AbapDataType",
    "AbapField",
    "AbapTableDef",
    "SelectStatement",
]
