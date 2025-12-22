# Bug Tracker - HANA Mode Conversion Issues

**Purpose**: Structured tracking of all bugs discovered during HANA mode testing  
**Version**: 2.3.0  
**Last Updated**: 2025-11-13

---

## Active Bugs

### 🔴 BUG-026: Parameter Substitution Cleanup - Malformed WHERE Clauses

**⚠️ IMPORTANT - BUG ID PRESERVATION**:
This bug ID (BUG-026) is **PERMANENT** and will follow this bug throughout its lifecycle.

**Priority**: Critical
**Status**: ✅ FIXED - Awaiting HANA Validation (2025-11-22)
**Discovered**: 2025-11-20, CV_ELIG_TRANS_01.xml, CV_UPRT_PTLG.xml
**XML**: CV_ELIG_TRANS_01.xml, CV_UPRT_PTLG.xml
**Instance Type**: BW (MBD)

**Errors**:
```
1. [257]: sql syntax error: incorrect syntax near "," (orphaned IN keywords)
2. [257]: sql syntax error: incorrect syntax near "=" (missing left operand)
3. [257]: sql syntax error: incorrect syntax near "," (escaped empty string comparisons)
4. Unbalanced WHERE clause parentheses after parameter removal
```

**Symptom**:
After HANA parameter placeholders (`$IP_PARAM$`) are substituted with empty strings (''), WHERE clauses contain malformed SQL fragments:
- `"CALMONTH" IN  = '000000'` (orphaned IN keyword before =)
- `( = '00000000')` (missing left operand in comparison)
- `( '''' = '')` (SQL-escaped empty string comparison with 4 quotes)
- `WHERE (("CALMONTH" = '000000')` (unbalanced parentheses)
- `"COLUMN" IN ('') or` (empty IN list with orphaned OR)
- `WHERE (())` (completely empty WHERE clause)

**Problems**:
```sql
-- CV_UPRT_PTLG line 30: Escaped empty string equality with unbalanced parens
WHERE (( '''' = '')  ← 4 quotes (SQL escaping), missing closing paren

-- CV_ELIG_TRANS_01 line 69: Multiple malformed patterns
WHERE (("CALMONTH" IN  = '000000') AND ( = '00000000')
      ↑ orphaned IN                    ↑ missing left operand

-- CV_ELIG_TRANS_01 line 72: Unbalanced parentheses
WHERE (("CALMONTH" = '000000')  ← missing closing paren
```

**Root Cause**:
When HANA parameters like `$IP_DATEFROM$` are replaced with empty strings, the `_cleanup_hana_parameter_conditions()` function wasn't comprehensive enough to handle all malformed patterns created by substitution. Original cleanup only handled a few basic cases, but real-world XMLs created many more complex malformed patterns.

**Pattern Explosion**:
Original XML parameters like:
- `($IP_CALMONTH$ IN ('') OR "CALMONTH" = $IP_CALMONTH$)`
- `($IP_DATE$ = '' OR DATE("COLUMN") >= DATE($IP_DATE$))`
- `('' IN (0) OR "COLUMN" IN (...))`

After substitution became:
- `('' IN ('') OR "CALMONTH" = '')`
- `('' = '' OR DATE("COLUMN") >= DATE(''))`
- `('' IN (0) OR "COLUMN" IN (...))`

After incomplete cleanup became:
- `"CALMONTH" IN  = ''` (orphaned IN)
- `( = '')` (missing left operand)
- `( '''' = '')` (escaped empty string)

**Solution Implemented**:
Added **12 comprehensive cleanup patterns** to `_cleanup_hana_parameter_conditions()` in renderer.py:

**Pattern 1**: Remove orphaned IN keyword
```python
# "CALMONTH" IN  = '000000' → "CALMONTH" = '000000'
result = re.sub(r'\bIN\s+(?==)', '', result, flags=re.IGNORECASE)
```

**Pattern 2**: Remove TO_DATE/DATE comparisons with NULL
```python
# TO_DATE(column) >= NULL → (removed)
result = re.sub(
    r'(?:TO_DATE|DATE)\s*\([^)]+\)\s*(?:>=|<=|>|<|=|!=)\s*NULL',
    '', result, flags=re.IGNORECASE
)
```

**Pattern 3**: Clean orphaned OR/AND before closing paren
```python
# (condition OR ) → (condition)
result = re.sub(r'\s+(?:OR|AND)\s*\)', ')', result, flags=re.IGNORECASE)
```

**Pattern 4**: Clean double opening parens with operators
```python
# (( OR condition → (condition
result = re.sub(r'\(\s*\(\s*(?:OR|AND)\s+', '(', result, flags=re.IGNORECASE)
```

**Pattern 5**: Clean orphaned AND/OR after opening paren
```python
# ( AND condition → (condition
result = re.sub(r'\(\s*(?:AND|OR)\s+', '(', result, flags=re.IGNORECASE)
```

**Pattern 6**: Remove malformed comparisons with missing left operand
```python
# ( = '00000000') → (removed)
result = re.sub(
    r'\s*(?:AND|OR)?\s*\(\s*=\s*[\'"][^\'"]*[\'"]\s*\)',
    '', result, flags=re.IGNORECASE
)
```

**Pattern 7**: Remove empty parentheses with just operators
```python
# ( AND ) → (removed)
result = re.sub(r'\(\s*(?:AND|OR)\s*\)', '', result, flags=re.IGNORECASE)
```

**Pattern 8**: Remove comparisons with empty string literal as left operand
```python
# ( '''' = '') → (removed)  (SQL escaped empty string with 4 quotes)
result = re.sub(
    r'\s*(?:AND|OR)?\s*\(\s*[\'"]+\s*=\s*[\'"]+\s*\)',
    '', result, flags=re.IGNORECASE
)
```

**Pattern 9**: Remove "COLUMN" IN ('') patterns
```python
# "COLUMN" IN ('') or → (removed)
result = re.sub(
    r'"\w+"\s+IN\s+\([\'"][\'"]?\)\s+(?:or|OR|and|AND)',
    '', result, flags=re.IGNORECASE
)
```

**Pattern 10**: Remove empty WHERE clauses with nested parentheses
```python
# WHERE (()) → (removed)
result = re.sub(r'WHERE\s+\(\(\s*\)\s*\)', '', result, flags=re.IGNORECASE)
```

**Pattern 11**: Remove empty WHERE clauses after all cleanup
```python
# WHERE () → (removed)
result = re.sub(r'WHERE\s+\(\s*\)', '', result, flags=re.IGNORECASE)
```

