# HANA Conversion Rules

**Target Database**: SAP HANA (SQL Views)
**Version**: 2.4.0
**Last Updated**: 2025-11-16
**Validated**:
- CV_CNCLD_EVNTS.xml (ECC, 243L, 84ms)
- CV_INVENTORY_ORDERS.xml (BW, 220L, 34ms)
- CV_PURCHASE_ORDERS.xml (BW, ~220L, 29ms)
- CV_EQUIPMENT_STATUSES.xml (BW, 170L, 32ms)
- CV_TOP_PTHLGY.xml (BW, 2139L, in progress)

---

## Purpose

This document contains **ONLY** the transformation rules for converting HANA Calculation View XMLs to **HANA SQL** (native HANA views, not Snowflake).

**Use this when**: `database_mode: hana`

---

## Rule Execution Order

Rules applied in priority order (lower number = earlier execution):

1. **Priority 10**: Legacy function rewrites (LEFTSTR, RIGHTSTR, LEFTSTRU, RIGHTSTRU) *(BUG-044: Unicode variants)*
2. **Priority 15**: Calculated column expansion
3. **Priority 20**: Uppercase functions
4. **Priority 30**: IN operator → OR conditions
5. **Priority 38**: case() function → CASE WHEN *(BUG-046: SAP Column Engine case() to SQL CASE expression)*
6. **Priority 40**: IF → CASE WHEN
7. **Priority 45**: Empty string → NULL
8. **Priority 50**: String concatenation (+ → ||) *(BUG-042: Column Engine + becomes HANA SQL ||)*
9. **Priority 55**: UNION NULL padding *(BUG-043: ConstantAttributeMapping null="true" → SQL NULL)*
10. **Priority 60**: Subquery wrapping
11. **Priority 70**: Column qualification
12. **Priority 80**: Parameter removal

---

## 🔴 CRITICAL: CONVERSION PRINCIPLES

### PRINCIPLE #1: HANA CV Location ≠ SQL View Location (BUG-025)

**⚠️ FUNDAMENTAL ARCHITECTURAL PRINCIPLE - ALWAYS APPLIES**

**Discovery**: 2025-11-20, SESSION 8
**Related Bug**: BUG-025
**Affected Components**: DataSource references, JOIN operations, Star Join operations

**The Problem**:
When HANA Calculation Views reference OTHER calculation views, the converter was using incorrect schema references, causing "table not found" errors in _SYS_BIC catalog.

**Root Cause**:
HANA has TWO completely separate storage locations that must NEVER be confused:

1. **HANA Calculation View Storage** (Source/Content):
   - Location: `Content > Macabi_BI > Eligibility > Calculation Views`
   - This is where HANA CV definitions live in the repository
   - Format: Package hierarchy with dots: `Macabi_BI.Eligibility`

2. **SQL View Creation Location** (Target/_SYS_BIC):
   - Location: `Systems > _SYS_BIC > Views`
   - This is where our generated SQL views are created
   - Format: View name includes package path: `"_SYS_BIC"."Package.Path/ViewName"`

**The Rule**:
```
IF DataSource.type == CALCULATION_VIEW AND database_mode == HANA:
    THEN reference = "_SYS_BIC"."Package.Path/CV_NAME"
    NOT reference = schema.cv_name_lowercase
```

**Example - WRONG**:
```sql
-- Converter was generating:
INNER JOIN eligibility__cv_md_eyposper ON ...
-- Error: Could not find table/view ELIGIBILITY__CV_MD_EYPOSPER in schema _SYS_BIC
```

**Example - CORRECT**:
```sql
-- Should generate:
INNER JOIN "_SYS_BIC"."Macabi_BI.Eligibility/CV_MD_EYPOSPER" ON ...
```

**Implementation**:
```python
# In _render_from() function (renderer.py line 942):
if ctx.database_mode == DatabaseMode.HANA and ds.source_type == DataSourceType.CALCULATION_VIEW:
    from ..package_mapper import get_package
    cv_name = ds.object_name
    package = get_package(cv_name)
    if package:
        view_name_with_package = f"{package}/{cv_name}"
        return f'"_SYS_BIC".{_quote_identifier(view_name_with_package)}'
```

**Why This Works in Other Cases**:
- Base table references (SAPABAP1 schema): Use `SAPABAP1.table_name` - different schema entirely
- CTE references: Use CTE aliases, not DataSource objects
- Only CALCULATION_VIEW DataSource references in HANA mode need special handling

**Visual Evidence**:
Screenshot from HANA Studio shows clear separation:
- Left panel: `_SYS_BIC > Views` (where SQL views live)
- Bottom panel: `Content > Macabi_BI > Eligibility` (where HANA CVs live)

**Files Modified**:
- `xml2sql/src/xml_to_sql/sql/renderer.py`: Lines 942-970 (_render_from function)
- Added import: `DataSourceType`

**Testing**:
- CV_ELIG_TRANS_01.xml: References CV_MD_EYPOSPER (BUG-025 discovered here)
- All future XMLs with CV-to-CV references

---

### PRINCIPLE #2: Parameter Substitution Cleanup (BUG-026)

**⚠️ MANDATORY CLEANUP AFTER PARAMETER SUBSTITUTION**

**Discovery**: 2025-11-22, SESSION 7
**Related Bug**: BUG-026
**Affected Components**: WHERE clauses with HANA input parameters

**The Problem**:
When HANA calculation view parameters (`$IP_PARAM$`) are substituted with empty strings, the resulting SQL contains malformed WHERE clauses that cause syntax errors.

**Root Cause**:
Parameter placeholders in XML are designed to work with HANA's parameter framework. When converted to static SQL, they must be removed cleanly, but simple string replacement creates invalid patterns.

**Example Malformed Patterns**:
```sql
-- After parameter substitution:
"CALMONTH" IN  = '000000'      -- Orphaned IN keyword
( = '00000000')                 -- Missing left operand
( '''' = '')                    -- Escaped empty string comparison
WHERE (("CALMONTH" = '000000')  -- Unbalanced parentheses
"COLUMN" IN ('') or             -- Empty IN list
WHERE (())                      -- Completely empty WHERE
```

**The Rule**:
```
AFTER parameter substitution with empty strings:
  MUST apply 12 comprehensive cleanup patterns
  MUST balance parentheses
  MUST remove malformed operators and comparisons
  MUST verify WHERE clause is syntactically valid
```

**Implementation - 12 Cleanup Patterns**:
```python
# In _cleanup_hana_parameter_conditions() function (renderer.py lines 1383-1491):

# Pattern 1: Remove orphaned IN keyword
"CALMONTH" IN  = '000000' → "CALMONTH" = '000000'

# Pattern 2: Remove TO_DATE/DATE comparisons with NULL
TO_DATE(column) >= NULL → (removed)

# Pattern 3: Clean orphaned OR/AND before closing paren
(condition OR ) → (condition)

# Pattern 4: Clean double opening parens with operators
(( OR condition → (condition

# Pattern 5: Clean orphaned AND/OR after opening paren
( AND condition → (condition

# Pattern 6: Remove malformed comparisons with missing left operand
( = '00000000') → (removed)

# Pattern 7: Remove empty parentheses with just operators
( AND ) → (removed)

# Pattern 8: Remove empty string comparisons (4-quote patterns)
( '''' = '') → (removed)

# Pattern 9: Remove "COLUMN" IN ('') patterns
"COLUMN" IN ('') or → (removed)

# Pattern 10: Remove empty WHERE with nested parentheses
WHERE (()) → (removed)

# Pattern 11: Remove empty WHERE clauses
WHERE () → (removed)

# Pattern 12: Balance parentheses
WHERE ((condition) → WHERE ((condition))
```

**Files Modified**:
- `xml2sql/src/xml_to_sql/sql/renderer.py`: Lines 1383-1491

**Validation**:
- CV_UPRT_PTLG.xml ✅ VALIDATED (27ms execution)
- CV_ELIG_TRANS_01.xml (awaiting validation)

---

### PRINCIPLE #3: CTE Topological Sort Ordering (BUG-028)

**⚠️ CRITICAL: CTE DEPENDENCY ORDER MUST BE CORRECT**

