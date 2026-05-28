# Bug Tracker - HANA Mode Conversion Issues

**Purpose**: Structured tracking of all bugs discovered during HANA mode testing  
**Version**: 2.3.0  
**Last Updated**: 2025-11-13

---

## Active Bugs

### 🔴 BUG-047: Single-Input Union Node Generates Broken Placeholder SQL

**Priority**: High
**Status**: ✅ FIXED - Awaiting HANA Validation (2026-03-03)
**Discovered**: 2026-03-03, ADSO.xml
**XML**: ADSO.xml (and expected: INFOCUBES, MULTIPROVIDERS, COMPOSITE_PROVIDER, INFOSET)

**Error**:
```
SAP DBTech JDBC: [257]: sql syntax error: incorrect syntax near ")": line 75 col 3 (at pos 2590)
```

**Symptom**:
Union node with exactly 1 input generates `SELECT 1 AS placeholder` instead of rendering the single input with its column mappings. The real data CTE (`adso`) is defined but never referenced. The final SELECT queries the placeholder CTE for columns that don't exist in it.

**Generated SQL (broken)**:
```sql
adso AS (
    SELECT ... FROM join_7 LEFT OUTER JOIN projection_9 ...
),
union_1 AS (
    SELECT 1 AS placeholder   ← wrong
)
SELECT INFOCUBE, LASTUSED, TXTLG, SOURCE_TYPE, OBJVERS FROM union_1  ← columns don't exist
```

**Root Cause**:
`_render_union()` in `renderer.py` line 835 had `if len(node.inputs) < 2:` which blocked ALL unions with fewer than 2 inputs, including single-input unions which are a valid SAP BW design pattern. A single-input Union is used to rename columns (ADSONM → INFOCUBE) and inject constant values (SOURCE_TYPE = 'ADSO').

**Fix**:
Changed `if len(node.inputs) < 2:` → `if len(node.inputs) == 0:` at renderer.py line 835.
With `len == 1`, the normal rendering loop runs: produces `SELECT ... FROM adso AS adso` (no UNION keyword since `"\nUNION ALL\n".join([single_query])` = single_query).

**Files Modified**:
- `pipelines/xml-to-sql/src/xml_to_sql/sql/renderer.py` line 835: `< 2` → `== 0`