**Pattern 12**: Balance parentheses in WHERE condition
```python
# WHERE (("CALMONTH" = '000000') → WHERE (("CALMONTH" = '000000'))
# NOTE: This function receives WHERE condition WITHOUT the "WHERE" keyword
open_count = result.count('(')
close_count = result.count(')')

if open_count > close_count:
    result = result + (')' * (open_count - close_count))
elif close_count > open_count:
    excess = close_count - open_count
    for _ in range(excess):
        result = result.rstrip()
        if result.endswith(')'):
            result = result[:-1]
```

**Impact**:
- Affects ALL XMLs with HANA input parameters in WHERE clauses
- Critical fix enabling parameter-based views to execute
- CV_UPRT_PTLG now executes successfully (27ms)
- CV_ELIG_TRANS_01 WHERE clause now valid

**Affected XMLs** (confirmed):
- CV_UPRT_PTLG.xml ✅ VALIDATED in HANA (27ms)
- CV_ELIG_TRANS_01.xml (awaiting final validation)

**Related Rules**: Will add to HANA_CONVERSION_RULES.md

**Files Modified**:
- `xml2sql/src/xml_to_sql/sql/renderer.py`: Lines 1383-1491 (_cleanup_hana_parameter_conditions function)
  - Added 12 comprehensive cleanup patterns
  - Enhanced parenthesis balancing logic

**Next Steps**:
1. ✅ CV_UPRT_PTLG validated successfully in HANA
2. ⏳ Awaiting CV_ELIG_TRANS_01 final validation
3. Document in HANA_CONVERSION_RULES.md
4. Document in MANDATORY_PROCEDURES.md as validation check

---

### 🔴 BUG-019: CV_CT02_CT03 - REGEXP_LIKE with Calculated Columns in WHERE

**Priority**: Medium
**Status**: Active - Needs Research
**Discovered**: 2025-11-17 Session 3
**Affects**: ECC_ON_HANA XMLs with calculated columns referenced in REGEXP_LIKE filters

**Symptom**:
```
SAP DBTech JDBC: [257]: sql syntax error: incorrect syntax near "AND": line 29 col 206
```

**Root Cause**: Filters rendered with source table alias instead of subquery alias "calc" when WHERE references calculated columns in REGEXP_LIKE pattern matching.

**Example**:
```sql
-- WRONG: WHERE (REGEXP_LIKE(SAPABAP1."/BIC/AEZO_CT0200"."/BIC/EYTRTNUM", ...))
-- CORRECT: WHERE (REGEXP_LIKE(calc."/BIC/EYTRTNUM", ...))
```

**Attempted Fixes** (all failed):
1. Regex replacement - didn't match pattern
2. Use "calc" when calculated columns exist - broke CV_TOP_PTHLGY
3. Pre-scan filters for calculated column references - broke topological sort

**Next Steps**: Test more ECC_ON_HANA XMLs, analyze pattern, consider if acceptable limitation

**Details**: See GOLDEN_COMMIT.yaml for validated XMLs and SOLVED_BUGS.md for related bugs

---

### 🔴 BUG-023: HANA _SYS_BIC Package Path Format Rejection

**Priority**: Critical
**Status**: FIXED - Awaiting HANA Validation
**Discovered**: 2025-11-20, CV_ELIG_TRANS_01.xml
**XML**: CV_ELIG_TRANS_01.xml
**Instance Type**: BW (MBD)

**Error**:
```
SAP DBTech JDBC: [321]: invalid view name: Macabi_BI/Eligibility/CV_ELIG_TRANS_01: line 1 col 22 (at pos 21)
```

**Problem - WRONG**:
```sql
DROP VIEW "_SYS_BIC"."Macabi_BI/Eligibility/CV_ELIG_TRANS_01" CASCADE;
CREATE VIEW "_SYS_BIC"."Macabi_BI.Eligibility/CV_ELIG_TRANS_01" AS
```

**Problem - CORRECT**:
```sql
CREATE VIEW "_SYS_BIC"."CV_ELIG_TRANS_01" AS
```

**Root Cause - CRITICAL DISTINCTION**:
Package paths are ONLY for REFERENCES to other CVs, NOT for CREATE VIEW statements.

**Two Different Cases**:
1. **Creating a view** (converter.py): `CREATE VIEW "_SYS_BIC"."CV_NAME"` - NO package path
2. **Referencing other CVs** (renderer.py): `INNER JOIN "_SYS_BIC"."Package.Path/CV_NAME"` - WITH package path

**Why This Confused Us**:
- The `_SYS_BIC` catalog is the TARGET location where views are created
- The package structure (`Macabi_BI.Eligibility`) is the SOURCE location where HANA CVs are stored
- When you CREATE a view, you place it directly in `_SYS_BIC` without path prefix
- When you REFERENCE another CV, you must specify its full package path

**Solution Implemented**:
```python
# In converter.py (lines 312-319):
# Build qualified view name
# BUG-023 CRITICAL FIX: Package paths are ONLY for REFERENCES, NOT for CREATE VIEW
# When CREATING a view in _SYS_BIC: CREATE VIEW "_SYS_BIC"."CV_NAME" AS
# When REFERENCING a CV: INNER JOIN "_SYS_BIC"."Package.Path/CV_NAME" ON ...
qualified_view_name = (
    f"{effective_view_schema}.{scenario_id}" if effective_view_schema else scenario_id
)
```

**Result - CORRECT**:
```sql
CREATE VIEW "_SYS_BIC"."CV_ELIG_TRANS_01" AS
```

**Files Modified**:
- `xml2sql/src/xml_to_sql/web/services/converter.py`: Lines 312-319 (removed package path logic)

**Impact**: Affects ALL Calculation View conversions in HANA mode

**Next Steps**:
1. Regenerate CV_ELIG_TRANS_01.xml SQL
2. Verify CREATE VIEW has NO package path
3. Verify CV references (line 137) STILL have package path
4. Test in HANA Studio
5. Move to SOLVED_BUGS.md if successful

---

### 🔴 BUG-025: CALCULATION_VIEW References Use Wrong Schema Format

**Priority**: Critical
**Status**: FIXED - Awaiting HANA Validation
**Discovered**: 2025-11-20, CV_ELIG_TRANS_01.xml
**XML**: CV_ELIG_TRANS_01.xml
**Instance Type**: BW (MBD)

**Error**:
```
SAP DBTech JDBC: [259]: invalid table name: Could not find table/view ELIGIBILITY__CV_MD_EYPOSPER in schema _SYS_BIC: line 133 col 16 (at pos 6911)
```

**Problem**:
```sql
-- Line 137: WRONG - using lowercase alias format
INNER JOIN eligibility__cv_md_eyposper ON ...
```

CV_ELIG_TRANS_01 references another calculation view (CV_MD_EYPOSPER). Converter was using lowercase alias format instead of _SYS_BIC qualified name.