**Discovery**: 2025-11-22, SESSION 7
**Related Bug**: BUG-028
**Affected Components**: All multi-node calculation views

**The Problem**:
CTEs were generated in wrong order, causing "table not found" errors when a CTE referenced another CTE that was defined later in the SQL.

**Root Cause**:
The topological sort function used incorrect ID normalization. Input IDs like `#/0/prj_visits` were only stripped of "#" leaving `/0/prj_visits`, which didn't match node ID `prj_visits`, breaking dependency tracking.

**Example - WRONG Order**:
```sql
WITH
join_1 AS (
  SELECT ...
  FROM prj_visits  -- ERROR: prj_visits not defined yet!
  LEFT OUTER JOIN prj_treatments ON ...
),
prj_visits AS (    -- Defined AFTER it's referenced
  SELECT ...
),
```

**Example - CORRECT Order**:
```sql
WITH
prj_visits AS (    -- Defined FIRST
  SELECT ...
),
prj_treatments AS (
  SELECT ...
),
join_1 AS (        -- References previous CTEs
  SELECT ...
  FROM prj_visits  -- Now valid!
  LEFT OUTER JOIN prj_treatments ON ...
)
```

**The Rule**:
```
FOR each CTE that references another CTE:
  Referenced CTE MUST appear BEFORE referencing CTE in WITH clause

Input ID normalization:
  "#/0/prj_visits" → "prj_visits"
  "#//prj_visits"  → "prj_visits"
  "#/prj_visits"   → "prj_visits"
  All must match node ID for dependency tracking
```

**Implementation**:
```python
# In _topological_sort() function (renderer.py lines 298-313):
from ..parser.scenario_parser import _clean_ref
import re

for input_id in node.inputs:
    # Use _clean_ref() to remove "#" and normalize slashes
    cleaned_input = _clean_ref(input_id)
    # Remove digit+slash prefixes like "0/", "1/"
    cleaned_input = re.sub(r'^\d+/', '', cleaned_input)

    if cleaned_input in all_ids:
        graph[cleaned_input].append(node_id)
        in_degree[node_id] += 1
```

**Files Modified**:
- `xml2sql/src/xml_to_sql/sql/renderer.py`: Lines 298-313

**Validation**:
- CV_ELIG_TRANS_01.xml (awaiting validation - had join_1 before prj_visits)

---

### PRINCIPLE #4: Column Qualification in JOIN Contexts (BUG-027)

**⚠️ MANDATORY: QUALIFY COLUMN NAMES IN MULTI-TABLE CONTEXTS**

**Discovery**: 2025-11-22, SESSION 7
**Related Bug**: BUG-027
**Affected Components**: JOIN nodes with calculated columns

**The Problem**:
Calculated columns in JOIN nodes that reference simple column names were not qualified with table aliases, causing "column ambiguously defined" errors when both JOIN inputs had columns with the same name.

**Root Cause**:
RAW expression types in `_render_expression()` function bypassed table alias qualification logic. Only COLUMN expression types were qualified, but calculated columns use RAW expressions.

**Example - WRONG**:
```sql
join_1 AS (
  SELECT
      prj_visits.CALDAY AS CALDAY,
      ...,
      "CALDAY" AS CC_CALDAY  -- AMBIGUOUS! Which table's CALDAY?
  FROM prj_visits
  LEFT OUTER JOIN prj_treatments ON ...  -- Both have CALDAY column
)
```

**Example - CORRECT**:
```sql
join_1 AS (
  SELECT
      prj_visits.CALDAY AS CALDAY,
      ...,
      prj_visits."CALDAY" AS CC_CALDAY  -- Qualified with table alias
  FROM prj_visits
  LEFT OUTER JOIN prj_treatments ON ...
)
```

**The Rule**:
```
IN multi-table contexts (JOIN, UNION, etc.):
  IF expression is RAW type
  AND expression is simple column name (no functions)
  AND table_alias is provided
  THEN qualify column with table_alias
```

**Implementation**:
```python
# In _render_expression() function (renderer.py lines 996-1007):
if expr.expression_type == ExpressionType.RAW:
    translated = translate_raw_formula(expr.value, ctx)
    if translated != expr.value:
        return translated
    result = _substitute_placeholders(expr.value, ctx)

    # BUG-027: Qualify bare column names when table_alias provided
    if table_alias and result.strip('"').isidentifier() and not '(' in result:
        # Simple column name (no function calls) - qualify it
        return f"{table_alias}.{result}"
    return result
```

**Logic**:
1. Check if `table_alias` is provided (indicates multi-table context)
2. Check if result is simple identifier (not a function call with "(")
3. If both true: qualify with `table_alias.column_name`

**Files Modified**:
- `xml2sql/src/xml_to_sql/sql/renderer.py`: Lines 996-1007

**Validation**:
- CV_ELIG_TRANS_01.xml ✅ VALIDATED (28ms execution)

---

### PRINCIPLE #5: View Name Quoting in DDL Statements (BUG-029)

**⚠️ CRITICAL: DDL IDENTIFIERS MUST BE QUOTED WHILE PRESERVING COLUMN CASE-INSENSITIVITY**

**Discovery**: 2025-11-22, SESSION 7
**Related Bug**: BUG-029
**Affected Components**: DROP VIEW, CREATE VIEW statements

**The Problem**:
View names in DROP/CREATE VIEW statements were not quoted, causing HANA [321] "invalid view name" errors. However, an aggressive fix that quoted ALL identifiers broke case-insensitive column matching.

**Root Cause - Case-Sensitivity Paradox**:
- **Quoted identifiers** (`"CV_NAME"`) are **case-sensitive** in HANA
- **Unquoted identifiers** (`CV_NAME`) are **case-insensitive** in HANA
- **View names in DDL**: MUST be quoted (HANA requirement)
- **Column names in SELECT**: SHOULD be unquoted (for case-insensitive matching)

**Example - Initial Problem**:
```sql
-- WRONG - View name not quoted
DROP VIEW "_SYS_BIC".CV_ELIG_TRANS_01 CASCADE;
-- Error: [321]: invalid view name: CV_ELIG_TRANS_01
```

**Example - Aggressive Fix (BROKE REGRESSION)**:
```sql
-- Fixed view name quoting BUT broke column matching:
SELECT
    "Rank_Column" AS RANK_COLUMN  -- Column defined with mixed case
FROM ...
WHERE "RANK_COLUMN" <= 1  -- Reference in uppercase

-- Error: [260]: invalid column name: RANK_1.RANK_COLUMN
-- Why: "Rank_Column" ≠ "RANK_COLUMN" (case-sensitive when both quoted)
```

**Example - CORRECT (Surgical Fix)**:
```sql
-- View name quoted in DDL:
DROP VIEW "_SYS_BIC"."CV_ELIG_TRANS_01" CASCADE;
CREATE VIEW "_SYS_BIC"."CV_ELIG_TRANS_01" AS

-- Column names unquoted in SELECT (case-insensitive):
SELECT
    Rank_Column AS RANK_COLUMN  -- Unquoted = case-insensitive
FROM ...
WHERE RANK_COLUMN <= 1  -- Matches despite case difference
```

**The Rule**:
```
IN DROP/CREATE VIEW statements:
  View names MUST be explicitly quoted
  BUT column names in SELECT/WHERE/JOIN should remain unquoted

Implement surgical quoting:
  ONLY quote in _generate_view_statement() for DDL
  PRESERVE _quote_identifier_part() behavior for columns
```

**Implementation**:
```python
# In _generate_view_statement() function (renderer.py lines 1594-1606):
def _generate_view_statement(view_name: str, mode: DatabaseMode, scenario: Optional[Scenario] = None) -> str:
    """Generate CREATE VIEW statement for target database with parameters if needed."""
    # BUG-029 FIX (SURGICAL): Always quote view names in DROP/CREATE VIEW statements
    # Unlike _quote_identifier() which preserves case-insensitivity for column names,
    # view names in DDL statements must be explicitly quoted to avoid HANA [321] errors
    if "." in view_name:
        # Schema-qualified name: quote each part separately
        parts = view_name.split(".")
        quoted_name = ".".join(f'"{part}"' for part in parts)
    else:
        # Simple view name: quote it
        quoted_name = f'"{view_name}"'

    return f"DROP VIEW {quoted_name} CASCADE;\nCREATE VIEW {quoted_name} AS"
```

