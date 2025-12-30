"""
ABAP Report Generator

Converts HANA SQL (CREATE VIEW statements) to ABAP Reports that:
1. Create a temporary view using native SQL
2. Fetch data from the view using cursor
3. Export to CSV file (GUI download or Application Server)

The generated program runs in SE38 and produces Unicode CSV output.
"""

import re
from typing import List, Tuple, Optional
from datetime import datetime


def extract_columns_from_sql(sql_content: str) -> List[str]:
    """
    Extract column names from the final SELECT statement in the SQL.

    For CREATE VIEW AS WITH ... SELECT, we need to find the outermost SELECT
    that defines the view columns.

    Args:
        sql_content: The generated SQL (CREATE VIEW AS ...)

    Returns:
        List of column names/aliases
    """
    columns = []

    # Find the final SELECT statement (the one that defines the view output)
    # This is typically after the last CTE definition
    # Pattern: Look for SELECT after the last "AS (" or after "CREATE VIEW ... AS"

    # First, try to find columns from the outermost SELECT after CTEs
    # The pattern is: ) SELECT ... FROM (where ) closes the last CTE)

    # Normalize whitespace for easier parsing
    sql_normalized = re.sub(r'\s+', ' ', sql_content)

    # Find the final SELECT - it's the one that comes after all CTEs
    # CTEs are: name AS ( ... ), so after the last ), we have the main SELECT

    # Strategy: Find all SELECT statements, take the last major one
    # Look for pattern: SELECT <columns> FROM

    # Find all SELECT...FROM blocks
    select_pattern = r'SELECT\s+(.*?)\s+FROM\s+'
    matches = list(re.finditer(select_pattern, sql_normalized, re.IGNORECASE | re.DOTALL))

    if not matches:
        return columns

    # Take the last SELECT (which is the main query after CTEs)
    last_select = matches[-1]
    columns_str = last_select.group(1)

    # Parse column expressions
    # Format: expr AS alias, expr AS alias, ...
    # or just: col1, col2, ...

    # Split by comma, but be careful of nested parentheses
    column_parts = _split_columns(columns_str)

    for part in column_parts:
        part = part.strip()
        if not part:
            continue

        # Check for AS alias
        as_match = re.search(r'\sAS\s+(["\w]+)\s*$', part, re.IGNORECASE)
        if as_match:
            alias = as_match.group(1).strip('"')
            columns.append(alias)
        else:
            # No alias, extract column name
            # Could be: table.column or just column
            # Take the last identifier
            identifiers = re.findall(r'["\w]+', part)
            if identifiers:
                col_name = identifiers[-1].strip('"')
                columns.append(col_name)

    return columns


def _split_columns(columns_str: str) -> List[str]:
    """
    Split column list by commas, respecting parentheses nesting.

    Args:
        columns_str: String like "col1, FUNC(a, b) AS c, col3"

    Returns:
        List of column expressions
    """
    parts = []
    current = ""
    depth = 0

    for char in columns_str:
        if char == '(':
            depth += 1
            current += char
        elif char == ')':
            depth -= 1
            current += char
        elif char == ',' and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += char

    if current.strip():
        parts.append(current.strip())

    return parts


def _sanitize_abap_identifier(name: str) -> str:
    """
    Convert a column name to a valid ABAP identifier.
    - Max 30 characters
    - Only alphanumeric and underscore
    - Must start with letter
    """
    # Remove quotes and special characters
    clean = re.sub(r'[^a-zA-Z0-9_]', '_', name)

    # Ensure starts with letter
    if clean and not clean[0].isalpha():
        clean = 'C_' + clean

    # Truncate to 30 chars
    if len(clean) > 30:
        clean = clean[:30]

    # Default if empty
    if not clean:
        clean = 'COLUMN'

    return clean.upper()