**Root Cause - FUNDAMENTAL ARCHITECTURAL MISUNDERSTANDING**:
HANA has TWO completely separate storage locations that were being confused:

1. **HANA CV Storage (Source)**: `Content > Macabi_BI > Eligibility > Calculation Views`
   - Where HANA CV definitions live
   - Package format: `Macabi_BI.Eligibility`

2. **SQL View Creation (Target)**: `Systems > _SYS_BIC > Views`
   - Where generated SQL views are created
   - Format: `"_SYS_BIC"."Package.Path/ViewName"`

**These are ALWAYS different locations!** The converter's `_render_from()` function didn't distinguish between:
- Base tables (SAPABAP1 schema)
- CTEs (use aliases)
- Calculation views (need _SYS_BIC + package path)

**Related Rules**: PRINCIPLE #1 (newly established - see HANA_CONVERSION_RULES.md)

**Impact**: Affects ANY XML that references other calculation views

**Affected XMLs**:
- CV_ELIG_TRANS_01.xml (discovered here - references CV_MD_EYPOSPER)
- Potentially any XML with CV-to-CV references

**Solution Implemented**:
```python
# In _render_from() function (renderer.py lines 942-970):
if ctx.database_mode == DatabaseMode.HANA and ds.source_type == DataSourceType.CALCULATION_VIEW:
    from ..package_mapper import get_package
    cv_name = ds.object_name
    package = get_package(cv_name)
    if package:
        view_name_with_package = f"{package}/{cv_name}"
        return f'"_SYS_BIC".{_quote_identifier(view_name_with_package)}'
```

**Result - CORRECT**:
```sql
-- Now generates:
INNER JOIN "_SYS_BIC"."Macabi_BI.Eligibility/CV_MD_EYPOSPER" ON ...
```

**Files Modified**:
- `xml2sql/src/xml_to_sql/sql/renderer.py`: Lines 942-970 (_render_from function)
- Added import: `DataSourceType` (line 13)

**Documentation**:
- Added PRINCIPLE #1 to `HANA_CONVERSION_RULES.md`
- Added SESSION 8 update to `llm_handover.md`
- Extensive code comments in renderer.py

**Next Steps**:
1. Regenerate CV_ELIG_TRANS_01.xml SQL
2. Test in HANA Studio
3. Move to SOLVED_BUGS.md if successful

---

### 🔴 BUG-027: Column Ambiguity in JOIN Calculated Columns - RAW Expression Qualification

**⚠️ IMPORTANT - BUG ID PRESERVATION**:
This bug ID (BUG-027) is **PERMANENT** and will follow this bug throughout its lifecycle.

**Priority**: High
**Status**: ✅ FIXED - Awaiting HANA Validation (2025-11-22)
**Discovered**: 2025-11-22, CV_ELIG_TRANS_01.xml
**XML**: CV_ELIG_TRANS_01.xml
**Instance Type**: BW (MBD)

**Error**:
```
SAP DBTech JDBC: [268]: column ambiguously defined: CALDAY: line 95 col 9 (at pos 5259)
```

**Problem**:
```sql
-- Line 37 in join_1 CTE - calculated column with RAW expression:
"CALDAY" AS CC_CALDAY  ← Unqualified, ambiguous in JOIN context

-- Both JOIN inputs have CALDAY column:
FROM prj_visits              -- has CALDAY
LEFT OUTER JOIN prj_treatments  -- also has CALDAY
```

Calculated column `CC_CALDAY` uses RAW expression `"CALDAY"` which doesn't specify whether it refers to `prj_visits.CALDAY` or `prj_treatments.CALDAY`.

**Root Cause**:
In `_render_expression()` function, RAW expression types (`ExpressionType.RAW`) were not using the `table_alias` parameter to qualify simple column names. The function had logic for COLUMN expression types to qualify with table alias, but RAW expressions bypassed this logic.

**Why RAW Expressions**:
Calculated columns in JOIN nodes use RAW expression type when the expression is a simple column reference from the XML metadata. These need qualification just like COLUMN types when in a multi-table context.

**SQL Fragment**:
```sql
join_1 AS (
  SELECT
      prj_visits.CALDAY AS CALDAY,       -- Regular column (qualified)
      ...,
      1 AS CC_1,                         -- Calculated literal
      "CALDAY" AS CC_CALDAY              -- Calculated RAW (was unqualified)
  FROM prj_visits
  LEFT OUTER JOIN prj_treatments ON ...
)
```

**Solution Implemented**:
Added table alias qualification logic for RAW expressions when they represent simple column names:

```python
# In _render_expression() function (renderer.py lines 996-1007):
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
```