**Key Insight**:
- Don't modify `_quote_identifier_part()` - it correctly preserves case-insensitivity for columns
- Only quote view names at DDL generation time
- This surgical approach prevents regression in existing validated XMLs

**Files Modified**:
- `xml2sql/src/xml_to_sql/sql/renderer.py`: Lines 1594-1606

**Validation**:
- ✅ CV_ELIG_TRANS_01: 28ms (BUG-029 fix)
- ✅ CV_TOP_PTHLGY: 201ms (no regression - case-insensitive matching preserved)
- ✅ All previously validated XMLs still working

**Regression Testing**:
Full regression test passed - surgical fix avoided breaking 8 previously validated XMLs.

---

### PRINCIPLE #6: CV Reference Package Path Quoting (BUG-030)

**⚠️ CRITICAL: PACKAGE PATHS CONTAIN DOTS THAT ARE NOT SCHEMA SEPARATORS**

**Discovery**: 2025-11-22, SESSION 7
**Related Bug**: BUG-030
**Affected Components**: Calculation View references in FROM/JOIN clauses

**The Problem**:
When referencing other Calculation Views, the package path was incorrectly split on "." characters, creating three-level qualification instead of two-level, causing HANA [471] "invalid data source name" errors.

**Root Cause - Dot Ambiguity**:
- **Schema separators**: `"_SYS_BIC".` uses "." to separate schema from view name
- **Package paths**: `Macabi_BI.Eligibility` uses "." as part of hierarchical package structure
- `_quote_identifier()` splits on ALL dots, treating package path dots as schema separators

**Example - WRONG (Three-Level Qualification)**:
```sql
-- Incorrect - package path split on dot:
INNER JOIN "_SYS_BIC".MACABI_BI."Eligibility/CV_MD_EYPOSPER" AS cv_md_eyposper
           ↑ schema   ↑ package ↑ view (3 parts - wrong!)

-- Error: [471]: invalid data source name: _SYS_BIC
```

**Example - CORRECT (Two-Level Qualification)**:
```sql
-- Correct - entire package path + CV name as single identifier:
INNER JOIN "_SYS_BIC"."Macabi_BI.Eligibility/CV_MD_EYPOSPER" AS cv_md_eyposper
           ↑ schema   ↑ package.path/viewname (2 parts - correct!)
```

**The Rule**:
```
FOR Calculation View references:
  Package path format: "Package.Subpackage/CV_NAME"
  DO NOT use _quote_identifier() which splits on "."
  INSTEAD directly quote entire string as single identifier

Schema qualification:
  Level 1: "_SYS_BIC" (quoted schema)
  Level 2: "Package.Path/ViewName" (quoted as SINGLE identifier)
  NOT: "_SYS_BIC".Package."Path/ViewName" (three levels - wrong!)
```

**Why This Breaks**:
```python
# WRONG approach:
view_name_with_package = f"{package}/{cv_name}"
# Example: "Macabi_BI.Eligibility/CV_MD_EYPOSPER"

return f'"_SYS_BIC".{_quote_identifier(view_name_with_package)}'
# _quote_identifier() splits on "." into:
#   ["Macabi_BI", "Eligibility/CV_MD_EYPOSPER"]
# Result: "_SYS_BIC".MACABI_BI."Eligibility/CV_MD_EYPOSPER"
#         (3 levels - HANA rejects this)
```

**Implementation**:
```python
# In _render_from() function (renderer.py lines 954-962):
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
```

**Package Path Examples**:
```
Macabi_BI.Eligibility/CV_MD_EYPOSPER    → "_SYS_BIC"."Macabi_BI.Eligibility/CV_MD_EYPOSPER"
EYAL.EYAL_CTL/CV_MCM_CNTRL_Q51           → "_SYS_BIC"."EYAL.EYAL_CTL/CV_MCM_CNTRL_Q51"
Macabi_BI.Pathology/CV_TOP_PTHLGY        → "_SYS_BIC"."Macabi_BI.Pathology/CV_TOP_PTHLGY"
```

**Files Modified**:
- `xml2sql/src/xml_to_sql/sql/renderer.py`: Lines 954-962

**Validation**:
- ✅ CV_ELIG_TRANS_01: 28ms (references CV_MD_EYPOSPER successfully)
- ✅ All XMLs with CV-to-CV references now working

**Impact**:
- Affects ALL XMLs that reference other Calculation Views
- Critical for CV-to-CV joins
- Common pattern in complex calculation views

---

### PRINCIPLE #7: Calculated Column Forward References in Aggregations (BUG-032)

**⚠️ MANDATORY: EXPAND CALCULATED COLUMN REFERENCES IN AGGREGATIONS**

**Discovery**: 2025-11-22, SESSION 8
**Related Bug**: BUG-032
**Affected Components**: Aggregation nodes with interdependent calculated columns

**The Problem**:
Calculated columns in aggregation nodes that reference OTHER calculated columns in the same SELECT clause cause HANA [260] "invalid column name" errors.

**Root Cause**:
When aggregations have calculated columns added in an outer SELECT (after GROUP BY in inner query), calculated columns may reference each other. HANA doesn't allow forward references to column aliases defined in the same SELECT.

**Example - WRONG**:
```sql
SELECT
    agg_inner.*,
    SUBSTRING(agg_inner."AEDAT_EKKO", 1, 6) AS MONTH,
    SUBSTRING(agg_inner."AEDAT_EKKO", 1, 4) AS YEAR,
    week(agg_inner."AEDAT_EKKO") AS WEEK,
    agg_inner."YEAR"+CASE WHEN ... END AS WEEKDAY  -- ❌ References YEAR defined above
FROM (
  SELECT ... GROUP BY ...
) AS agg_inner

-- Error: [260]: invalid column name: AGG_INNER.YEAR
-- Why: YEAR doesn't exist in agg_inner - it's defined in the SAME outer SELECT
```

**Example - CORRECT**:
```sql
SELECT
    agg_inner.*,
    SUBSTRING(agg_inner."AEDAT_EKKO", 1, 6) AS MONTH,
    SUBSTRING(agg_inner."AEDAT_EKKO", 1, 4) AS YEAR,
    week(agg_inner."AEDAT_EKKO") AS WEEK,
    (SUBSTRING(agg_inner."AEDAT_EKKO", 1, 4))+CASE WHEN ... END AS WEEKDAY  -- ✅ Expanded
FROM (
  SELECT ... GROUP BY ...
) AS agg_inner
```

**The Rule**:
```
FOR aggregation nodes with calculated columns:
  IF calculated column formula references another calculated column name
  THEN expand the reference to the source expression
  BEFORE qualifying with agg_inner prefix
```

**Implementation**:
```python
# In _render_aggregation() function (renderer.py lines 761-790):
calc_column_map = {}  # Maps calc column name → rendered expression

for calc_name, calc_attr in node.calculated_attributes.items():
    if calc_attr.expression.expression_type == ExpressionType.RAW:
        formula = calc_attr.expression.value

        # BUG-032: Expand references to previously defined calculated columns
        for prev_calc_name, prev_calc_expr in calc_column_map.items():
            pattern = rf'"{re.escape(prev_calc_name)}"'
            if re.search(pattern, formula, re.IGNORECASE):
                formula = re.sub(pattern, f'({prev_calc_expr})', formula, flags=re.IGNORECASE)

        # Then qualify remaining column refs with agg_inner
        formula = re.sub(r'(?<!\.)"([A-Z_][A-Z0-9_]*)"', r'agg_inner."\1"', formula)
        calc_expr = translate_raw_formula(formula, ctx)
    else:
        calc_expr = _render_expression(ctx, calc_attr.expression, "agg_inner")

    outer_select.append(f"{calc_expr} AS {_quote_identifier(calc_name)}")
    calc_column_map[calc_name.upper()] = calc_expr  # Store for future expansions
```

