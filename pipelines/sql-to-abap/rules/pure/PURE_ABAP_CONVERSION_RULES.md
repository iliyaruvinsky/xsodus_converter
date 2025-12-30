# Pure ABAP Conversion Rules

## Overview

This document defines the transformation rules for converting SQL (with CTE structure) to Pure ABAP code.

**Key Principle**: Pure ABAP mode uses native SELECT statements and FOR ALL ENTRIES pattern instead of EXEC SQL, making the generated code portable across any SAP system (HANA, Oracle, SQL Server, MaxDB, etc.).

---

## Pipeline Flow

```
XML (Calculation View) → SQL (with CTEs) → Pure ABAP
```

The SQL intermediate representation provides:
1. Explicit JOIN conditions
2. Explicit WHERE clauses
3. Linear, clear data flow

---

## CTE Type Mappings

### 1. BASE_TABLE CTE → Direct SELECT

**SQL Pattern:**
```sql
cte_name AS (
  SELECT col1, col2 FROM schema.table WHERE condition
)
```

**ABAP Transformation:**
```abap
DATA: lt_cte_name TYPE TABLE OF ty_cte_name.

SELECT col1 col2
  INTO TABLE lt_cte_name
  FROM table
  WHERE condition.
```

**Rules:**
- Schema prefix is stripped (SAP manages schema)
- Business filters applied for BW metadata tables (see BUSINESS_FILTERS)
- Column aliases become structure field names

---

### 2. JOIN CTE → FOR ALL ENTRIES

**SQL Pattern:**
```sql
join_cte AS (
  SELECT a.col1, b.col2
  FROM left_cte a
  INNER JOIN right_cte b ON a.key = b.key
)
```

**ABAP Transformation:**
```abap
* Step 1: Read left side
DATA: lt_left_keys TYPE TABLE OF ty_left_keys.
SELECT DISTINCT key INTO TABLE lt_left_keys FROM lt_left_cte.

* Step 2: FOR ALL ENTRIES select from right
IF lt_left_keys IS NOT INITIAL.
  SELECT col1 col2
    INTO TABLE lt_join_cte
    FROM right_table
    FOR ALL ENTRIES IN lt_left_keys
    WHERE key = lt_left_keys-key.
ENDIF.
```

**Rules:**
- LEFT side provides keys for FOR ALL ENTRIES
- RIGHT side is queried using FOR ALL ENTRIES
- Always check `IS NOT INITIAL` before FOR ALL ENTRIES
- Use DISTINCT for key extraction to avoid duplicates

---

### 3. UNION CTE → APPEND

**SQL Pattern:**
```sql
union_cte AS (
  SELECT col1, col2 FROM cte_a
  UNION ALL
  SELECT col1, col2 FROM cte_b
)
```

**ABAP Transformation:**
```abap
DATA: lt_union_cte TYPE TABLE OF ty_union.

APPEND LINES OF lt_cte_a TO lt_union_cte.
APPEND LINES OF lt_cte_b TO lt_union_cte.
```

**Rules:**
- UNION ALL → direct APPEND
- UNION (distinct) → APPEND + DELETE ADJACENT DUPLICATES
- Column structures must be compatible

---

### 4. FILTER CTE → LOOP with WHERE

**SQL Pattern:**
```sql
filter_cte AS (
  SELECT * FROM source_cte WHERE condition
)
```

**ABAP Transformation:**
```abap
LOOP AT lt_source_cte INTO ls_source WHERE condition.
  APPEND ls_source TO lt_filter_cte.
ENDLOOP.
```

**Alternative (inline):**
```abap
lt_filter_cte = FILTER #( lt_source_cte WHERE condition ).
```

---

## Business Filters

These filters are automatically applied to BW metadata tables to prevent TIME_OUT dumps:

| Table | Filter |
|-------|--------|
| ROOSOURCE | `objvers = 'A' AND type <> 'HIER'` |
| ROOSFIELD | `objvers = 'A'` |
| RSDIOBJ | `objvers = 'A'` |
| RSDIOBJT | `objvers = 'A'` |
| ROOSOURCET | `langu = 'E'` |
| DD03T | `ddlanguage = 'E'` |
| DD04T | `ddlanguage = 'E'` |
| DD03L | `fieldname NOT LIKE '.INCLUDE%' AND fieldname NOT LIKE 'INCLU-%'` |

---

## Data Type Mappings