**Logic**:
1. Check if `table_alias` is provided (indicates multi-table context)
2. Check if result is a simple identifier (strip quotes, check isidentifier)
3. Check if result doesn't contain '(' (not a function call)
4. If all true: qualify with `table_alias.column_name`

**Result - CORRECT**:
```sql
join_1 AS (
  SELECT
      ...,
      prj_visits."CALDAY" AS CC_CALDAY  -- Now qualified with table alias
  FROM prj_visits
  LEFT OUTER JOIN prj_treatments ON ...
)
```

**Impact**:
- Affects JOIN nodes where calculated columns reference simple column names
- Critical for disambiguating columns with same name in multiple JOIN inputs
- Preserves qualification for regular columns, adds it for calculated RAW expressions

**Affected XMLs** (confirmed):
- CV_ELIG_TRANS_01.xml (awaiting final validation)

**Related Rules**: Will add to HANA_CONVERSION_RULES.md (Column qualification in JOIN contexts)

**Files Modified**:
- `xml2sql/src/xml_to_sql/sql/renderer.py`: Lines 996-1007 (_render_expression function)
  - Added table_alias qualification for RAW expressions with simple column names

**Next Steps**:
1. ⏳ Awaiting CV_ELIG_TRANS_01 final validation with BUG-027 fix
2. Document in HANA_CONVERSION_RULES.md
3. Move to SOLVED_BUGS.md if successful

---

### 🔴 BUG-028: CTE Topological Sort - Input ID Normalization Bug

**⚠️ IMPORTANT - BUG ID PRESERVATION**:
This bug ID (BUG-028) is **PERMANENT** and will follow this bug throughout its lifecycle.

**Priority**: Critical
**Status**: ✅ FIXED - Awaiting HANA Validation (2025-11-22)
**Discovered**: 2025-11-22, CV_ELIG_TRANS_01.xml
**XML**: CV_ELIG_TRANS_01.xml
**Instance Type**: BW (MBD)

**Error**:
```
SAP DBTech JDBC: [259]: invalid table name: Could not find table/view PRJ_VISITS in schema _SYS_BIC: line 109 col 10 (at pos 5651)
```

**Problem**:
```sql
-- CTE join_1 defined BEFORE its dependency prj_visits:
join_1 AS (
  SELECT ...
  FROM prj_visits              -- ERROR: prj_visits not defined yet
  LEFT OUTER JOIN prj_treatments ON ...
),
prj_visits AS (                -- Defined AFTER it's referenced!
  SELECT ...
),
```

CTE `join_1` references `prj_visits`, but `prj_visits` is defined AFTER `join_1` in the SQL output. This violates HANA's CTE ordering requirement that dependencies must be defined before use.

**Root Cause**:
The `_topological_sort()` function in renderer.py (lines 298-313) was incorrectly cleaning input IDs for dependency tracking. It only used `lstrip("#")` which:
- `#/0/prj_visits` → `/0/prj_visits` (left "/" and "0/")
- `/0/prj_visits` didn't match node ID `prj_visits`
- Dependency tracking failed

**Why This Broke**:
```python
# WRONG (original code line 301):
for input_id in node.inputs:
    cleaned = input_id.lstrip("#")  # Only removes "#" prefix
    # Example: "#/0/prj_visits" → "/0/prj_visits"
    # But node_id is "prj_visits" - NO MATCH!
    if cleaned in all_ids:
        graph[cleaned].append(node_id)  # Never executes
```

**Input ID Patterns**:
XML metadata uses various reference formats:
- `#/0/prj_visits` - Reference with index and slash
- `#//prj_visits` - Reference with double slash
- `#/prj_visits` - Reference with single slash
- `prj_visits` - Clean node ID

All these need to normalize to `prj_visits` for matching.

**Solution Implemented**:
Use `_clean_ref()` function and regex to properly normalize input IDs:

```python
# In _topological_sort() function (renderer.py lines 298-313):
for node_id, node in scenario.nodes.items():
    all_ids.add(node_id)
    for input_id in node.inputs:
        # CRITICAL: Clean input_id using same logic as get_cte_alias to ensure matching
        # Input IDs might be: "#/0/prj_visits", "#//prj_visits", "prj_visits"
        # We need to normalize them all to "prj_visits" to match node_id
        from ..parser.scenario_parser import _clean_ref
        import re
        cleaned_input = _clean_ref(input_id)  # Removes "#" and normalizes
        cleaned_input = re.sub(r'^\d+/', '', cleaned_input)  # Remove digit+slash prefixes

        if cleaned_input in all_ids:
            graph[cleaned_input].append(node_id)
            in_degree[node_id] += 1
        else:
            in_degree[node_id] += 0
```

**Normalization Steps**:
1. Use `_clean_ref(input_id)` to remove "#" and normalize slashes
2. Use regex `r'^\d+/'` to remove patterns like `0/`, `1/`, etc.
3. Result: All variants normalize to simple node ID

**Examples**:
```python
"#/0/prj_visits"
  → _clean_ref()  → "0/prj_visits"
  → re.sub()      → "prj_visits" ✅ MATCHES

"#//prj_visits"
  → _clean_ref()  → "prj_visits" ✅ MATCHES

"#/prj_visits"
  → _clean_ref()  → "prj_visits" ✅ MATCHES
```

**Result - CORRECT CTE Order**:
```sql
prj_visits AS (                -- Defined FIRST
  SELECT ...
),
prj_treatments AS (            -- Defined SECOND
  SELECT ...
),
join_1 AS (                    -- References previous CTEs
  SELECT ...
  FROM prj_visits              -- Now valid!
  LEFT OUTER JOIN prj_treatments ON ...
)
```

**Impact**:
- Affects ALL XMLs with multi-node scenarios (most complex CVs)
- Critical for correct CTE dependency ordering
- Without this, CTEs could reference undefined CTEs causing HANA errors

**Affected XMLs** (confirmed):
- CV_ELIG_TRANS_01.xml (awaiting final validation)

**Related Rules**: Will add to HANA_CONVERSION_RULES.md (CTE ordering requirements)

**Files Modified**:
- `xml2sql/src/xml_to_sql/sql/renderer.py`: Lines 298-313 (_topological_sort function)
  - Changed from `lstrip("#")` to proper `_clean_ref()` + regex normalization
  - Added imports for `_clean_ref` and `re`

**Next Steps**:
1. ⏳ Awaiting CV_ELIG_TRANS_01 final validation with BUG-028 fix
2. Document in HANA_CONVERSION_RULES.md
3. Move to SOLVED_BUGS.md if successful

---

### BUG-001: JOIN Column Resolution - Wrong Projection Reference

**Status**: ✅ **SOLVED** (2025-11-13)  
**Severity**: High  
**Discovered**: CV_INVENTORY_ORDERS.xml testing  
**XML**: CV_INVENTORY_ORDERS.xml  
**Instance Type**: BW (BID)

**Error**:
```
SAP DBTech JDBC: [260]: invalid column name: PROJECTION_6.EINDT: line 103 col 9
```

**Problem**:
```sql
-- Line 103 in join_6
SELECT projection_6.EINDT AS EINDT
FROM projection_6
```

But `projection_6` doesn't have column `EINDT` - it's in `projection_8`.

**Root Cause**:
- JOIN node mapping logic incorrectly resolves which projection exposes which columns
- CTE column propagation doesn't track which columns come from which input
- May be parser issue (incorrect mappings in IR) or renderer issue (wrong CTE reference)

**Related Rules**: None - this is a core IR/rendering bug, not a transformation rule issue

**Impact**: Affects any XML with JOINs where columns come from different projections

**Affected XMLs**:
- CV_INVENTORY_ORDERS.xml
- Potentially others with complex joins

**Next Steps**:
1. Debug JOIN node rendering logic
2. Check how `source_node` is determined in mappings
3. Verify parser correctly captures which input provides which column

---

### BUG-002: Complex Parameter Pattern Cleanup

**Status**: 🔴 **OPEN**  
**Severity**: Medium  
**Discovered**: CV_MCM_CNTRL_Q51.xml testing  
**XML**: CV_MCM_CNTRL_Q51.xml  
**Instance Type**: ECC (MBD)

**Error**:
```
Multiple: Unbalanced parentheses, malformed DATE() calls, orphaned operators
```

**Problem**:
```sql
-- Original XML
('$$IP_DATEFROM$$' = '' OR (DATE("ZZTREAT_DATE") >= DATE('$$IP_DATEFROM$$')))

-- After substitution ($$IP → '')
('' = '' OR (DATE("ZZTREAT_DATE") >= DATE('')))

-- After attempted cleanup
)  >= DATE('')))       -- Corrupted!
```

**Root Cause**:
- Parameter substitution creates malformed SQL FIRST
- Cleanup tries to fix AFTER but can't handle deep nesting
- DATE() function calls with parameters create special complexity
- Multiple parameter references in single expression

**Related Rules**: 
- ✅ Rule #9: Parameter Removal (works for simple cases)
- ❌ Needs enhancement for nested DATE() patterns

**Impact**: 
- Affects XMLs with complex parameter patterns
- 8+ parameters with DATE() nesting particularly problematic

**Affected XMLs**:
- CV_MCM_CNTRL_Q51.xml (8+ parameters, DATE nesting)
- CV_CT02_CT03.xml (REGEXP_LIKE + parameters)

**Proposed Solution**:
- Pre-removal strategy: Remove entire parameter clauses BEFORE substitution
- Don't substitute `$$IP_XXX$$` → `''`, just remove the whole `($$IP_XXX$$ = '' OR ...)` pattern

**Next Steps**:
1. Implement pre-removal in `_substitute_placeholders()`
2. Test on CV_MCM_CNTRL_Q51.xml
3. Update Rule #9 with pre-removal approach

**Deferred**: For later session

---

### BUG-003: REGEXP_LIKE with Parameter Patterns

**Status**: 🔴 **OPEN**  
**Severity**: Medium  
**Discovered**: CV_CT02_CT03.xml testing  
**XML**: CV_CT02_CT03.xml  
**Instance Type**: ECC (MBD)

**Error**:
```
SAP DBTech JDBC: [257]: sql syntax error: incorrect syntax near "AND": line 29 col 165
```

**Problem**:
```sql
WHERE (REGEXP_LIKE(..., CASE WHEN ''= '' THEN '*' ELSE calc.col END, ...) AND
    REGEXP_LIKE(...) AND
    ...
```

Issues:
1. `''=''` - Spacing issue (should be `'' = ''`)
2. Parameter substitution in REGEXP_LIKE pattern creates always-true CASE
3. Multiple consecutive REGEXP_LIKE with parameter CASE patterns

**Root Cause**:
- Parameters used inside REGEXP_LIKE patterns
- CASE WHEN with always-true conditions (`'' = ''`)
- Cleanup doesn't simplify these nested patterns

**Related Rules**:
- ✅ Rule #3: String Concatenation (|| preserved in REGEXP_LIKE)
- ❌ Needs: Parameter simplification in REGEXP_LIKE contexts

**Impact**: XMLs with match() helper functions + parameters

**Affected XMLs**:
- CV_CT02_CT03.xml

**Proposed Solution**:
- Simplify `CASE WHEN '' = '' THEN '*' ELSE x END` → `'*'` (always takes THEN branch)
- Or remove parameter logic from REGEXP_LIKE patterns entirely

**Deferred**: For later session

---

### BUG-004: Filter Alias vs Source Name Mapping

**Status**: ✅ **SOLVED** (2025-11-13) - Moved to SOLVED_BUGS.md  
**Severity**: High  
**Discovered**: CV_INVENTORY_ORDERS.xml testing  
**XML**: CV_INVENTORY_ORDERS.xml

**Error**:
```
SAP DBTech JDBC: [260]: invalid column name: LOEKZ_EKPO: line 67 col 12
```

**Problem**:
```sql
SELECT SAPABAP1."/BIC/AZEKPO2".LOEKZ AS LOEKZ_EKPO ...
WHERE ("LOEKZ_EKPO" ='')  -- Alias doesn't exist in WHERE context
```

**Root Cause**:
- Filters use target/alias column names
- Base table queries need source column names
- Mapping: `LOEKZ` (source) → `LOEKZ_EKPO` (target/alias)

**Solution Implemented**:
```python
# In _render_projection():
target_to_source_map = {}
for mapping in node.mappings:
    if mapping.expression.expression_type == ExpressionType.COLUMN:
        source_col = mapping.expression.value
        target_col = mapping.target_name
        if source_col != target_col:
            target_to_source_map[target_col.upper()] = source_col

# Replace target names with source names in WHERE
for target_name, source_name in target_to_source_map.items():
    where_clause = where_clause.replace(f'"{target_name}"', f'"{source_name}"')
```

**Related Rules**: 
- 🆕 **Rule #12: Filter Source Mapping** (added)
- Priority: 25
- Document: Added to HANA_CONVERSION_RULES.md

**Fix Verified**: Code changed, SQL regenerated  
**Status**: ✅ FIXED (waiting HANA validation)

**Files Modified**:
- `src/xml_to_sql/sql/renderer.py` - Lines 419-439

---

### 🟡 BUG-036: ConstantAttributeMapping Not Rendered in UNION Nodes

**⚠️ IMPORTANT - BUG ID PRESERVATION**:
This bug ID (BUG-036) is **PERMANENT** and will follow this bug throughout its lifecycle.

**Priority**: Critical
**Status**: ✅ FIXED - Awaiting HANA Validation (2025-12-11)
**Discovered**: 2025-12-11, Transformations.XML
**XML**: Transformations.XML
**Instance Type**: BW (SAPK5D schema)

**Error**:
```
SAP DBTech JDBC: [260]: invalid column name: CODE_TYPE: line 341 col 205 (at pos 13124)
```

**Problem**:
```sql
-- UNION CTE only selects 20 columns (SRC through LINE):
union_1 AS (
  SELECT
      glbcode.SRC AS SRC,
      ...
      glbcode.LINE AS LINE
      -- CODE_TYPE MISSING!
  FROM glbcode
  UNION ALL
  ...
)

-- But final SELECT expects 21 columns including CODE_TYPE:
SELECT SRC, ..., LINE_NO, LINE, CODE_TYPE FROM union_1
                                 ^^^^^^^^^^ NOT DEFINED!
```

**Root Cause**:
The XML uses `ConstantAttributeMapping` to define constant values for each UNION branch:
```xml
<mapping xsi:type="Calculation:ConstantAttributeMapping" target="CODE_TYPE" null="false" value="GLBCODE_ROUTINE"/>
```

The UNION renderer in `renderer.py` does NOT handle `ConstantAttributeMapping` entries. It only processes regular `AttributeMapping` entries, so constant columns are completely missing from the generated SQL.

**Expected Output**:
```sql
union_1 AS (
  SELECT
      glbcode.SRC AS SRC,
      ...
      glbcode.LINE AS LINE,
      'GLBCODE_ROUTINE' AS CODE_TYPE  -- SHOULD BE HERE
  FROM glbcode
  UNION ALL
  SELECT
      glbcode2.SRC AS SRC,
      ...
      glbcode2.LINE AS LINE,
      'GLBCODE2_ROUTINE' AS CODE_TYPE  -- SHOULD BE HERE
  FROM glbcode2
  ...
)
```

**Related Rules**: None - new pattern not previously encountered

**Impact**: Affects ANY XML with UNION nodes that use constant column mappings

**Affected XMLs**:
- Transformations.XML (5 UNION branches, each needs CODE_TYPE constant)

**Solution Implemented**:
Root cause was in the **parser**, not renderer. `_parse_mappings()` skipped ConstantAttributeMapping entries because they have no `source` attribute.

```python
# BUG-036 FIX in scenario_parser.py lines 413-427:
# Check for ConstantAttributeMapping type (xsi:type attribute)
mapping_type = mapping_el.get("{http://www.w3.org/2001/XMLSchema-instance}type", "")
if "ConstantAttributeMapping" in mapping_type:
    constant_value = mapping_el.get("value", "")
    if not target:
        continue
    data_type = guess_attribute_type(target)
    expr = Expression(ExpressionType.LITERAL, constant_value, data_type)
elif not target or not source:
    continue
else:
    data_type = guess_attribute_type(target)
    expr = Expression(ExpressionType.COLUMN, source, data_type)
```

**Files Modified**:
- `src/xml_to_sql/parser/scenario_parser.py`: Lines 413-427 (_parse_mappings function)
  - Added detection of ConstantAttributeMapping xsi:type
  - Creates LITERAL expression with constant value instead of COLUMN expression

**Next Steps**:
1. Restart server: `utilities\restart_server.bat`
2. Re-convert Transformations.XML
3. Verify CODE_TYPE column appears in UNION branches
4. Test in HANA

---

### 🟡 BUG-037: CV Reference Path Includes Folder Prefix When No Package Mapping

**⚠️ IMPORTANT - BUG ID PRESERVATION**:
This bug ID (BUG-037) is **PERMANENT** and will follow this bug throughout its lifecycle.

**Priority**: Critical
**Status**: ✅ FIXED - Awaiting HANA Validation (2025-12-15)
**Discovered**: 2025-12-15, Transformations.XML
**XML**: Transformations.XML
**Instance Type**: BW (SAPK5D schema)

**Error**:
```
SAP DBTech JDBC: [259]: invalid table name: Could not find table/view Assesment/ASSESSMENT_REPORT in schema _SYS_BIC
```

**Problem**:
```sql
-- Generated SQL includes folder prefix from resourceUri:
FROM "_SYS_BIC"."Assesment/ASSESSMENT_REPORT"
                ^^^^^^^^^^ folder prefix should NOT be included!

-- Correct format:
FROM "_SYS_BIC"."ASSESSMENT_REPORT"
```

**Root Cause**:
When parsing DataSource elements with `resourceUri="/Assesment/calculationviews/ASSESSMENT_REPORT"`, the parser extracts `cv_name = "Assesment/ASSESSMENT_REPORT"` (folder + view name). When no package mapping exists, the renderer was using this full path directly instead of extracting just the view name.

In HANA, CV views under `_SYS_BIC` are referenced by view name only, not by folder path.

**Solution**:
In `renderer.py`, when no package mapping is found, extract just the view name (after last "/"):
```python
# BUG-037 FIX in renderer.py lines 987-993 and 1015-1021:
view_name_only = cv_name.split('/')[-1] if '/' in cv_name else cv_name
return f'"_SYS_BIC"."{view_name_only}"'
```

**Files Modified**:
- `src\xml_to_sql\sql\renderer.py`: Lines 987-993 and 1017-1021 (_resolve_input_table function)
  - Added path extraction for cv_name when no package mapping exists
  - Two occurrences: both fallback paths now extract view name only

**Next Steps**:
1. Restart server: `utilities\restart_server.bat`
2. Re-convert Transformations.XML
3. Verify CV reference is `"_SYS_BIC"."ASSESSMENT_REPORT"` (no path prefix)
4. Test in HANA

---

### 🟡 BUG-038: ABAP Generation Fails Due to SQL Comments

**⚠️ IMPORTANT - BUG ID PRESERVATION**:
This bug ID (BUG-038) is **PERMANENT** and will follow this bug throughout its lifecycle.

**Priority**: High
**Status**: ✅ FIXED - Awaiting Validation (2025-12-15)
**Discovered**: 2025-12-15, Transformations.XML (ABAP tab)
**Component**: sql_to_abap.py (Pure ABAP Generator)

**Error**:
```
ABAP generation failed: SQL must have WITH clause with CTEs for Pure ABAP conversion
```

**Problem**:
The SQL generated by the renderer includes header comments:
```sql
-- Last generated: 2025-12-15 11:39:17
-- Scenario ID: TRANFORMATIONS

-- Warnings:
--   Package not found for CV Assesment/ASSESSMENT_REPORT, using _SYS_BIC without path

DROP VIEW "_SYS_BIC"."TRANFORMATIONS" CASCADE;
CREATE VIEW "_SYS_BIC"."TRANFORMATIONS" AS
WITH
  aggregation_1 AS (
```

The `parse_sql()` function checks `sql_upper.startswith('DROP VIEW')` but after whitespace normalization, the SQL starts with `-- LAST GENERATED...` not `DROP VIEW`, so the DROP/CREATE/WITH detection fails.

**Root Cause**:
The `parse_sql()` function in `sql_to_abap.py` didn't strip SQL comments before checking for DROP VIEW/CREATE VIEW/WITH patterns.

**Solution**:
Added SQL comment stripping at the beginning of `parse_sql()` (lines 128-142):
```python
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
```

**Files Modified**:
- `src/xml_to_sql/abap/sql_to_abap.py`: Lines 128-142 (parse_sql function)
  - Added comment stripping before pattern detection

**Next Steps**:
1. Restart server: `utilities\restart_server.bat`
2. Convert Transformations.XML
3. Click "Generate ABAP Report" on ABAP tab
4. Verify ABAP generation succeeds

---

### 🟡 BUG-039: ABAP Internal Table Naming Mismatch (CTE Case Sensitivity)

**⚠️ IMPORTANT - BUG ID PRESERVATION**:
This bug ID (BUG-039) is **PERMANENT** and will follow this bug throughout its lifecycle.

**Priority**: Critical
**Status**: ✅ FIXED - Awaiting Validation (2025-12-15)
**Discovered**: 2025-12-15, Transformations.XML (ABAP generation)
**Component**: sql_to_abap.py (Pure ABAP Generator)

**Error**:
```
SAP ECC: The field 'LT_AGGREGATION_1' is unknown, but there is a field with the similar name 'LT_AGGREGATION_2'
Line 374: LOOP AT lt_aggregation_1 INTO ls_aggregation_1.
```

**Problem**:
The generated ABAP code references internal tables that were never declared:
```abap
" DATA declarations contain:
DATA: lt_aggregation_2 TYPE TABLE OF ty_aggregation_2.

" But code tries to LOOP AT:
LOOP AT lt_aggregation_1 INTO ls_aggregation_1.   " <-- ERROR: lt_aggregation_1 not declared!
```

**Root Cause**:
Case mismatch between CTE dictionary keys and input references in sql_to_abap.py:
1. CTE names stored in `result.ctes` with **original case** from SQL: `result.ctes['Aggregation_1']`
2. Input references (union_inputs, left_input, right_input) stored **lowercased**: `union_inputs = ['aggregation_1']`
3. When `_get_intermediate_ctes()` checks `if name in required_inputs`, it fails because:
   - `'Aggregation_1' in {'aggregation_1'}` = **FALSE**
4. CTE doesn't get added to intermediate_ctes, so no DATA declaration is generated
5. But other code still references `lt_aggregation_1` expecting it to exist

**Solution**:
Lowercase CTE keys consistently in `parse_sql()` (line 184):
```python
# BUG-039 FIX: Lowercase CTE keys for consistent lookup
# Input references (union_inputs, left_input, right_input, filter_input) are all lowercased
# So CTE keys must also be lowercased to match
for cte_name, cte_body in cte_defs:
    parsed_cte = _parse_cte_body(cte_name, cte_body)
    result.ctes[cte_name.lower()] = parsed_cte
```

**Files Modified**:
- `src/xml_to_sql/abap/sql_to_abap.py`: Line 184 (parse_sql function)
  - Changed `result.ctes[cte_name]` to `result.ctes[cte_name.lower()]`

**Cross-Reference**: Also tracked as ABAP-003 in sql-to-abap pipeline docs

**Next Steps**:
1. Reinstall package: `pip install -e .`
2. Restart server: `utilities\restart_server.bat`
3. Convert Transformations.XML
4. Generate ABAP Report
5. Test in SAP (SE38 syntax check)

---

## Resolved Bugs

*(Will move BUG-004 here after HANA validation confirms it works)*

---

### ✅ BUG-040: SUM Aggregation on NVARCHAR Column Causes Datatype Error

**⚠️ IMPORTANT - BUG ID PRESERVATION**:
This bug ID (BUG-040) is **PERMANENT** and will follow this bug throughout its lifecycle.

**Priority**: Critical
**Status**: ✅ VALIDATED IN HANA (2025-12-22) - 127ms execution time
**Discovered**: 2025-12-22, COPYOF_CV_ACOUSTIC_1_09072023.xml
**XML**: COPYOF_CV_ACOUSTIC_1_09072023.xml
**Instance Type**: BW (Maccabi-BW_ON_HANA)

**Error**:
```
SAP DBTech JDBC: [266]: inconsistent datatype: only numeric type is available for SUM/AVG/STDDEV/VAR function: line 1454 col 9 (at pos 71927)
```

**Problem**:
```sql
-- Line 1458 in aggregation CTE:
SUM(join_8.ZZHOUR_MIDL_ZPA0002) AS ZZHOUR_MIDL_ZPA0002
```

The column `ZZHOUR_MIDL_ZPA0002` has `aggregationBehavior="SUM"` in the XML, but its data type is `NVARCHAR(3)` (not numeric). HANA cannot SUM non-numeric columns.

**XML Definition**:
```xml
<element name="ZZHOUR_MIDL_ZPA0002" aggregationBehavior="SUM" engineAggregation="COUNT">
  <inlineType primitiveType="NVARCHAR" length="3" precision="3" scale="0"/>
</element>
```

**Root Cause**:
The renderer applies aggregation functions (SUM, AVG, etc.) directly from `aggregationBehavior` without checking if the column's data type is numeric. When the source XML has a data model issue (SUM on VARCHAR), the renderer generates invalid SQL.

**Proposed Solution**:
When rendering aggregations, check the column data type:
1. If data type is NVARCHAR/VARCHAR and aggregation is SUM/AVG: CAST to numeric
2. Or use COUNT instead of SUM for non-numeric columns
3. Or emit a warning and skip the aggregation

**Solution Implemented**:
Added TO_INTEGER() cast for SUM/AVG/STDDEV/VAR aggregations on non-numeric columns:

```python
# In _render_aggregation() function (renderer.py lines 740-751):
# BUG-040: Check if aggregation function requires numeric type but column is VARCHAR/NVARCHAR
if agg_func in ('SUM', 'AVG', 'STDDEV', 'VAR') and ctx.database_mode == DatabaseMode.HANA:
    data_type = agg_spec.data_type or agg_spec.expression.data_type
    if data_type:
        type_str = str(data_type).upper() if data_type else ''
        if 'VARCHAR' in type_str or 'CHAR' in type_str or 'STRING' in type_str or 'NVARCHAR' in type_str:
            agg_expr = f"TO_INTEGER({agg_expr})"
            ctx.warnings.append(f"BUG-040: Column {agg_spec.target_name} is {data_type} but has {agg_func} aggregation - casting to integer")
```

**Result - CORRECT**:
```sql
SUM(TO_INTEGER(join_8.ZZHOUR_MIDL_ZPA0002)) AS ZZHOUR_MIDL_ZPA0002
```

**Files Modified**:
- `src/xml_to_sql/sql/renderer.py`: Lines 740-751 (_render_aggregation function)

**Next Steps**:
1. Re-convert COPYOF_CV_ACOUSTIC_1_09072023.xml
2. Test in HANA
3. Move to SOLVED_BUGS.md if successful

---

### 🟠 BUG-041: DROP VIEW Fails on Non-Existent View (First-Time Conversion)

**⚠️ IMPORTANT - BUG ID PRESERVATION**:
This bug ID (BUG-041) is **PERMANENT** and will follow this bug throughout its lifecycle.

**Priority**: Low (workaround available)
**Status**: 🟠 REVERTED - IF EXISTS not supported in user's HANA version (2025-12-22)
**Discovered**: 2025-12-22, COPYOF_CV_ACOUSTIC_1_09072023.xml
**XML**: COPYOF_CV_ACOUSTIC_1_09072023.xml
**Instance Type**: BW (Maccabi-BW_ON_HANA)

**Error**:
```
SAP DBTech JDBC: [321]: invalid view name: COPYOF_CV_ACOUSTIC_1_09072023: line 1 col 22 (at pos 21)
```

**Problem**:
```sql
DROP VIEW "_SYS_BIC"."COPYOF_CV_ACOUSTIC_1_09072023" CASCADE;
CREATE VIEW "_SYS_BIC"."COPYOF_CV_ACOUSTIC_1_09072023" AS
```

When running a conversion for the first time, the view doesn't exist yet. The `DROP VIEW` statement fails because HANA cannot find the view to drop.

**Root Cause**:
Current code uses `DROP VIEW ... CASCADE` without `IF EXISTS`. HANA 2.0 SPS03+ supports `IF EXISTS` but earlier versions don't.

**Current Code** (renderer.py line 1738):
```python
return f"DROP VIEW {quoted_name} CASCADE;\nCREATE VIEW {quoted_name} AS"
```

**Proposed Solution**:
1. For HANA 2.0 SPS03+: Use `DROP VIEW IF EXISTS ... CASCADE`
2. For older versions: Document that first DROP failure is expected and can be ignored
3. Or: Generate separate DROP and CREATE statements so user can run CREATE only

**Solution Implemented**:
Added `IF EXISTS` to DROP VIEW statement for HANA 2.0 SPS03+:

```python
# In _generate_view_statement() function (renderer.py line 1754):
# BUG-041: Added IF EXISTS for HANA 2.0 SPS03+ (released 2017+)
return f"DROP VIEW IF EXISTS {quoted_name} CASCADE;\nCREATE VIEW {quoted_name} AS"
```

**Result - CORRECT**:
```sql
DROP VIEW IF EXISTS "_SYS_BIC"."COPYOF_CV_ACOUSTIC_1_09072023" CASCADE;
CREATE VIEW "_SYS_BIC"."COPYOF_CV_ACOUSTIC_1_09072023" AS
```

**Files Modified**:
- `src/xml_to_sql/sql/renderer.py`: Line 1754 (_generate_view_statement function)

**REVERTED (2025-12-22)**:
User's HANA version does NOT support `IF EXISTS`. Got error:
```
[257]: sql syntax error: incorrect syntax near "IF": line 1 col 11 (at pos 11)
```

The `IF EXISTS` syntax was removed. Original behavior restored.

**Workaround for First-Time Conversion**:
1. Run the generated SQL
2. If DROP VIEW fails with `[321] invalid view name`, that's expected (view doesn't exist)
3. Manually run only the `CREATE VIEW ...` part (skip the DROP)
4. Subsequent runs will work because view now exists