**Files Modified**:
- `src/xml_to_sql/sql/renderer.py`: Lines 761-790

**Validation**:
- ✅ CV_INVENTORY_STO: 59ms (WEEKDAY references YEAR successfully)
- ✅ All previously validated XMLs still working (no regression)

**Affected XMLs**:
- CV_INVENTORY_STO.xml (WEEKDAY references YEAR, both calculated columns)

**Related**: BUG-033 (same issue in JOIN nodes)

---

### PRINCIPLE #8: Calculated Column Forward References in JOINs (BUG-033)

**⚠️ MANDATORY: EXPAND CALCULATED COLUMN REFERENCES IN JOINS**

**Discovery**: 2025-11-22, SESSION 8
**Related Bug**: BUG-033
**Affected Components**: JOIN nodes with calculated columns referencing mapped columns

**The Problem**:
Calculated columns in JOIN nodes that reference column ALIASES (mapped columns) defined in the same SELECT clause cause HANA [260] "invalid column name" errors.

**Root Cause**:
JOIN nodes render all columns (mappings + calculated columns) in a single SELECT. When calculated column formulas reference mapped column aliases (e.g., CC_NETWR references EBELN_EKKN), HANA can't resolve the alias because it's being defined in the same SELECT statement.

**Example - WRONG**:
```sql
SELECT
    ekpo.EBELN AS EBELN,
    ...
    ekkn.NETWR AS NETWR_EKKN,
    ekkn.EBELN AS EBELN_EKKN,           -- Line 380: Define alias
    ekkn.EBELP AS EBELP_EKKN,           -- Line 381: Define alias
    CASE WHEN (("EBELN_EKKN") IS NULL) AND (("EBELP_EKKN") IS NULL)
         THEN "NETWR"
         ELSE "NETWR_EKKN" END AS CC_NETWR  -- ❌ References aliases defined above
FROM ekpo AS ekpo
LEFT OUTER JOIN ekkn AS ekkn ON ...

-- Error: [260]: invalid column name: EBELN_EKKN
-- Why: EBELN_EKKN is defined in SAME SELECT where it's referenced
```

**Example - CORRECT**:
```sql
SELECT
    ekpo.EBELN AS EBELN,
    ...
    ekkn.NETWR AS NETWR_EKKN,
    ekkn.EBELN AS EBELN_EKKN,           -- Alias kept
    ekkn.EBELP AS EBELP_EKKN,           -- Alias kept
    CASE WHEN ((ekkn.EBELN) IS NULL) AND ((ekkn.EBELP) IS NULL)
         THEN (ekpo.NETWR)
         ELSE (ekkn.NETWR) END AS CC_NETWR  -- ✅ Expanded to source expressions
FROM ekpo AS ekpo
LEFT OUTER JOIN ekkn AS ekkn ON ...
```

**The Rule**:
```
FOR JOIN nodes with calculated columns:
  IF calculated column formula references a mapped column alias
  THEN expand the alias to its source expression
  BEFORE rendering the formula
```

**Implementation**:
```python
# In _render_join() function (renderer.py lines 592-638):
column_map = {}  # Map target column name → source expression

for mapping in node.mappings:
    source_expr = _render_expression(ctx, mapping.expression, source_alias)
    columns.append(f"{source_expr} AS {_quote_identifier(mapping.target_name)}")

    # BUG-033: Store mapping for calculated column expansion
    column_map[mapping.target_name.upper()] = source_expr

# BUG-033: Expand calculated column references to mapped columns
for calc_name, calc_attr in node.calculated_attributes.items():
    if calc_attr.expression.expression_type == ExpressionType.RAW:
        formula = calc_attr.expression.value

        # Expand references to mapped columns
        for col_name, col_expr in column_map.items():
            pattern = rf'"{re.escape(col_name)}"'
            if re.search(pattern, formula, re.IGNORECASE):
                formula = re.sub(pattern, f'({col_expr})', formula, flags=re.IGNORECASE)

        calc_expr = translate_raw_formula(formula, ctx)
    else:
        calc_expr = _render_expression(ctx, calc_attr.expression, left_alias)

    columns.append(f"{calc_expr} AS {_quote_identifier(calc_name)}")
```

**Files Modified**:
- `src/xml_to_sql/sql/renderer.py`: Lines 592-638

**Validation**:
- ✅ CV_PURCHASING_YASMIN: 70ms (CC_NETWR references expanded successfully)
- ✅ All previously validated XMLs still working (no regression)

**Affected XMLs**:
- CV_PURCHASING_YASMIN.xml (CC_NETWR references EBELN_EKKN, EBELP_EKKN, NETWR_EKKN)

**Related**: BUG-032 (same issue in aggregation nodes)

**Key Insight**:
Both BUG-032 and BUG-033 follow the same pattern:
- **Root Cause**: Calculated columns reference other columns defined in same SELECT
- **HANA Rule**: Cannot use column aliases before they're defined
- **Solution**: Expand aliases to their source expressions during rendering
- **Affected Nodes**: Aggregations (BUG-032) and JOINs (BUG-033)

This fix pattern applies wherever calculated columns might reference aliases in the same SELECT context.

---

### PRINCIPLE #9: Target Schema for Cross-System Migration

**⚠️ CRITICAL: CROSS-SYSTEM XML MIGRATION REQUIRES TARGET SCHEMA CONFIGURATION**

**Discovery**: 2025-12-01, SESSION 9
**Affected Components**: All table references in SQL generation

**The Problem**:
When converting XML calculation views from one SAP system to another (e.g., SAPK5D to MBD), the source schema embedded in the XML does not match the target system's schema where tables reside.

**Root Cause**:
XML calculation views contain schema references from their source system. When migrating to a different system, these schema names are invalid on the target. For example:
- Source XML references: `SAPK5D.MARA`
- Target system has tables in: `SAPABAP1.MARA`

**Important Distinction**:
- **View schema (`view_schema`)**: Where the generated SQL view is created (always `_SYS_BIC` with package path)
- **Table schema (`target_schema`)**: Where the base tables reside on target system (e.g., `SAPABAP1`)

**Example - WRONG (Source Schema)**:
```sql
-- Using source system schema:
CREATE VIEW "_SYS_BIC"."MBD/DSO" AS
SELECT ... FROM "SAPK5D"."MARA"  -- ❌ Schema doesn't exist on target
```

**Example - CORRECT (Target Schema)**:
```sql
-- Using target system schema:
CREATE VIEW "_SYS_BIC"."MBD/DSO" AS
SELECT ... FROM "SAPABAP1"."MARA"  -- ✅ Correct target schema
```

**The Rule**:
```
IF target_schema is configured:
  ALL table schema references → target_schema
  View schema remains "_SYS_BIC" (unchanged)

Example: target_schema = "SAPABAP1"
  SAPK5D.MARA → SAPABAP1.MARA
  ABAP.EKKO  → SAPABAP1.EKKO
```

**Implementation**:
```python
# In RenderContext class (renderer.py):
class RenderContext:
    target_schema: Optional[str]  # Universal target schema for all table references

    def resolve_schema(self, schema_name: str) -> str:
        """Resolve schema name - target_schema overrides ALL schemas."""
        if self.target_schema:
            return self.target_schema
        return self.schema_overrides.get(schema_name, schema_name)
```

**UI Configuration**:
- Field: "Target SAP Instance (Table Schema)"
- Default: `SAPABAP1` (most common for SAP ECC/S4HANA)
- Purpose: Enables cross-system XML migration without manual SQL editing

**Common Use Cases**:
1. **Development to Production**: XMLs from DEV system (SAPK5D) running on PROD (SAPABAP1)
2. **System Migration**: Moving calculation views between SAP instances
3. **Multi-System**: Converting XMLs from different source systems to unified target

**Files Modified**:
- `src/xml_to_sql/sql/renderer.py`: RenderContext.target_schema, resolve_schema()
- `src/xml_to_sql/web/api/models.py`: ConversionConfig.target_schema
- `src/xml_to_sql/web/services/converter.py`: target_schema parameter
- `src/xml_to_sql/web/api/routes.py`: Passing target_schema through API
- `web_frontend/src/components/ConfigForm.jsx`: UI field for target_schema