| SQL Type | ABAP Type | Notes |
|----------|-----------|-------|
| VARCHAR | CHAR/STRING | Use CHAR for fixed length |
| INTEGER | I | 4-byte integer |
| DECIMAL | P DECIMALS | Packed decimal |
| DATE | DATS | YYYYMMDD format |
| TIMESTAMP | TIMESTAMPL | High precision |
| NVARCHAR | STRING | Unicode string |

---

## Aggregation Handling

### SQL Aggregations → COLLECT

**SQL Pattern:**
```sql
SELECT key, SUM(amount) as total FROM table GROUP BY key
```

**ABAP Transformation:**
```abap
DATA: lt_result TYPE TABLE OF ty_result,
      ls_collect TYPE ty_result.

LOOP AT lt_source INTO ls_source.
  ls_collect-key = ls_source-key.
  ls_collect-total = ls_source-amount.
  COLLECT ls_collect INTO lt_result.
ENDLOOP.
```

**Supported Functions:**
- SUM → COLLECT
- COUNT → COLLECT with counter field
- MAX/MIN → LOOP with comparison
- AVG → SUM / COUNT

---

## Output Generation

### CSV Export (GUI_DOWNLOAD)

```abap
CALL FUNCTION 'GUI_DOWNLOAD'
  EXPORTING
    filename                = lv_filename
    filetype                = 'ASC'
    write_field_separator   = 'X'
  TABLES
    data_tab                = lt_output
  EXCEPTIONS
    file_write_error        = 1.
```

### Application Server Export

```abap
OPEN DATASET lv_filename FOR OUTPUT IN TEXT MODE ENCODING UTF-8.
LOOP AT lt_output INTO ls_output.
  TRANSFER ls_output TO lv_filename.
ENDLOOP.
CLOSE DATASET lv_filename.
```

---

## Execution Order

CTEs are executed in topological order based on dependencies:

1. Parse all CTE definitions
2. Build dependency graph (which CTE references which)
3. Topological sort ensures each CTE is populated before use
4. Final SELECT uses the last CTE

---

## Limitations

1. **Complex Expressions**: Calculated columns with complex SQL functions may need manual adjustment
2. **Window Functions**: ROW_NUMBER, RANK etc. require ABAP loop-based implementation
3. **Subqueries**: Correlated subqueries need manual conversion
4. **CASE WHEN**: Converted to IF/ELSEIF in ABAP
5. **Calculation View References (CRITICAL)**: If the source XML references another CV (`_SYS_BIC.CV_NAME`), Pure ABAP cannot be generated. CVs are HANA-specific and not accessible via standard ABAP SELECT.

### CV Reference Limitation Details

**Detection**: Any CTE with `FROM "_SYS_BIC".*` indicates a CV reference.

**Example (Transformations.XML)**:
```sql
aggregation_1 AS (
  SELECT ... FROM "_SYS_BIC".ASSESSMENT_REPORT  -- CV REFERENCE!
)
```

**Impact**:
- Pure ABAP cannot SELECT from `_SYS_BIC` views
- FOR ALL ENTRIES dependency chain breaks
- FAE mapper may pick wrong source table (causes "field unknown" errors)

**Workaround**: Use SQL-in-ABAP (EXEC SQL) for XMLs with CV references.

---

## Case Sensitivity Rules

### Internal Lookup Keys
All identifiers stored in dictionaries must be lowercased for consistent lookup:

```python
# CTE keys (BUG-039 fix)
result.ctes[cte_name.lower()] = parsed_cte

# Column lookups
column_map[column_name.lower()] = info
```

### ABAP Identifiers
Use lowercase with prefix convention:
- `lt_` - Local table (internal table)
- `ls_` - Local structure (work area)
- `lv_` - Local variable
- `ty_` - Type definition

### Cross-Reference
| Bug | Issue | Rule |
|-----|-------|------|
| BUG-039 | CTE case mismatch | Lowercase all dictionary keys |
| ABAP-003 | Same as BUG-039 | Lowercase all dictionary keys |

---

## Code Location

The Pure ABAP generator code is located at:
- Main converter: `pipelines/xml-to-sql/src/xml_to_sql/abap/sql_to_abap.py`
- Pure generator: `pipelines/xml-to-sql/src/xml_to_sql/abap/pure_generator.py`
- Module init: `pipelines/xml-to-sql/src/xml_to_sql/abap/__init__.py`

---

**Last Updated**: 2025-12-15
**Version**: 1.1 (Added CV Reference Limitation, Case Sensitivity Rules)