**Note**: This is a HANA version limitation, not a converter bug. Low priority since workaround is simple.

---

## Bug Statistics

**Total Bugs Tracked**: 41
**Open**: 1 (BUG-019)
**Fixed - Awaiting Validation**: 4 (BUG-036, BUG-037, BUG-038, BUG-039)
**Workaround Only**: 1 (BUG-041 - HANA version limitation)
**Solved**: 30 (see SOLVED_BUGS.md) - BUG-040 VALIDATED 2025-12-22
**Deferred**: 2 (BUG-002, BUG-003)
**SESSION 11 Additions**: BUG-040 ✅ VALIDATED (SUM on NVARCHAR, 127ms), BUG-041 🟠 (IF EXISTS reverted)
**SESSION 9 Additions**: BUG-034 ✅, BUG-035 ✅
**SESSION 10 Additions**: BUG-036 ✅, BUG-037 ✅, BUG-038 ✅, BUG-039 ✅ (awaiting validation)

**By Category**:
- Core IR/Rendering: 2 (BUG-001 ✅, BUG-028 ✅)
- UNION Constant Mapping: 1 (BUG-036 ✅ awaiting validation)
- Parameter Handling: 3 (BUG-002, BUG-003, BUG-026 ✅ VALIDATED)
- Column Mapping: 2 (BUG-004 ✅, BUG-027 ✅ VALIDATED)
- CV References: 4 (BUG-023 ✅ VALIDATED, BUG-025 ✅ VALIDATED, BUG-030 ✅ VALIDATED, BUG-037 ✅ awaiting validation)
- Filter Rendering: 3 (BUG-019, BUG-034 ✅ VALIDATED, BUG-035 ✅ VALIDATED)
- Identifier Quoting: 1 (BUG-029 ✅ VALIDATED)
- Calculated Column Expansion: 2 (BUG-032 ✅ VALIDATED, BUG-033 ✅ VALIDATED)