**Validation**:
- ✅ DSO migration: SAPK5D → SAPABAP1 successful (MBD content package)
- View created in `_SYS_BIC` schema, tables referenced from `SAPABAP1`

---

## HANA-Specific Transformation Rules

### Rule 0B: case() Function to CASE WHEN (Priority 38) — BUG-046

**Rule ID**: `HANA_CASE_FUNC_TO_CASE_WHEN`
**Applies To**: All HANA versions, all Snowflake
**Category**: Conditional expressions
**Bug Reference**: BUG-046

**Why**: SAP Column Engine formulas use `case(value, match1, result1, ..., default)` — a function-call syntax for simple CASE expressions. This is NOT valid SQL in any database.

**Transformation**:
```
Source:  case(value, match1, result1, match2, result2, ..., default)
Target:  CASE value WHEN match1 THEN result1 WHEN match2 THEN result2 ... ELSE default END
```

**Example**:
```sql
-- Before (SAP Column Engine formula, invalid SQL)
case("DATATP",'CURR','000015','DATS','000008','DEC','000017','000000')

-- After (valid HANA SQL)
CASE SAPABAP1.RSDKYF.DATATP WHEN 'CURR' THEN '000015' WHEN 'DATS' THEN '000008' WHEN 'DEC' THEN '000017' ELSE '000000' END
```

**Implementation**: `function_translator.py::_convert_case_function_to_sql()`

**Validated**: INFOOBJECTS.xml (3 case() formulas converted, 51ms)

---

### Rule 1: IF() to CASE WHEN (Priority 40)

**Rule ID**: `HANA_1_0_IF_TO_CASE`  
**Applies To**: All HANA versions >=1.0  
**Category**: Conditional expressions

**Why**: HANA SQL views don't support `IF()` function in SELECT clauses.

**Transformation**:
```
Source:  IF(condition, then_value, else_value)
Target:  CASE WHEN condition THEN then_value ELSE else_value END
```

**Example**:
```sql
-- Before
IF(RIGHT("CALMONTH", 2) = '01', '2015' + '1', '')

-- After
CASE WHEN RIGHT("CALMONTH", 2) = '01' THEN '2015' + '1' ELSE NULL END
```

**Implementation**: `function_translator.py::_convert_if_to_case_for_hana()`

**Validated**: CV_CNCLD_EVNTS.xml (12 IF statements converted)

---

### Rule 2: IN Operator to OR Conditions (Priority 30)

**Rule ID**: `HANA_1_0_IN_TO_OR`  
**Applies To**: All HANA versions >=1.0  
**Category**: Operators

**Why**: HANA doesn't support `IN` operator inside conditional expressions (IF/CASE context).

**Transformation**:
```
Source:  (expression IN (val1, val2, val3))
Target:  (expression = val1 OR expression = val2 OR expression = val3)
```

**Example**:
```sql
-- Before
(RIGHT("CALMONTH", 2) IN ('01', '02', '03'))

-- After  
(RIGHT("CALMONTH", 2) = '01' OR RIGHT("CALMONTH", 2) = '02' OR RIGHT("CALMONTH", 2) = '03')
```

**Implementation**: `function_translator.py::_convert_in_to_or_for_hana()`

**Validated**: CV_CNCLD_EVNTS.xml (multiple IN operators converted)

---

### Rule 3: String Concatenation (Priority 50)

**Rule ID**: `HANA_1_0_STRING_CONCAT`  
**Applies To**: All HANA versions >=1.0  
**Category**: Operators  
**Exception**: Don't convert inside REGEXP_LIKE()

**Why**: HANA uses `+` operator for string concatenation (traditional), though `||` is also supported.

**Transformation**:
```
Source:  string1 || string2
Target:  string1 + string2
```

**Example**:
```sql
-- Before
SUBSTRING("ZZTREAT_DATE", 1, 4) || '1'

-- After
SUBSTRING("ZZTREAT_DATE", 1, 4) + '1'
```

**Implementation**: `function_translator.py::_translate_string_concat_to_hana()`  
**Protection**: Preserves `||` inside `REGEXP_LIKE()` calls

**Validated**: CV_CNCLD_EVNTS.xml

---

### Rule 4: Uppercase Functions (Priority 20)

**Rule ID**: `HANA_1_0_UPPERCASE_IF`  
**Applies To**: All HANA versions >=1.0  
**Category**: Syntax normalization

**Why**: HANA requires uppercase function names.

**Transformation**:
```
Source:  if(condition, ...)
Target:  IF(condition, ...)
```

**Implementation**: `function_translator.py::_uppercase_if_statements()`

**Also applies to**: AND keywords in cleanup phase

---

### Rule 5: LEFTSTR/RIGHTSTR (Version-Dependent)

**HANA 1.0**: `HANA_1_0_LEFTSTR_PRESERVE`  
**HANA 2.0+**: `HANA_2_0_LEFTSTR_MODERNIZE`

**For HANA 1.0**:
```
Source:  leftstr("CALMONTH", 2)
Target:  LEFTSTR("CALMONTH", 2)  (preserve legacy function)
```

**For HANA 2.0+**:
```
Source:  leftstr("CALMONTH", 2)
Target:  SUBSTRING("CALMONTH", 1, 2)  (modernize)
```

**Implementation**: `function_translator.py::_translate_for_hana()`

---

### Rule 6: Calculated Column Expansion (Priority 15)

**Rule ID**: `HANA_1_0_CALC_COL_EXPANSION`  
**Applies To**: All HANA versions >=1.0  
**Category**: Structural transformation

**Why**: SQL doesn't allow referencing column aliases in the same SELECT clause.

**Problem**:
```sql
SELECT 
    SUBSTRING("DATE", 1, 6) AS CALMONTH,
    RIGHT("CALMONTH", 2) AS QUARTER  -- ERROR: CALMONTH not defined yet
```

**Solution**:
```sql
SELECT 
    SUBSTRING("DATE", 1, 6) AS CALMONTH,
    RIGHT(SUBSTRING("DATE", 1, 6), 2) AS QUARTER  -- Expanded inline
```

**Implementation**: `renderer.py::_render_projection()` with calc_column_map

**Validated**: CV_CNCLD_EVNTS.xml (CALQUARTER references CALMONTH)

---

### Rule 7: Subquery Wrapping (Priority 60)

**Rule ID**: `HANA_1_0_SUBQUERY_WRAP`  
**Applies To**: All HANA versions >=1.0  
**Category**: Structural transformation

**Why**: Filters can't reference calculated columns in the same SELECT.

**Transformation**:
```sql
-- Before (INVALID)
SELECT 
    SUBSTRING("DATE", 1, 6) AS CALMONTH
FROM table
WHERE CALMONTH = '202401'  -- ERROR: CALMONTH not in scope

-- After (VALID)
SELECT * FROM (
  SELECT SUBSTRING("DATE", 1, 6) AS CALMONTH
  FROM table
) AS calc
WHERE calc.CALMONTH = '202401'  -- OK: calc.CALMONTH exists
```

**Implementation**: `renderer.py::_render_projection()` needs_subquery logic

**Validated**: CV_CNCLD_EVNTS.xml (3 projections wrapped)

---

### Rule 8: Column Qualification (Priority 70)

**Rule ID**: `HANA_1_0_COLUMN_QUALIFICATION`  
**Applies To**: All HANA versions >=1.0  
**Category**: Structural transformation

**Why**: When using subqueries, all column references in WHERE must be qualified.

**Transformation**:
```
Source:  WHERE ("COLUMN" = 'value')
Target:  WHERE (calc."COLUMN" = 'value')
```

**Implementation**: `renderer.py::_render_projection()` - regex qualification

**Validated**: CV_CNCLD_EVNTS.xml

---

### Rule 9: Parameter Removal (Priority 80)

**Rule ID**: `HANA_1_0_PARAMETER_REMOVAL`  
**Applies To**: All HANA versions >=1.0  
**Category**: Parameter handling

**Why**: HANA SQL views don't support runtime parameters like calculation views.

**Strategy**: Remove parameter filter clauses entirely.