def _extract_view_name(sql_content: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract schema and view name from CREATE VIEW statement.

    Args:
        sql_content: SQL with CREATE VIEW "schema"."view_name" AS ...

    Returns:
        Tuple of (schema, view_name) or (None, None) if not found
    """
    # Pattern: CREATE VIEW "schema"."view_name" AS
    pattern = r'CREATE\s+VIEW\s+"([^"]+)"\s*\.\s*"([^"]+)"'
    match = re.search(pattern, sql_content, re.IGNORECASE)

    if match:
        return match.group(1), match.group(2)

    # Try without schema: CREATE VIEW "view_name" AS
    pattern2 = r'CREATE\s+VIEW\s+"([^"]+)"\s+AS'
    match2 = re.search(pattern2, sql_content, re.IGNORECASE)

    if match2:
        return None, match2.group(1)

    return None, None


def _extract_select_query(sql_content: str) -> str:
    """
    Extract the SELECT query (WITH clause + SELECT) from CREATE VIEW statement.

    Args:
        sql_content: SQL with CREATE VIEW "schema"."view" AS WITH ... SELECT ...

    Returns:
        The query part (WITH ... SELECT ...) without CREATE VIEW wrapper
    """
    # Find the AS keyword after CREATE VIEW and extract everything after it
    # Pattern: CREATE VIEW "schema"."name" AS <query>
    pattern = r'CREATE\s+VIEW\s+"[^"]+"\s*\.\s*"[^"]+"\s+AS\s+(.+)$'
    match = re.search(pattern, sql_content, re.IGNORECASE | re.DOTALL)

    if match:
        return match.group(1).strip()

    # Try without schema
    pattern2 = r'CREATE\s+VIEW\s+"[^"]+"\s+AS\s+(.+)$'
    match2 = re.search(pattern2, sql_content, re.IGNORECASE | re.DOTALL)

    if match2:
        return match2.group(1).strip()

    return ""


def generate_abap_report(
    sql_content: str,
    scenario_id: str,
    column_names: Optional[List[str]] = None
) -> str:
    """
    Generate a complete ABAP Report program that exports data to CSV.

    The program:
    1. Tries to create a view using the provided SQL
    2. If view creation fails (authorization), falls back to direct query execution
    3. Fetches all data using native SQL cursor
    4. Exports to CSV with headers
    5. Reports success/fallback status in final messages

    Args:
        sql_content: The generated SQL (DROP VIEW + CREATE VIEW)
        scenario_id: Scenario identifier (e.g., "DATA_SOURCES")
        column_names: Optional list of column names. If not provided, extracted from SQL.

    Returns:
        Complete ABAP Report source code
    """
    # Extract column names if not provided
    if not column_names:
        column_names = extract_columns_from_sql(sql_content)

    # Fallback if no columns found
    if not column_names:
        column_names = ["DATA"]

    # Sanitize column names for ABAP
    abap_columns = [_sanitize_abap_identifier(col) for col in column_names]

    # Ensure unique names
    seen = {}
    unique_columns = []
    for col in abap_columns:
        if col in seen:
            seen[col] += 1
            unique_columns.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 0
            unique_columns.append(col)
    abap_columns = unique_columns

    # Extract view name from SQL
    schema, view_name = _extract_view_name(sql_content)
    if not view_name:
        view_name = f"Z_TEMP_{scenario_id}"

    full_view_name = f'"{schema}"."{view_name}"' if schema else f'"{view_name}"'

    # Generate program name
    program_name = f"Z_XDS_{scenario_id}".upper()
    if len(program_name) > 30:
        program_name = program_name[:30]

    # Build the ABAP report
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Generate TYPE definition (ALL fields need comma in ABAP, including last one)
    type_fields = "\n".join([f"         {col} TYPE string," for col in abap_columns])

    # Generate FETCH INTO variables
    fetch_vars = ", ".join([f":ls_data-{col}" for col in abap_columns])

    # Generate CSV header concatenation (ABAP uses space-separated operands)
    header_parts = "' '".join(column_names)  # Original names for header

    # Generate data row concatenation
    data_concat_parts = []
    for col in abap_columns:
        data_concat_parts.append(f"ls_data-{col}")

    # Escape the SQL for ABAP string literals
    # Split SQL into manageable chunks and escape single quotes
    sql_lines = sql_content.replace("'", "''").split('\n')

    # Build SQL execution statements
    # We need to execute DROP VIEW and CREATE VIEW separately
    drop_sql = ""
    create_sql = ""

    for line in sql_content.split('\n'):
        line_stripped = line.strip()
        if line_stripped.upper().startswith('DROP VIEW'):
            drop_sql = line_stripped
        elif line_stripped.upper().startswith('CREATE VIEW') or create_sql:
            create_sql += line + '\n'

    create_sql = create_sql.strip()

    # Extract the direct query (WITH ... SELECT ...) for fallback execution
    direct_query = _extract_select_query(sql_content)

    # NOTE: In EXEC SQL blocks, SQL is passed directly to the database
    # Single quotes should NOT be escaped (escaping is only for ABAP string literals)
    create_sql_escaped = create_sql

    abap_code = f'''*&---------------------------------------------------------------------*
*& Report {program_name}
*&---------------------------------------------------------------------*
*& Generated by XML2SQL Converter
*& Timestamp: {timestamp}
*& Source: {scenario_id}
*&
*& This program exports data from a HANA Calculation View to CSV format.
*& It tries to create a view first; if that fails (authorization), it
*& falls back to direct query execution without creating a view.
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
TYPES: BEGIN OF ty_data,
{type_fields}
       END OF ty_data.

*----------------------------------------------------------------------*
* Data Declarations
*----------------------------------------------------------------------*
DATA: lt_data   TYPE TABLE OF ty_data,
      ls_data   TYPE ty_data,
      lt_csv    TYPE TABLE OF string,
      lv_line   TYPE string,
      lv_count  TYPE i,
      lv_msg    TYPE string,
      gv_view_created TYPE abap_bool VALUE abap_false,
      gv_view_error   TYPE string,
      gv_fetch_failed TYPE abap_bool VALUE abap_false,
      gv_fetch_error  TYPE string.

*----------------------------------------------------------------------*
* Text Elements (define in SE38 -> Goto -> Text Elements)
*----------------------------------------------------------------------*
* TEXT-001: Export Settings
* TEXT-002: Processing...
* TEXT-003: Records exported:
* TEXT-004: Export completed successfully
* TEXT-005: Error during export

*----------------------------------------------------------------------*
* Main Processing
*----------------------------------------------------------------------*
START-OF-SELECTION.

  WRITE: / 'Starting data export...'.
  WRITE: / 'View:', '{view_name}'.

  " Step 1: Try to create the view using native SQL
  PERFORM create_view.

  " Step 2: Fetch data (from view if created, or direct query if not)
  PERFORM fetch_data.

  " Step 3: Export to CSV (only if fetch succeeded)
  IF gv_fetch_failed = abap_false.
    PERFORM export_csv.
  ENDIF.

  " Step 4: Cleanup (optional - drop view if it was created)
  IF gv_view_created = abap_true.
    " PERFORM cleanup_view.
  ENDIF.

  " Final status messages
  WRITE: / ''.
  WRITE: / '========================================'.
  IF gv_fetch_failed = abap_true.
    " FAILURE - couldn't fetch data at all
    WRITE: / 'FAILED: Could not fetch data.'.
    WRITE: / ''.
    IF gv_view_created = abap_false.
      WRITE: / 'Step 1 FAILED: View creation'.
      WRITE: / '  Error:', gv_view_error.
    ELSE.
      WRITE: / 'Step 1 OK: View created'.
    ENDIF.
    WRITE: / 'Step 2 FAILED: Data fetch'.
    WRITE: / '  Error:', gv_fetch_error.
    WRITE: / ''.
    WRITE: / 'RESOLUTION: The ABAP database user lacks SELECT'.
    WRITE: / 'privilege on the referenced Calculation View.'.
    WRITE: / 'Contact your HANA admin to grant SELECT on:'.
    WRITE: / '  "_SYS_BIC".ASSESSMENT_REPORT'.
  ELSEIF gv_view_created = abap_true.
    WRITE: / 'SUCCESS: View created and data exported.'.
    WRITE: / 'Records:', lv_count.
    WRITE: / 'File:', p_path.
  ELSE.
    WRITE: / 'SUCCESS: Data exported (direct query mode).'.
    WRITE: / 'NOTE: View creation failed - used direct query instead.'.
    WRITE: / 'Records:', lv_count.
    WRITE: / 'File:', p_path.
  ENDIF.
  WRITE: / '========================================'.

*&---------------------------------------------------------------------*
*& Form CREATE_VIEW
*&---------------------------------------------------------------------*
FORM create_view.
  DATA: lv_sql TYPE string,
        lx_error TYPE REF TO cx_sy_native_sql_error,
        lv_error_text TYPE string.

  " Drop existing view (ignore errors if view doesn't exist)
  TRY.
      EXEC SQL.
        DROP VIEW {full_view_name} CASCADE
      ENDEXEC.
      WRITE: / 'Existing view dropped.'.
    CATCH cx_sy_native_sql_error INTO lx_error.
      " View doesn't exist - this is OK, continue
      WRITE: / 'No existing view to drop (OK).'.
  ENDTRY.

  " Try to create the view with the converted SQL
  TRY.
      EXEC SQL.
        {create_sql_escaped}
      ENDEXEC.
      gv_view_created = abap_true.
      WRITE: / 'View created successfully.'.
    CATCH cx_sy_native_sql_error INTO lx_error.
      lv_error_text = lx_error->get_text( ).
      gv_view_error = lv_error_text.
      WRITE: / 'View creation failed:', lv_error_text.
      WRITE: / 'Falling back to direct query execution...'.
      " DO NOT STOP - continue with direct query execution
  ENDTRY.

ENDFORM.

*&---------------------------------------------------------------------*
*& Form FETCH_DATA
*&---------------------------------------------------------------------*
FORM fetch_data.
  DATA: lx_error TYPE REF TO cx_sy_native_sql_error,
        lv_error_text TYPE string.

  WRITE: / 'Fetching data...'.

  TRY.
      IF gv_view_created = abap_true.
        " View was created successfully - use it
        WRITE: / 'Using view:', '{full_view_name}'.
        EXEC SQL.
          OPEN dbcur FOR
            SELECT * FROM {full_view_name}
        ENDEXEC.
      ELSE.
        " View creation failed - execute query directly
        WRITE: / 'Using direct query execution (no view).'.
        EXEC SQL.
          OPEN dbcur FOR
            {direct_query}
        ENDEXEC.
      ENDIF.
    CATCH cx_sy_native_sql_error INTO lx_error.
      lv_error_text = lx_error->get_text( ).
      gv_fetch_error = lv_error_text.
      gv_fetch_failed = abap_true.
      WRITE: / 'Data fetch failed:', lv_error_text.
      EXIT. " Exit the form, don't try to fetch rows
  ENDTRY.

  IF gv_fetch_failed = abap_true.
    EXIT. " Don't continue if fetch failed
  ENDIF.

  IF sy-subrc <> 0.
    WRITE: / 'Error opening cursor. RC:', sy-subrc.
    gv_fetch_failed = abap_true.
    gv_fetch_error = 'Cursor open failed'.
    EXIT.
  ENDIF.

  " Fetch all rows
  DO.
    CLEAR ls_data.

    EXEC SQL.
      FETCH NEXT dbcur INTO {fetch_vars}
    ENDEXEC.

    IF sy-subrc <> 0.
      EXIT. " No more rows
    ENDIF.

    APPEND ls_data TO lt_data.
    lv_count = lv_count + 1.

    " Progress indicator every 10000 rows
    IF lv_count MOD 10000 = 0.
      WRITE: / 'Rows fetched:', lv_count.
    ENDIF.
  ENDDO.

  " Close cursor
  EXEC SQL.
    CLOSE dbcur
  ENDEXEC.

  WRITE: / 'Total rows fetched:', lv_count.

ENDFORM.

*&---------------------------------------------------------------------*
*& Form EXPORT_CSV
*&---------------------------------------------------------------------*
FORM export_csv.
  DATA: lv_sep TYPE string.

  lv_sep = p_delim.

  " Add header row if requested
  IF p_head = abap_true.
    CLEAR lv_line.
    CONCATENATE
      '{header_parts}'
      INTO lv_line SEPARATED BY lv_sep.
    APPEND lv_line TO lt_csv.
  ENDIF.

  " Add data rows
  LOOP AT lt_data INTO ls_data.
    CLEAR lv_line.
'''

    # Generate the CONCATENATE statement for data rows
    concat_fields = "\n      ".join([f"ls_data-{col}" for col in abap_columns])

    abap_code += f'''    CONCATENATE
      {concat_fields}
      INTO lv_line SEPARATED BY lv_sep.
    APPEND lv_line TO lt_csv.
  ENDLOOP.

  " Export based on selection
  IF p_gui = abap_true.
    " GUI Download (to user's PC)
    PERFORM download_gui.
  ELSE.
    " Application Server (AL11)
    PERFORM download_server.
  ENDIF.

ENDFORM.

*&---------------------------------------------------------------------*
*& Form DOWNLOAD_GUI
*&---------------------------------------------------------------------*
FORM download_gui.
  DATA: lv_filename TYPE string,
        lv_path     TYPE string,
        lv_fullpath TYPE string.

  lv_fullpath = p_path.

  CALL FUNCTION 'GUI_DOWNLOAD'
    EXPORTING
      filename                = lv_fullpath
      filetype                = 'ASC'
      codepage                = '4110'  " UTF-8
      write_field_separator   = space
    TABLES
      data_tab                = lt_csv
    EXCEPTIONS
      file_write_error        = 1
      no_batch                = 2
      gui_refuse_filetransfer = 3
      invalid_type            = 4
      no_authority            = 5
      unknown_error           = 6
      header_not_allowed      = 7
      separator_not_allowed   = 8
      filesize_not_allowed    = 9
      header_too_long         = 10
      dp_error_create         = 11
      dp_error_send           = 12
      dp_error_write          = 13
      unknown_dp_error        = 14
      access_denied           = 15
      dp_out_of_memory        = 16
      disk_full               = 17
      dp_timeout              = 18
      file_not_found          = 19
      dataprovider_exception  = 20
      control_flush_error     = 21
      OTHERS                  = 22.

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
    WRITE: / 'Error opening file on server:', lv_filename.
    WRITE: / 'RC:', sy-subrc.
    RETURN.
  ENDIF.

  LOOP AT lt_csv INTO lv_line.
    TRANSFER lv_line TO lv_filename.
  ENDLOOP.

  CLOSE DATASET lv_filename.

  WRITE: / 'File saved to application server:', lv_filename.

ENDFORM.

*&---------------------------------------------------------------------*
*& Form CLEANUP_VIEW
*&---------------------------------------------------------------------*
FORM cleanup_view.
  " Optional: Drop the temporary view after export
  EXEC SQL.
    DROP VIEW {full_view_name} CASCADE
  ENDEXEC.

  WRITE: / 'View dropped.'.

ENDFORM.
'''

    return abap_code


def generate_abap_simple(
    sql_content: str,
    scenario_id: str
) -> str:
    """
    Generate a simpler ABAP program that just executes the SELECT
    without creating a view first. Used when view already exists.

    Args:
        sql_content: SQL SELECT statement
        scenario_id: Scenario identifier

    Returns:
        ABAP Report source code
    """
    # This is a fallback for simpler cases
    return generate_abap_report(sql_content, scenario_id)