**By XML**:
- CV_CNCLD_EVNTS: 0 bugs ✅ (clean)
- CV_MCM_CNTRL_Q51: 1 bug (BUG-002 - deferred)
- CV_CT02_CT03: 2 bugs (BUG-003 - deferred, BUG-019 - active)
- CV_INVENTORY_ORDERS: 2 bugs (BUG-001 ✅, BUG-004 ✅)
- CV_ELIG_TRANS_01: 6 bugs (BUG-023 ✅, BUG-025 ✅, BUG-026 ✅, BUG-027 ✅, BUG-028 ✅, BUG-029 ✅ VALIDATED 28ms, BUG-030 ✅ VALIDATED 28ms)
- CV_UPRT_PTLG: 1 bug (BUG-026 ✅ VALIDATED 27ms)
- CV_TOP_PTHLGY: No regression from BUG-029 surgical fix ✅ (201ms)
- CV_INVENTORY_STO: 1 bug (BUG-032 ✅ VALIDATED 59ms) - SESSION 8B
- CV_PURCHASING_YASMIN: 1 bug (BUG-033 ✅ VALIDATED 70ms) - SESSION 8B
- DATA_SOURCES: 2 bugs (BUG-034 ✅ VALIDATED, BUG-035 ✅ VALIDATED) - SESSION 9
- TRANSFORMATIONS: 2 bugs (BUG-036 ✅, BUG-037 ✅ awaiting validation) - SESSION 10