**Original**:
```xml
('$$IP_TREAT_DATE$$' = '' OR "ZZTREAT_DATE" = '$$IP_TREAT_DATE$$')
```

**After substitution**:
```sql
('' = '' OR "ZZTREAT_DATE" = '')  -- Always true, pointless
```

**Final** (cleaned):
```sql
-- Entire clause removed
```

**Implementation**: 
- `function_translator.py::_substitute_placeholders()` - Replace with ''
- `renderer.py::_cleanup_hana_parameter_conditions()` - Remove clauses

**Limitations**:
- Complex DATE() patterns may leave fragments
- Nested parameters may cause orphaned parens
- See GOLDEN_COMMIT.yaml for CV_MCM_CNTRL_Q51 validation details and BUG-021 critical pattern

---

### Rule 10: NULL Fallback (Priority 45)

**Rule ID**: `HANA_1_0_NULL_FALLBACK`  
**Applies To**: All HANA versions >=1.0  
**Category**: Data type handling

**Why**: Empty string in CASE ELSE causes "invalid number" error in numeric contexts.

**Transformation**:
```
Source:  ELSE ''
Target:  ELSE NULL
```

**Implementation**: `function_translator.py::_convert_if_to_case_for_hana()`

---

### Rule 11: VIEW Creation Syntax

**Snowflake**: `CREATE OR REPLACE VIEW <view_name> AS`  
**HANA**:

```
DROP VIEW <schema>.<view_name> CASCADE;
CREATE VIEW <schema>.<view_name> AS
```

- Default schema today: `SAPABAP1` (configurable via `defaults.view_schema` or per-scenario `overrides.schema`)
- Applies to both ECC and BW conversions
- Ensures re-runs always recreate the view cleanly

**Implementation**: 
- `config`: `defaults.view_schema`, `overrides.schema`
- `cli/app.py` + `web/services/converter.py` – pass schema-qualified view name
- `renderer.py::_generate_view_statement()` – renders DROP/CREATE with schema

---

### Rule 12: Filter/GROUP BY Source Mapping (Priority 25)

**Rule ID**: `HANA_SOURCE_NAME_MAPPING`  
**Applies To**: All HANA versions, all node types  
**Category**: Column name resolution

**Why**: XML uses target/alias names but SQL needs source/actual column names for base table queries.

**Problem**: User naming convention adds table suffixes (LOEKZ→LOEKZ_EKPO) to distinguish columns from different sources.

**Transformations**:
1. **Projection Filters**: `WHERE ("LOEKZ_EKPO" = '')` → `WHERE ("LOEKZ" = '')`
2. **Aggregation GROUP BY**: `GROUP BY WAERS_EKKO` → `GROUP BY join_4.WAERS`
3. **Aggregation Specs**: `SUM(WEMNG_EKET)` → `SUM(join_4.WEMNG)`

**Implementation**: 
- `renderer.py::_render_projection()` - Lines 419-439 (filter mapping)
- `renderer.py::_render_aggregation()` - Lines 588-603 (GROUP BY), 611-631 (aggregation specs)

**Validated**: CV_INVENTORY_ORDERS.xml (220 lines, executes successfully)

---

### Rule 13: ColumnView JOIN Parsing (Priority 5)

**Rule ID**: `COLUMNVIEW_JOIN_PARSING`  
**Applies To**: ColumnView XML format (HANA 1.x era)  
**Category**: Parser enhancement

**Why**: ColumnView JOINs have different XML structure than Calculation:scenario JOINs.

**XML Pattern**:
```xml
<viewNode xsi:type="View:JoinNode" name="Join_6">
  <join leftInput="#//Join_6/Projection_6" rightInput="#//Join_6/Projection_8" joinType="inner">
    <leftElementName>EBELN_EKPO</leftElementName>
    <rightElementName>EBELN</rightElementName>
  </join>
</viewNode>
```

**Implementation**: `parser/column_view_parser.py` - Added JoinNode handler with join type/condition parsing

**Validated**: CV_INVENTORY_ORDERS join_6 renders with correct INNER JOIN syntax

---

### Rule 14: Aggregation Calculated Columns (Priority 55)

**Rule ID**: `AGGREGATION_CALC_COLS`  
**Applies To**: Aggregation nodes with calculated columns  
**Category**: Structural transformation

**Why**: Calculated columns in aggregations must be computed AFTER grouping.

**Structure**:
```sql
aggregation AS (
  SELECT
      agg_inner.*,
      SUBSTRING(agg_inner."AEDAT_EKKO", 1, 6) AS MONTH  -- After grouping
  FROM (
    SELECT dimensions, SUM(measures)
    FROM input
    GROUP BY dimensions
  ) AS agg_inner
)
```

**Implementation**: `renderer.py::_render_aggregation()` - Lines 647-673

**Validated**: MONTH, YEAR in CV_INVENTORY_ORDERS

---

### Rule 14: Legacy Type Cast Functions (STRING, INT)

**Rule ID**: `HANA_LEGACY_TYPE_CASTS`
**Applies To**: All HANA versions
**Category**: Function mapping
**Discovered**: 2025-11-16, CV_TOP_PTHLGY.xml
**Bugs Fixed**: BUG-013, BUG-017

**Why**: Legacy XML formulas use simplified type cast functions that don't exist in HANA SQL.

**Transformations**:
```
Source:  string(FIELD)       →  Target: TO_VARCHAR(FIELD)
Source:  int(FIELD)           →  Target: TO_INTEGER(FIELD)
Source:  decimal(FIELD, P, S) →  Target: TO_DECIMAL(FIELD, P, S)  (if discovered)
Source:  date(FIELD)          →  Target: TO_DATE(FIELD)
```

**Implementation**: `functions.yaml` catalog entries:
- `STRING` → `TO_VARCHAR`
- `INT` → `TO_INTEGER`

**Catalog Entry**:
```yaml
  - name: STRING
    handler: rename
    target: "TO_VARCHAR"

  - name: INT
    handler: rename
    target: "TO_INTEGER"
```

**Validated**: CV_TOP_PTHLGY.xml

---

### Rule 15: Function Name Case Sensitivity

**Rule ID**: `HANA_FUNCTION_UPPERCASE`
**Applies To**: All HANA versions
**Category**: Syntax normalization
**Discovered**: 2025-11-16, CV_TOP_PTHLGY.xml
**Bug Fixed**: BUG-016

**Why**: HANA SQL functions are case-sensitive and must be uppercase.

**Transformations**:
```
Source:  adddays(date, -3)   →  Target: ADD_DAYS(date, -3)
Source:  daysbetween(d1, d2) →  Target: DAYS_BETWEEN(d1, d2)
Source:  substring(str, 1, 4)→  Target: SUBSTRING(str, 1, 4)
```

**Implementation**: `functions.yaml` catalog entries with uppercase targets

**Catalog Entry**:
```yaml
  - name: ADDDAYS
    handler: rename
    target: "ADD_DAYS"

  - name: DAYSBETWEEN
    handler: rename
    target: "DAYS_BETWEEN"
```

**Validated**: CV_TOP_PTHLGY.xml

---

### Rule 16: TIMESTAMP Arithmetic (CRITICAL - Needs Pattern Matching)

**Rule ID**: `HANA_TIMESTAMP_ARITHMETIC`
**Applies To**: All HANA versions
**Category**: Expression pattern rewrite
**Discovered**: 2025-11-16, CV_TOP_PTHLGY.xml
**Bug Fixed**: BUG-015 (partial - manual fix only)
**Status**: ⚠️ REQUIRES PATTERN MATCHING SYSTEM

**Why**: HANA doesn't support direct arithmetic operations on TIMESTAMP types.

**Problem**:
```sql
-- INVALID in HANA
TO_DATE(CURRENT_TIMESTAMP - 365)
TO_DATE(NOW() - 270)
date(NOW() - 365)
```

**Solution**:
```sql
-- VALID in HANA
TO_DATE(ADD_DAYS(CURRENT_TIMESTAMP, -365))
TO_DATE(ADD_DAYS(CURRENT_DATE, -270))
ADD_DAYS(CURRENT_DATE, -365)
```

**Current Implementation**: Manual `sed` patch (NOT SUSTAINABLE)