**Note on [321] DROP VIEW error**:
Also observed: `[321]: invalid view name: ADSO` on DROP VIEW. Likely first-run behavior (view doesn't exist yet; `_SYS_BIC` returns [321] vs [397] for non-existent objects). Not blocking CREATE VIEW. Will confirm after CREATE VIEW succeeds.

---

### 🔴 BUG-048: DECFLOAT Column Engine Function Not Recognized in HANA SQL

**Priority**: High
**Status**: ✅ FIXED - Awaiting HANA Validation (2026-03-03)
**Discovered**: 2026-03-03, ADSO.xml
**XML**: ADSO.xml (and expected in any XML with the Executed_After pattern)

**Error**:
```
SAP DBTech JDBC: [328]: invalid name of function or procedure: DECFLOAT: line 37 col 9 (at pos 1289)
```

**Symptom**:
Column Engine formula `decfloat(format(adddays(now(),-365),'YYYYMMDD') + '000000')` generates SQL with `decfloat(...)` which HANA SQL does not recognize as a function.

**Root Cause**:
`decfloat()` is a SAP Column Engine type-cast function (cast to decimal floating point). It has no direct equivalent function in HANA SQL. `TO_DECIMAL()` is the correct HANA SQL equivalent.

**Fix**:
Added catalog entry to `src/xml_to_sql/catalog/data/functions.yaml`:
```yaml
- name: DECFLOAT
  handler: rename
  target: "TO_DECIMAL"
```
Also mirrored to `catalog/hana/data/functions.yaml` (documentation copy).

**Files Modified**:
- `pipelines/xml-to-sql/src/xml_to_sql/catalog/data/functions.yaml`: Added DECFLOAT → TO_DECIMAL
- `pipelines/xml-to-sql/catalog/hana/data/functions.yaml`: Mirror copy updated

**Action Required**: Reinstall package: `pip install -e .` then reconvert.

---

### 🔴 BUG-049: $$param$$ Placeholders in SingleValueFilter Flattened to Empty String

**Priority**: High
**Status**: ✅ FIXED - Awaiting HANA Validation (2026-03-03)
**Discovered**: 2026-03-03, downstream SQL review (CONVERSION_ISSUES_PROMPT.md ISSUE 1 & 6)
**XML**: ADSO, BEX_QUERIES, COMPOSITE_PROVIDER, DS_3X, DSO, INFOCUBES, INFOOBJECTS, INFOSET, MULTIPROVIDERS, OH_DEST (17 occurrences across 10 files)

**Symptom in output SQL**:
```sql
WHERE SAPABAP1.RSOADSOT.LANGU = ''   -- ← should be 'E' (or '$$Language$$')
```

**Root Cause**:
`_parse_filters()` in `scenario_parser.py` reads `value="$$Language$$"` from a `SingleValueFilter` XML element and stores it as a `LITERAL` expression. When `_render_expression()` renders a LITERAL, it calls `_render_literal()` which simply wraps the value in quotes → `'$$Language$$'`. The parameter cleanup regex (renderer.py lines 1472-1540) then strips the `$$Language$$` content from *inside* the quotes, leaving `''`. The `_substitute_placeholders()` function that correctly resolves parameters from `localVariables` is only called for `RAW` expressions, never for `LITERAL` expressions.

The defaultValue from `<localVariables>` (`defaultValue="E"`) IS correctly parsed and stored in `ctx.scenario.variables` — it's just never applied to the filter literal.

**Fix** (renderer.py `_render_expression()`, LITERAL branch):
Add a helper `_resolve_parameter_literal(value, ctx)` that checks if the value contains `$$...$$` and substitutes from `ctx.scenario.variables`. Call it before `_render_literal()`.

**Files to Modify**:
- `pipelines/xml-to-sql/src/xml_to_sql/sql/renderer.py`: Add `_resolve_parameter_literal()`, call in LITERAL branch (~line 1071)

**Resolution**: Use `defaultValue` from XML `localVariables` (option A — clean SQL, no noise).

**Affects**: 17 occurrences, 10 files. ISSUE 6 (`$$colname$$` → `''`) has the same root cause but result stays `''` (defaultValue IS empty string) — correct by coincidence but now derived properly.

---

### 🔴 BUG-050: Node-Level `<filter>` Elements on ProjectionView/JoinView Silently Dropped

**Priority**: Medium
**Status**: ✅ FIXED - Awaiting HANA Validation (2026-03-03)
**Discovered**: 2026-03-03, downstream SQL review (CONVERSION_ISSUES_PROMPT.md ISSUE 3)
**XML**: ADSO, BEX_QUERIES, COMPOSITE_PROVIDER, INFOCUBES, INFOSET, MULTIPROVIDERS, TRANFORMATIONS, TRANSFORMATIONS_DETAILS, TRANSFORMATIONS_FIELDS_MAPPING

**Symptom**:
RSZCOMPDIR projection CTEs (and ZDTP_TRFN projections) missing their `WHERE OBJVERS = 'A'` filter. The source XML has the filter, but the SQL output omits it.

**Root Cause**:
`_parse_projection()` in `scenario_parser.py` calls `_parse_filters()` which ONLY loops through `<viewAttribute>` child elements looking for nested `<filter>` sub-elements. The bare `<filter>` element that is a direct child of the `calculationView` node is never read:
```xml
<calculationView xsi:type="Calculation:ProjectionView" id="Projection_2" filterExpressionLanguage="COLUMN_ENGINE">
  ...
  <filter>(&quot;OBJVERS&quot; ='A')</filter>   ← COMPLETELY IGNORED
</calculationView>
```

**Fix** (`_parse_projection()` in `scenario_parser.py`):
After calling `_parse_filters()`, also check for a bare `<filter>` child of the node element. If found, parse its text content as a `Predicate(kind=PredicateKind.RAW, ...)` and append to `filters`.

**Files to Modify**:
- `pipelines/xml-to-sql/src/xml_to_sql/parser/scenario_parser.py`: Add bare `<filter>` parsing in `_parse_projection()` (~line 307)

---

### 🔴 BUG-053: Integer-Declared Calc Columns Returning String Literals Break Downstream SUM/AVG

**Priority**: High
**Status**: ✅ VALIDATED in HANA (2026-05-10, CREATE VIEW: 75ms)
**Discovered**: 2026-05-10, CV_E2E_VST.xml (Maccabi BW_ON_HANA)
**XML**: CV_E2E_VST.xml (and any XML with integer calc columns whose formula returns string literals)

**Error**:
```
SAP DBTech JDBC: [266]: inconsistent datatype: only numeric type is available for SUM/AVG/STDDEV/VAR function: line 677 col 9
```

**Symptom**:
Calculated column declared as `<inlineType primitiveType="SMALLINT"/>` has formula returning string literals:
```xml
<element name="CC_PATTEST" aggregationBehavior="NONE">
  <inlineType primitiveType="SMALLINT"/>
  <calculationDefinition language="COLUMN_ENGINE">
    <formula>if("_BIC_EYHERAZ01"='0000001115','1','0')</formula>
  </calculationDefinition>
</element>
```
HANA Column Engine auto-coerces the strings `'1'`/`'0'` to SMALLINT, but standard SQL doesn't. Downstream `SUM(CC_PATTEST)` fails because the actual SQL data type is VARCHAR, not integer.

**Generated SQL (before fix)**:
```sql
CASE WHEN ... THEN '1' ELSE '0' END AS CC_PATTEST     -- VARCHAR result
SUM(CC_PATTEST)                                        -- ERROR [266]
```

**Generated SQL (after fix)**:
```sql
TO_INTEGER(CASE WHEN ... THEN '1' ELSE '0' END) AS CC_PATTEST   -- INTEGER result
SUM(CC_PATTEST)                                                  -- works
```

**Root Cause**:
Renderer outputs the CASE WHEN formula as-is. The XML's declared SMALLINT type is ignored at the calc column level — only used for output schema documentation. The actual SQL output type is determined by the formula's literals.

**Fix**:
When `calc_attr.data_type.type.value == "NUMBER" AND scale == 0` (i.e., integer-class declared type), wrap the rendered expression with `TO_INTEGER()` in HANA mode. This:
- Aligns actual SQL type with declared type
- Coerces string literals `'1'`, `'0'` to integers `1`, `0`
- Is a safe no-op cast for already-numeric values
- Same pattern as BUG-040 but applied at calc column level instead of SUM/AVG level

**Files Modified**:
- `pipelines/xml-to-sql/src/xml_to_sql/sql/renderer.py`: 3 locations (projection ~449, JOIN ~671, aggregation ~845) — added `elif` branch wrapping integer-typed calc columns with `TO_INTEGER()`

**Scope**: UNIVERSAL — any XML with calc columns declared as SMALLINT/INTEGER/BIGINT/TINYINT.

---

### 🔴 BUG-051: BOOLEAN Calculated Columns Rendered as Bare Expressions in SELECT

**Priority**: High
**Status**: ✅ FIXED - Awaiting HANA Validation (2026-03-26)
**Discovered**: 2026-03-26, TRANFORMATIONS.xml
**XML**: TRANFORMATIONS.xml (and any XML with `datatype="BOOLEAN"` calculated columns)

**Error**:
```
SAP DBTech JDBC: [257]: sql syntax error: incorrect syntax near "=": line 35 col 39 (at pos 1301)
```

**Symptom**:
Calculated column with `datatype="BOOLEAN"` renders a bare boolean expression in SELECT:
```sql
LEFT(TABLE.LINE, 1)='*' or LEFT(TABLE.LINE, 5) = '... "' AS COMMENTS
```
HANA SQL doesn't support bare boolean expressions in SELECT — they must be wrapped.

**Root Cause**:
XML `<calculatedViewAttribute datatype="BOOLEAN">` has a formula that evaluates to true/false.
The renderer outputs the formula as-is, but HANA SQL requires `CASE WHEN (...) THEN 1 ELSE 0 END`.

**Fix**:
Added BOOLEAN datatype detection in all 3 calculated column rendering paths in `renderer.py`:
- Line 443-448 (projection path)
- Line 657-661 (JOIN path)
- Line 825-829 (aggregation path)
When `calc_attr.data_type.type.value == "BOOLEAN"` and HANA mode, wraps in `CASE WHEN (...) THEN 1 ELSE 0 END`.

**Files Modified**:
- `pipelines/xml-to-sql/src/xml_to_sql/sql/renderer.py`: Lines 443-448, 657-661, 825-829

---

### 🔴 BUG-052: SqlScriptView Nodes Generate Placeholder Instead of Embedded SQL

**Priority**: High
**Status**: ✅ FIXED - Awaiting HANA Validation (2026-03-26)
**Discovered**: 2026-03-26, USED_HIERARCHIES.xml
**XML**: USED_HIERARCHIES.xml (and any `calculationScenarioType="SCRIPT_BASED"` views)

**Error**:
```
SAP DBTech JDBC: [257]: sql syntax error: incorrect syntax near ")": line 5 col 3 (at pos 104)
```
(Plus [362]: invalid schema name: SAPK5D on MBD system)

**Symptom**:
Script-based calculation views with `xsi:type="Calculation:SqlScriptView"` generate:
```sql
script_view AS (
    SELECT 1 AS placeholder
)
```
Instead of using the embedded SQL from the `<definition>` element.

**Root Cause**:
1. `SqlScriptView` falls into the `else` branch in parser (treated as generic CALCULATION node)
2. The `<definition>` element containing the SQL procedure body is never parsed
3. `_render_calculation()` returns placeholder for nodes with no inputs

**Fix** (three parts):
1. **Model** (`models.py`): Added `default_schema` field to `ScenarioMetadata`
2. **Parser** (`scenario_parser.py`): Extract `<definition>` text into `node.properties["script_definition"]`; parse `<defaultSchema schemaName="..."/>` into metadata
3. **Renderer** (`renderer.py`): New `_extract_select_from_script()` helper extracts SELECT from procedure body, resolves `defaultSchema` through `schema_overrides`, and replaces hardcoded schemas automatically

**Auto Schema Resolution**:
- XML has `<defaultSchema schemaName="ABAP"/>`
- `schema_overrides` maps `ABAP → SAPABAP1`
- Detects `"SAPK5D"` in script FROM clauses → auto-replaces with `"SAPABAP1"`
- No manual config entry needed for hardcoded schemas

**Files Modified**:
- `pipelines/xml-to-sql/src/xml_to_sql/domain/models.py`: Added `default_schema` to ScenarioMetadata
- `pipelines/xml-to-sql/src/xml_to_sql/parser/scenario_parser.py`: Lines 99-104, 255-260
- `pipelines/xml-to-sql/src/xml_to_sql/sql/renderer.py`: Lines 953-957, 1309-1349

---

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
- `pipelines/xml-to-sql/src/xml_to_sql/sql/renderer.py`: Lines 1383-1491 (_cleanup_hana_parameter_conditions function)
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
- `pipelines/xml-to-sql/src/xml_to_sql/web/services/converter.py`: Lines 312-319 (removed package path logic)

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
- `pipelines/xml-to-sql/src/xml_to_sql/sql/renderer.py`: Lines 942-970 (_render_from function)
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
- `pipelines/xml-to-sql/src/xml_to_sql/sql/renderer.py`: Lines 996-1007 (_render_expression function)
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
- `pipelines/xml-to-sql/src/xml_to_sql/sql/renderer.py`: Lines 298-313 (_topological_sort function)
  - Changed from `lstrip("#")` to proper `_clean_ref()` + regex normalization
  - Added imports for `_clean_ref` and `re`

**Next Steps**:
1. ⏳ Awaiting CV_ELIG_TRANS_01 final validation with BUG-028 fix
2. Document in HANA_CONVERSION_RULES.md
3. Move to SOLVED_BUGS.md if successful

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

### 🟡 BUG-042: String Concatenation + Operator Causes Invalid Number Error in HANA SQL

**⚠️ IMPORTANT - BUG ID PRESERVATION**:
This bug ID (BUG-042) is **PERMANENT** and will follow this bug throughout its lifecycle.

**Priority**: Critical
**Status**: ✅ VALIDATED IN HANA (2025-02-24) — moved to SOLVED_BUGS.md
**Discovered**: 2025-02-24, TRANSFORMATIONS_DETAILS.xml
**XML**: TRANSFORMATIONS_DETAILS.xml
**Instance Type**: BW (SAPABAP1)

**Error**:
```
SAP DBTech JDBC: [339]: invalid number: not a valid number string ''
```

**Problem**:
```sql
-- Line 239 of generated SQL:
ELSE '/BIC/'+(projection_2.PARAMNM) END AS FIELDNM
--          ^ WRONG: + is arithmetic only in HANA SQL
```

**Root Cause**:
The `_translate_string_concat_to_hana()` function in `function_translator.py` was **backwards** — it converted `||` to `+`, assuming HANA uses `+` for string concatenation. This is WRONG:
- **Column Engine** (XML formulas): Uses `+` for string concatenation
- **HANA SQL** (CREATE VIEW): Uses `||` for string concatenation, `+` is arithmetic only

The XML formula `'/BIC/'+"PARAMNM"` stayed as `+` in the output SQL, causing HANA to attempt arithmetic conversion of strings to numbers.

**Solution Implemented**:
Reversed the function to convert `+` to `||` when adjacent to string literals:

```python
# BUG-042 FIX in function_translator.py lines 594-611:
def _translate_string_concat_to_hana(formula: str) -> str:
    result = formula
    # Pattern: 'string' + something → 'string' || something
    result = re.sub(r"'\s*\+\s*", "' || ", result)
    # Pattern: something + 'string' → something || 'string'
    result = re.sub(r"\s*\+\s*'", " || '", result)
    return result
```

**Result - CORRECT**:
```sql
ELSE '/BIC/' || (projection_2.PARAMNM) END AS FIELDNM
```

**Regression Risk**: ZERO — no validated SQL files contain `||` or string `+` concatenation.

**Files Modified**:
- `pipelines/xml-to-sql/src/xml_to_sql/sql/function_translator.py`: Lines 594-611 (_translate_string_concat_to_hana function)

**Next Steps**:
1. Restart server / reinstall package
2. Re-convert TRANSFORMATIONS_DETAILS.xml
3. Test in HANA (skip DROP, run CREATE only)

---

### 🟡 BUG-043: UNION ALL Empty String '' Causes Type Conversion Error with INTEGER Columns

**⚠️ IMPORTANT - BUG ID PRESERVATION**:
This bug ID (BUG-043) is **PERMANENT** and will follow this bug throughout its lifecycle.

**Priority**: Critical
**Status**: ✅ VALIDATED IN HANA (2025-02-24) — moved to SOLVED_BUGS.md
**Discovered**: 2025-02-24, TRANSFORMATIONS_DETAILS.xml
**XML**: TRANSFORMATIONS_DETAILS.xml
**Instance Type**: BW (SAPABAP1)

**Error**:
```
SAP DBTech JDBC: [339]: invalid number: not a valid number string ''
```

**Problem**:
```sql
-- UNION ALL branches pad missing columns with empty strings:
SELECT ... '' AS LINE_NO, '' AS MD_MPER, ... FROM others_type
UNION ALL
SELECT ... routine_type.LINE_NO AS LINE_NO, ... FROM routine_type
-- If LINE_NO is INTEGER in the source table, HANA type resolution
-- tries to convert '' to INTEGER → fails with [339]
```

**Root Cause**:
The XML uses `ConstantAttributeMapping` with `null="true"` attribute to pad UNION branches:
```xml
<mapping xsi:type="Calculation:ConstantAttributeMapping" target="LINE_NO" null="true" value=""/>
```

The `null="true"` means "this column should be NULL in this UNION branch". But the parser (BUG-036 fix) ignored the `null` attribute and always created `Expression(LITERAL, "")`, rendering as `''`.

In HANA UNION ALL, type resolution uses TYPE PRECEDENCE — if any branch has an INTEGER column, the result type becomes INTEGER. Then `''` in other branches must be converted to INTEGER, failing on empty string.

**Solution Implemented**:
Two surgical changes:

**Change 1** — Parser: Check `null="true"` attribute (scenario_parser.py lines 421-425):
```python
# BUG-043: Check null="true" attribute — render as SQL NULL, not empty string ''
null_flag = mapping_el.get("null", "false").lower() == "true"
if null_flag and not constant_value:
    expr = Expression(ExpressionType.RAW, "NULL")
else:
    data_type = guess_attribute_type(target)
    expr = Expression(ExpressionType.LITERAL, constant_value, data_type)
```

**Change 2** — Renderer: Prevent BUG-027 from qualifying NULL keyword (renderer.py line 1080-1082):
```python
# BUG-043: Don't qualify SQL keywords (NULL, TRUE, FALSE) — they are literals, not columns
if table_alias and result.strip('"').isidentifier() and not '(' in result:
    if result.upper() not in ('NULL', 'TRUE', 'FALSE'):
        return f"{table_alias}.{result}"
```

**Result - CORRECT**:
```sql
-- Before (broken):
SELECT ... '' AS LINE_NO, '' AS MD_MPER, ... FROM others_type

-- After (fixed):
SELECT ... NULL AS LINE_NO, NULL AS MD_MPER, ... FROM others_type
```

`NULL` is type-compatible with any column type in UNION ALL.

**Regression Risk**: VERY LOW — only affects ConstantAttributeMapping entries with `null="true"` + empty value. None of the 15 validated XMLs in GOLDEN_COMMIT use this pattern.

**Files Modified**:
- `src/xml_to_sql/parser/scenario_parser.py`: Lines 421-425 (_parse_mappings function)
- `src/xml_to_sql/sql/renderer.py`: Lines 1080-1082 (_render_expression function)

**Next Steps**:
1. Restart server / reinstall package
2. Re-convert TRANSFORMATIONS_DETAILS.xml
3. Test in HANA (skip DROP, run CREATE only)

---

### ✅ BUG-044: RIGHTSTRU / LEFTSTRU Unicode Functions Not Recognized in HANA SQL

**⚠️ IMPORTANT - BUG ID PRESERVATION**:
This bug ID (BUG-044) is **PERMANENT** and will follow this bug throughout its lifecycle.

**Priority**: Medium
**Status**: ✅ VALIDATED in HANA (2025-02-26)
**Discovered**: 2025-02-26, INFOOBJECTS.xml
**XML**: INFOOBJECTS.xml
**Instance Type**: BW (SAPABAP1)

**Error**:
```
SAP DBTech JDBC: [328]: invalid name of function or procedure: RIGHTSTRU: line 12 col 110 (at pos 545)
```

**Problem**:
```sql
-- Line 13 of generated SQL:
'/BI0/OI' || rightstru(SAPABAP1.RSDKYF.KYFNM, (LENGTH(...))-1)
--           ^^^^^^^^^ HANA doesn't recognize this function
```

**Root Cause**:
`rightstru()` and `leftstru()` are Unicode-aware variants of `rightstr()` and `leftstr()` from SAP Column Engine. The function catalog had mappings for `RIGHTSTR` → `RIGHT` and `LEFTSTR` → `LEFT`, but was missing the Unicode variants.

HANA SQL's `RIGHT()` and `LEFT()` functions already handle Unicode (NVARCHAR) natively.

**⚠️ LESSON LEARNED — DUPLICATE CATALOG FILES**:
Initial fix was applied to the WRONG file (`catalog/hana/data/functions.yaml`) instead of the CORRECT file (`src/xml_to_sql/catalog/data/functions.yaml`). The Python package loads from `xml_to_sql.catalog.data` (the `src/` path), NOT from `catalog/hana/data/`.

**Solution Implemented**:
Added two entries to `src/xml_to_sql/catalog/data/functions.yaml`:
```yaml
- name: LEFTSTRU
  handler: rename
  target: "LEFT"

- name: RIGHTSTRU
  handler: rename
  target: "RIGHT"
```

**Files Modified**:
- `src/xml_to_sql/catalog/data/functions.yaml`: Added LEFTSTRU and RIGHTSTRU mappings
- `catalog/hana/data/functions.yaml`: Also added (mirror copy for documentation)

**Next Steps**:
1. Reinstall: `pip install -e .`
2. Re-convert INFOOBJECTS.xml
3. Test in HANA (skip DROP, run CREATE only)

---

## Bug Statistics

**Total Bugs Tracked**: 53
**Open**: 1 (BUG-019)
**Fixed - Awaiting Validation**: 6 (BUG-036, BUG-037, BUG-038, BUG-039, BUG-049, BUG-050)
**Workaround Only**: 1 (BUG-041 - HANA version limitation)
**Solved**: 40 (see SOLVED_BUGS.md) - BUG-053 VALIDATED 2026-05-10 (CV_E2E_VST.xml, 75ms)
**Deferred**: 2 (BUG-002, BUG-003)
**SESSION 16 Additions**: BUG-053 ✅ VALIDATED (Integer calc columns → TO_INTEGER wrap, CV_E2E_VST.xml 75ms)
**SESSION 15 Additions**: BUG-051 ✅ VALIDATED (BOOLEAN calc columns → CASE WHEN), BUG-052 ✅ VALIDATED (SqlScriptView + auto schema resolution)
**SESSION 14 Additions**: BUG-047 ✅ VALIDATED, BUG-048 ✅ VALIDATED, BUG-049 ✅ FIXED (awaiting validation), BUG-050 ✅ FIXED (awaiting validation)
**SESSION 13 Additions**: BUG-046 ✅ VALIDATED (case() function → CASE WHEN, INFOOBJECTS.xml 51ms)
**SESSION 12 Additions**: BUG-042 ✅, BUG-043 ✅, BUG-044 ✅, BUG-045 ✅ (BUG-043 regression fix)
**SESSION 11 Additions**: BUG-040 ✅ VALIDATED (SUM on NVARCHAR, 127ms), BUG-041 🟠 (IF EXISTS reverted)
**SESSION 9 Additions**: BUG-034 ✅, BUG-035 ✅
**SESSION 10 Additions**: BUG-036 ✅, BUG-037 ✅, BUG-038 ✅, BUG-039 ✅ (awaiting validation)

**By Category**:
- Core IR/Rendering: 2 (BUG-001 ✅, BUG-028 ✅)
- UNION Constant Mapping: 3 (BUG-036 ✅ awaiting validation, BUG-043 ✅ VALIDATED, BUG-045 ✅ SOLVED - BUG-043 regression)
- Union Node Rendering: 1 (BUG-047 ✅ VALIDATED - single-input Union pass-through)
- Parameter Resolution: 1 (BUG-049 ✅ FIXED awaiting validation - $$param$$ flattened to '' in filters)
- Node-Level Filter Parsing: 1 (BUG-050 ✅ FIXED awaiting validation - bare <filter> on ProjectionView dropped)
- Parameter Handling: 3 (BUG-002, BUG-003, BUG-026 ✅ VALIDATED)
- Column Mapping: 2 (BUG-004 ✅, BUG-027 ✅ VALIDATED)
- CV References: 4 (BUG-023 ✅ VALIDATED, BUG-025 ✅ VALIDATED, BUG-030 ✅ VALIDATED, BUG-037 ✅ awaiting validation)
- Filter Rendering: 3 (BUG-019, BUG-034 ✅ VALIDATED, BUG-035 ✅ VALIDATED)
- Identifier Quoting: 1 (BUG-029 ✅ VALIDATED)
- Calculated Column Expansion: 2 (BUG-032 ✅ VALIDATED, BUG-033 ✅ VALIDATED)
- String Concatenation: 1 (BUG-042 ✅ VALIDATED)
- Function Catalog: 2 (BUG-044 ✅ VALIDATED, BUG-048 ✅ VALIDATED - DECFLOAT→TO_DECIMAL)
- Boolean Expression Rendering: 1 (BUG-051 ✅ VALIDATED - BOOLEAN calc columns need CASE WHEN)
- Script View Support: 1 (BUG-052 ✅ VALIDATED - SqlScriptView definition extraction + auto schema resolution)
- Integer Type Coercion: 1 (BUG-053 ✅ VALIDATED - integer calc columns need TO_INTEGER wrap)

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
- TRANSFORMATIONS_DETAILS: 2 bugs (BUG-042 ✅ VALIDATED, BUG-043 ✅ VALIDATED) - SESSION 12
- INFOOBJECTS: 2 bugs (BUG-044 ✅ VALIDATED, BUG-046 ✅ VALIDATED) - SESSION 12/13
- DSO: 1 bug (BUG-045 ✅ SOLVED - awaiting HANA validation) - SESSION 12
- ADSO: 2 bugs (BUG-047 ✅ VALIDATED, BUG-048 ✅ VALIDATED) - SESSION 14
- TRANFORMATIONS: 1 bug (BUG-051 ✅ VALIDATED - BOOLEAN calc column) - SESSION 15
- USED_HIERARCHIES: 1 bug (BUG-052 ✅ VALIDATED - SqlScriptView + auto schema resolution) - SESSION 15
- CV_E2E_VST: 1 bug (BUG-053 ✅ VALIDATED 75ms - integer calc columns w/ string-literal formulas) - SESSION 16

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