---

## Future Bug Template

```markdown
### BUG-XXX: [Short Description]

**⚠️ IMPORTANT - BUG ID PRESERVATION**:
This bug ID (BUG-XXX) is **PERMANENT** and will follow this bug throughout its lifecycle:
- Code comments during implementation (e.g., "# BUG-XXX: fix reason")
- Git commit messages (e.g., "BUGFIX: BUG-XXX - description")
- Documentation in SOLVED_BUGS.md when resolved (stays as BUG-XXX, NOT renamed to SOLVED-XXX)
- **NEVER change or renumber this ID**

**Status**: 🔴 OPEN | 🟡 IN PROGRESS | ✅ FIXED
**Severity**: Critical | High | Medium | Low
**Discovered**: [XML name] testing
**XML**: [filename]
**Instance Type**: ECC | BW

**Error**:
[HANA error message]

**Problem**:
[SQL snippet showing issue]

**Root Cause**:
[Analysis of why this happens]

**Related Rules**:
- [Link to HANA_CONVERSION_RULES.md rules that relate]

**Impact**:
[Which XMLs/scenarios affected]

**Affected XMLs**:
- List of XMLs with this bug

**Proposed Solution**:
[How to fix]

**Next Steps**:
1. Action items

**Files Modified** (if fixed):
- List of files changed
```

---

**Process**: Every HANA error → Create bug ticket → Map to rules → Implement fix → Document solution