**Proper Solution Needed**: Pattern matching system

**Pattern Catalog** (proposed in `PATTERN_MATCHING_DESIGN.md`):
```yaml
patterns:
  - name: "timestamp_minus_days"
    match: "CURRENT_TIMESTAMP\\s*-\\s*(\\d+)"
    hana: "ADD_DAYS(CURRENT_TIMESTAMP, -$1)"

  - name: "now_minus_days"
    match: "NOW\\(\\)\\s*-\\s*(\\d+)"
    hana: "ADD_DAYS(CURRENT_DATE, -$1)"

  - name: "date_now_minus"
    match: "date\\s*\\(\\s*NOW\\(\\)\\s*-\\s*(\\d+)\\s*\\)"
    hana: "ADD_DAYS(CURRENT_DATE, -$1)"
```

**See**: `PATTERN_MATCHING_DESIGN.md` for full implementation plan

**Validated**: CV_TOP_PTHLGY.xml (with manual patch)

---

### Rule 17: Schema Name Mapping

**Rule ID**: `HANA_SCHEMA_MAPPING`
**Applies To**: All HANA versions
**Category**: Configuration-driven transformation
**Discovered**: 2025-11-16, CV_TOP_PTHLGY.xml
**Bug Fixed**: BUG-014

**Why**: Different HANA instances use different schema naming conventions.

**Problem**: XML specifies `ABAP` schema, but actual HANA instance uses `SAPABAP1`.

**Solution**: Configuration override in `config.yaml`:
```yaml
schema_overrides:
  ABAP: "SAPABAP1"
  SAPK5D: "PRODUCTION_SCHEMA"  # Example for other mappings
```

**Implementation**: `renderer.py::render_scenario()` accepts `schema_overrides` parameter

**Common Mappings**:
- `ABAP` → `SAPABAP1` (most common)
- `SAPK5D` → customer-specific schema
- `_SYS_BIC` → preserved (calculation view catalog)

**Validated**: CV_TOP_PTHLGY.xml

---

### Rule 18: Single-Input Union Node Pass-Through (BUG-047)

**Rule ID**: `HANA_SINGLE_INPUT_UNION`
**Applies To**: All HANA versions
**Category**: Union node rendering
**Discovered**: 2026-03-03, ADSO.xml (SESSION 14)
**Bug Fixed**: BUG-047

**Why**: SAP BW uses Union nodes with a single input as a projection+rename node — not for combining multiple data sources. Prior code returned a placeholder CTE for any Union with fewer than 2 inputs, breaking this valid pattern.

**Pattern**:
```xml
<calculationView xsi:type="Calculation:UnionView" id="Union_1">
  <input emptyUnionBehavior="NO_ROW" node="#ADSO">
    <mapping ... target="INFOCUBE" source="ADSONM"/>       <!-- column rename -->
    <mapping ... target="SOURCE_TYPE" null="false" value="ADSO"/>  <!-- constant injection -->
  </input>
</calculationView>
```

**Broken SQL (before fix)**:
```sql
union_1 AS (SELECT 1 AS placeholder)
SELECT INFOCUBE, LASTUSED, SOURCE_TYPE FROM union_1  -- ❌ columns don't exist in placeholder
```

**Fixed SQL (after fix)**:
```sql
union_1 AS (
  SELECT adso.ADSONM AS INFOCUBE, adso.LASTUSED, 'ADSO' AS SOURCE_TYPE ...
  FROM adso
)
SELECT INFOCUBE, LASTUSED, SOURCE_TYPE FROM union_1  -- ✅
```

**Implementation**: `renderer.py::_render_union()` — guard changed from `len(node.inputs) < 2` to `len(node.inputs) == 0`

**Validated**: ADSO.xml (SESSION 14)

---

### Rule 19: Column Engine DECFLOAT → TO_DECIMAL (BUG-048)

**Rule ID**: `HANA_DECFLOAT_MAPPING`
**Applies To**: All HANA versions
**Category**: Function mapping
**Discovered**: 2026-03-03, ADSO.xml (SESSION 14)
**Bug Fixed**: BUG-048

**Why**: `decfloat()` is a Column Engine type-cast function and is **not valid in HANA SQL**. Passing it through unchanged produces error `[328]: invalid name of function or procedure: DECFLOAT`.

**Transformation**:
```
Source:  decfloat(expression)   →  Target: TO_DECIMAL(expression)
```

**Implementation**: `functions.yaml` catalog entry:
```yaml
- name: DECFLOAT
  handler: rename
  target: "TO_DECIMAL"
```

**Example** (from ADSO.xml):
```
decfloat(format(adddays(now(),-$$Backdays$$),'YYYYMMDD') + '000000')
  → TO_DECIMAL(TO_VARCHAR(ADD_DAYS(CURRENT_TIMESTAMP, -365), 'YYYYMMDD') || '000000')
```

**Validated**: ADSO.xml (SESSION 14)

---

### Rule 20: Input Parameter Placeholder Resolution in Filter Literals (BUG-049)

**Rule ID**: `HANA_PARAM_LITERAL_RESOLUTION`
**Applies To**: All HANA versions
**Category**: Parameter handling
**Discovered**: 2026-03-03, downstream SQL review SESSION 14
**Bug Fixed**: BUG-049

**Why**: Calculation Views can use `$$paramName$$` as filter values in `<viewAttribute><filter value="$$Language$$"/>` elements. These are stored as LITERAL expressions in the IR and never passed through `_substitute_placeholders()`. The parameter cleanup regex then strips the placeholder from inside the quoted string, leaving `''` (empty string).

**Transformation**:
```
value="$$Language$$" (defaultValue="E")  →  WHERE LANGU = 'E'
value="$$colname$$"  (defaultValue="")   →  WHERE COLNAME = ''   (correct by design)
```

**Implementation**: `renderer.py::_render_expression()` LITERAL branch — calls `_resolve_parameter_literal()` helper before `_render_literal()` when value contains `$$`. Helper looks up `ctx.scenario.variables` (populated from `<localVariables>` by `_parse_variables()`) to substitute defaultValue.

**Affected**: 17 filter occurrences across 10 files (ADSO, BEX_QUERIES, COMPOSITE_PROVIDER, DS_3X, DSO, INFOCUBES, INFOOBJECTS, INFOSET, MULTIPROVIDERS, OH_DEST)

**Validated**: Awaiting HANA execution

---

### Rule 21: Node-Level `<filter>` Elements on ProjectionView (BUG-050)

**Rule ID**: `HANA_NODE_LEVEL_FILTER`
**Applies To**: All HANA versions
**Category**: XML parsing / filter propagation
**Discovered**: 2026-03-03, downstream SQL review SESSION 14
**Bug Fixed**: BUG-050

**Why**: Some `ProjectionView` nodes carry a bare `<filter>` child element containing a COLUMN_ENGINE expression that filters the entire projection — distinct from per-column `<viewAttribute><filter>` elements. These were completely ignored by `_parse_filters()` which only scans inside `<viewAttribute>` children.

**Pattern in source XML**:
```xml
<calculationView xsi:type="Calculation:ProjectionView" id="Projection_2"
                 filterExpressionLanguage="COLUMN_ENGINE">
  ...
  <filter>(&quot;OBJVERS&quot; ='A')</filter>  <!-- ← COLUMN_ENGINE expression -->
</calculationView>
```

**Generated SQL (after fix)**:
```sql
projection_2 AS (
  SELECT ... FROM SAPK5D.RSZCOMPDIR
  WHERE (("OBJVERS" ='A'))   -- ← now included
)
```

**Implementation**: `scenario_parser.py::_parse_projection()` — after calling `_parse_filters()`, also reads bare `<filter>` child with `_find_child(node_el, "filter")`. If found, appends as `Predicate(kind=PredicateKind.RAW, ...)`. lxml auto-decodes HTML entities (`&quot;` → `"`).

**Affected**: RSZCOMPDIR projections in ADSO, INFOCUBES, MULTIPROVIDERS, COMPOSITE_PROVIDER, INFOSET, BEX_QUERIES; ZDTP_TRFN projections in TRANFORMATIONS, TRANSFORMATIONS_DETAILS, TRANSFORMATIONS_FIELDS_MAPPING

**Validated**: Awaiting HANA execution

---

### Rule 22: BOOLEAN Calculated Columns → CASE WHEN (BUG-051)

**Priority**: Applied during calculated column rendering
**Source Pattern**: `<calculatedViewAttribute datatype="BOOLEAN" expressionLanguage="COLUMN_ENGINE">`
**Transformation**: Wrap boolean expression in `CASE WHEN (...) THEN 1 ELSE 0 END`
**Reason**: HANA SQL does not support bare boolean expressions in SELECT lists
**Applied In**: `renderer.py` — all 3 calculated column rendering paths (projection, JOIN, aggregation)

**Example**:
```sql
-- Before (invalid HANA SQL):
LEFT(TABLE.LINE, 1)='*' or LEFT(TABLE.LINE, 5) = '...' AS COMMENTS

-- After (valid):
CASE WHEN (LEFT(TABLE.LINE, 1)='*' or LEFT(TABLE.LINE, 5) = '...') THEN 1 ELSE 0 END AS COMMENTS
```

**Affected**: Any XML with `datatype="BOOLEAN"` calculated view attributes (e.g., TRANFORMATIONS.xml)
**Validated**: Awaiting HANA execution

---

### Rule 23: SqlScriptView Definition Extraction + Auto Schema Resolution (BUG-052)

**Priority**: Applied during node rendering
**Source Pattern**: `<calculationView xsi:type="Calculation:SqlScriptView">` with `<definition>` element
**Transformation**: Extract SELECT from procedure body; auto-resolve hardcoded schemas via `<defaultSchema>` + schema_overrides
**Reason**: Script-based calculation views contain embedded SQL in `<definition>` — previously generated placeholder SQL. Hardcoded schemas from authoring system need remapping.
**Applied In**: `models.py` (metadata), `scenario_parser.py` (extraction), `renderer.py` (`_extract_select_from_script()`)

**Schema Resolution Logic**:
1. XML `<defaultSchema schemaName="ABAP"/>` → `default_schema = "ABAP"`
2. `schema_overrides["ABAP"]` → `target_schema = "SAPABAP1"`
3. Detect `"SAPK5D"` in script FROM clauses → not target → replaced with `"SAPABAP1"`

**Example**:
```
-- Script body (authored on BID system with SAPK5D schema):
BEGIN
  var_out = SELECT col1, col2 FROM "SAPK5D"."TABLE1" ...;
END

-- Extracted CTE (auto-resolved to SAPABAP1 via ABAP override):
SELECT col1, col2 FROM "SAPABAP1"."TABLE1" ...
```

**Affected**: Any XML with `calculationScenarioType="SCRIPT_BASED"` (e.g., USED_HIERARCHIES.xml)
**Validated**: Awaiting HANA execution

---

### Rule 24: Integer-Declared Calc Columns Wrapped with TO_INTEGER (BUG-053)

**Priority**: Applied during calculated column rendering
**Source Pattern**: `<element><inlineType primitiveType="SMALLINT|INTEGER|BIGINT|TINYINT"/><calculationDefinition>...</calculationDefinition></element>`
**Transformation**: Wrap rendered expression with `TO_INTEGER()` when declared type is integer-class
**Reason**: HANA Column Engine auto-coerces string literals (e.g., `'1'`, `'0'` from CASE WHEN) to declared type, but standard SQL doesn't. Without coercion, downstream `SUM`/`AVG` fails with HANA error [266].
**Applied In**: `renderer.py` — all 3 calculated column rendering paths (projection, JOIN, aggregation)

**Detection**: `calc_attr.data_type.type.value == "NUMBER" AND calc_attr.data_type.scale == 0`

**Example**:
```sql
-- Before (string-literal CASE WHEN — VARCHAR result):
CASE WHEN ... THEN '1' ELSE '0' END AS CC_PATTEST
SUM(CC_PATTEST)  -- ERROR [266]

-- After (TO_INTEGER coerces to integer):
TO_INTEGER(CASE WHEN ... THEN '1' ELSE '0' END) AS CC_PATTEST
SUM(CC_PATTEST)  -- works
```

**Affected**: Any XML with integer-typed calc columns whose formula returns string literals (e.g., CV_E2E_VST.xml). Safe no-op cast for already-numeric values.
**Validated**: ✅ CV_E2E_VST.xml (2026-05-10, CREATE VIEW 75ms)

---

### Rule 25: HANA Studio Malformed XML Pre-Processor (BUG-054)

**Priority**: Applied at XML ingestion (pre-parse, string-level)
**Source Pattern**: `leftInput="..."` or `rightInput="..."` attributes containing unescaped literal `"` quotes around an uppercase identifier (HANA schema name), e.g.:
```xml
<join leftInput="#//Join_2/Projection_1"
      rightInput="#//Join_2/"ABAP"./BIC/QEYPOSPER"
      joinType="leftOuter">
```
**Transformation**: Escape inner `"` as `&quot;` BEFORE lxml.parse() sees the bytes
**Reason**: HANA Studio export bug — should emit `&quot;` but emits literal `"`, breaking standards-compliant XML parsers (lxml, browsers). Same XML compiles in HANA Studio because its own parser is lenient with its own export bugs.

**Detection regex** (scoped tight):
```python
HANA_MALFORMED_QUOTE_PATTERN = re.compile(
    rb'((?:left|right)Input="[^"]*?)"([A-Z][A-Z0-9_]*)"([^"]*?")'
)
# Replacement: rb'\1&quot;\2&quot;\3'
```

**Applied In**: `parser/xml_sanitizer.py` — `sanitize_hana_xml_bytes()`. Called from:
- `parser/scenario_parser.py` — `parse_scenario()`
- `web/api/routes.py` — all 3 FastAPI upload handlers (after `file.read()`)
- `web/services/converter.py` — defensive sanitize before validation parse
- `cli/app.py` — secondary format-detection parse

**Safety properties**:
- **Idempotent**: running twice = running once (already-escaped `&quot;` has no literal `"` to re-match).
- **No false positives**: `<entity>#//"ABAP"./BIC/X</entity>` (text content) and `<comment text="...&quot;..."/>` (other attributes) are not touched — regex is anchored to `leftInput=`/`rightInput=` only.
- **Fast bail-out**: returns input unchanged if `leftInput`/`rightInput` substrings are absent.
- **Verified across 64 source XMLs**: 0 false-positives, 1 file fixed.

**Example**:
```
-- Before (lxml rejects):
rightInput="#//Join_2/"ABAP"./BIC/QEYPOSPER"

-- After (lxml accepts):
rightInput="#//Join_2/&quot;ABAP&quot;./BIC/QEYPOSPER"
```

**Affected**: Any XML re-exported from HANA Studio with this malformation pattern (e.g., CV_E2E_VST). Users no longer need to manually edit source XMLs.
**Validated**: ✅ End-to-end on user's `CV_E2E_VST (1).xml` Downloads file (2026-05-10). Awaiting fresh HANA Studio re-export validation.

---

## Known Limitations (HANA Mode)

### ❌ **NOT Implemented:**
1. ~~**Filter alias mapping**~~ ✅ SOLVED (Rule #12)
2. **Complex parameter cleanup** - DATE() nesting, multiple levels (CV_MCM_CNTRL_Q51)
3. **REGEXP_LIKE parameter patterns** - Special handling needed (CV_CT02_CT03)
4. **BW wrapper mode** - Implemented but optional

### ✅ **Working:**
1. All core transformations (IF, IN, strings, etc.)
2. Calculated column expansion
3. Subquery wrapping
4. Column qualification
5. Simple parameter removal
6. Version-aware function handling

---

## Files Reference

**Rules Catalog**: `src/xml_to_sql/catalog/data/conversion_rules.yaml`  
**Function Catalog**: `src/xml_to_sql/catalog/data/functions.yaml`  
**Implementation**: `src/xml_to_sql/sql/function_translator.py`, `src/xml_to_sql/sql/renderer.py`

---

**Status**: Core rules working for standard ECC calculation views. Edge cases documented for future refinement.

