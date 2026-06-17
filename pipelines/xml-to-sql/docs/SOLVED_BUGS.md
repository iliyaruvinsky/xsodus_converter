# Solved Bugs - HANA Mode Conversion

**Purpose**: Archive of resolved bugs with solutions and rule associations  
**Version**: 2.3.0

---

## Template

Each solved bug documents:
1. Original error and symptoms
2. Root cause analysis
3. Solution implemented
4. Code changes made
5. Associated conversion rules
6. Validation status

---

## Note on Bug Numbering System

**Historical bugs (BUG-001 through BUG-028)**:
During initial documentation organization (November 2025), bugs were renumbered when moved to solved status, creating separate BUG-XXX and SOLVED-XXX sequences. This historical practice created:
- Active bugs with BUG-XXX IDs (e.g., BUG-005, BUG-009)
- Corresponding solved entries with SOLVED-XXX IDs (e.g., SOLVED-001, SOLVED-006)
- Gaps in SOLVED numbering (missing SOLVED-009, 010, 018-020, 023-026)

These historical IDs (BUG-001 through BUG-028, SOLVED-001 through SOLVED-028) remain **UNCHANGED** for historical reference and traceability.

**Future bugs (BUG-029 onwards)**:
Starting with BUG-029, the dual numbering system is **DEPRECATED**. All future bugs:
- Keep their original BUG-XXX identifier throughout their entire lifecycle
- Are documented with BUG-XXX in code comments (e.g., "# BUG-029: fix reason")
- Are referenced with BUG-XXX in git commits (e.g., "BUGFIX: BUG-029 - description")
- Are moved to this file with their original BUG-XXX ID (NOT renumbered to SOLVED-XXX)

**Example**: BUG-029 discovered → BUG-029 in code → BUG-029 in commits → **BUG-029** in this document (not SOLVED-029)

**Traceability**: This ensures code comments, git commits, and documentation all reference the same immutable bug ID.

---

## Resolved Issues

### SOLVED-027: Calculation View ResourceUri - Strip Internal Paths

**Original Bug**: BUG-027
**Discovered**: 2025-11-20, KMDM_Materials.XML
**Resolved**: 2025-11-20

**Error**:
```
SAP DBTech JDBC: [257]: sql syntax error: Could not find table/view /KMDM/calculationviews/MATERIAL_DETAILS in schema _SYS_BIC
Could not find table/view /KMDM/Sold_Materials in schema _SYS_BIC
```

**Problem**:
Generated SQL referenced calculation views with incorrect paths:
```sql
-- WRONG - includes /calculationviews/ and leading /
FROM "/KMDM/calculationviews/MATERIAL_DETAILS"
FROM "/KMDM/Sold_Materials"

-- CORRECT - clean package/view path
FROM "KMDM/MATERIAL_DETAILS"
FROM "KMDM/Sold_Materials"
```

**Root Cause**:
In `scenario_parser.py` line 128, XML `<resourceUri>` was used directly as `object_name`:
- XML contains: `/KMDM/calculationviews/MATERIAL_DETAILS`
- `/calculationviews/` is an internal HANA Studio XML organization folder
- Leading `/` is part of XML path format but not SQL reference format
- Both needed to be stripped for correct SQL generation

**Solution**:
Modified `scenario_parser.py` lines 128-137 to strip internal folders and leading slash:

```python
if resource_uri:
    # BUG-027: Strip internal HANA Studio folder paths from resourceUri
    # These folders (/calculationviews/, /analyticviews/, /attributeviews/) are
    # XML organization folders in HANA Studio, not part of the actual view path
    # Example: /KMDM/calculationviews/MATERIAL_DETAILS -> KMDM/MATERIAL_DETAILS
    object_name = resource_uri
    for internal_folder in ['/calculationviews/', '/analyticviews/', '/attributeviews/']:
        object_name = object_name.replace(internal_folder, '/')
    # Strip leading slash - resourceUri paths start with / but SQL references don't
    if object_name.startswith('/'):
        object_name = object_name[1:]
```

**Files Modified**:
- `src/xml_to_sql/parser/scenario_parser.py` (lines 128-137)

**Transformation**:
```
Input:  /KMDM/calculationviews/MATERIAL_DETAILS
Output: KMDM/MATERIAL_DETAILS

Input:  /Macabi_BI/analyticviews/CV_ANALYSIS
Output: Macabi_BI/CV_ANALYSIS
```

**Impact**:
- Affects ALL XMLs with `type="CALCULATION_VIEW"` data sources
- KMDM_Materials.XML: Fixed 6 calculation view references
- Critical for any XML referencing other calculation views

**Validation**:
- ✅ KMDM_Materials.XML regenerated successfully
- ✅ All 6 CV references now correct (no /calculationviews/, no leading /)
- ✅ SQL syntax validated in generated output

**Related Rules**: New pattern - ResourceUri path normalization

---

### SOLVED-001: ColumnView JOIN Node Parsing

**Original Bug**: BUG-005  
**Discovered**: 2025-11-13, CV_INVENTORY_ORDERS.xml  
**Resolved**: 2025-11-13

**Error**:
```
invalid column name: PROJECTION_6.EINDT (should be projection_8.EINDT)
```

**Problem**:
ColumnView JOINs were not being parsed as JoinNode objects - they fell through to generic Node type, missing JOIN-specific parsing (join conditions, left/right input tracking).

**Root Cause**:
`column_view_parser.py` had handlers for Projection, Aggregation, Union but NOT for JoinNode. ColumnView JOIN nodes (`xsi:type="View:JoinNode"`) were falling through to the catchall generic Node handler.

**Solution**:
Added JoinNode parsing to ColumnView parser:

```python
if node_type.endswith("JoinNode"):
    join_type = _parse_join_type(node_el)
    join_conditions = _parse_join_conditions(node_el, inputs)
    return JoinNode(...)

def _parse_join_type(node_el):
    # Extract from <join joinType="inner">

def _parse_join_conditions(node_el, inputs):
    # Extract from <leftElementName> and <rightElementName>
```

**Files Modified**:
- `src/xml_to_sql/parser/column_view_parser.py` - Lines 174-192 (JoinNode handler), 340-392 (helper functions)

**Related Rules**: None (parser fix, not transformation rule)

**Validation**: ✅ CV_INVENTORY_ORDERS now creates proper JoinNode, renders with correct INNER JOIN syntax

---

### SOLVED-002: JOIN Column Resolution - Source Node Tracking

**Original Bug**: BUG-006  
**Discovered**: 2025-11-13, CV_INVENTORY_ORDERS.xml  
**Resolved**: 2025-11-13

**Error**:
```
invalid column name: PROJECTION_6.EINDT (EINDT is in projection_8, not projection_6)
```

**Problem**:
JOIN nodes with multiple inputs (leftInput, rightInput) were using wrong CTE alias for columns from right input.

**SQL Before**:
```sql
SELECT 
    projection_6.EINDT AS EINDT  -- WRONG: EINDT from projection_8
FROM projection_6
INNER JOIN projection_8 ...
```

**SQL After**:
```sql
SELECT 
    projection_8.EINDT AS EINDT  -- CORRECT
FROM projection_6
INNER JOIN projection_8 ...
```

**Root Cause**:
JOIN renderer already had `source_node` logic (lines 547-554) but ColumnView parser wasn't setting `source_node` in mappings properly due to SOLVED-001 (JoinNode not being created).

**Solution**:
Once JoinNode parsing was fixed (SOLVED-001), the existing renderer logic worked correctly.

**Files Modified**:
- `src/xml_to_sql/parser/column_view_parser.py` (via SOLVED-001 fix)

**Related Rules**: None (core rendering logic)

**Validation**: ✅ join_6 now correctly uses projection_8.EINDT, projection_8.WEMNG

---

### SOLVED-003: Filter Alias vs Source Name Mapping

**Original Bug**: BUG-004  
**Discovered**: 2025-11-13, CV_INVENTORY_ORDERS.xml  
**Resolved**: 2025-11-13

**Error**:
```
SAP DBTech JDBC: [260]: invalid column name: LOEKZ_EKPO: line 67 col 12
```

**Problem**:
Filters referenced target/alias column names instead of source column names when querying base tables.

**SQL Before**:
```sql
SELECT SAPABAP1."/BIC/AZEKPO2".LOEKZ AS LOEKZ_EKPO ...
WHERE ("LOEKZ_EKPO" ='')  -- ERROR: alias doesn't exist
```

**SQL After**:
```sql
SELECT SAPABAP1."/BIC/AZEKPO2".LOEKZ AS LOEKZ_EKPO ...
WHERE ("LOEKZ" ='')  -- FIXED: source column name
```

**Root Cause**:
- XML filters use element names: `<element name="LOEKZ_EKPO">` with `<filterExpression>"LOEKZ_EKPO" = ''</filterExpression>`
- But mappings show: `targetName="LOEKZ_EKPO" sourceName="LOEKZ"`
- SQL WHERE can't use aliases, needs actual column names

**Solution**:
Build target→source mapping from node.mappings and replace in WHERE clause.

**Code Changes**:
File: `src/xml_to_sql/sql/renderer.py`  
Function: `_render_projection()`  
Lines: 419-439

```python
# Build target→source name mapping
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

**Associated Rules**:
- **Created**: Rule #12 - Filter Source Mapping
- **Priority**: 25
- **Category**: Column name resolution

**Validation**: ✅ WHERE now uses source column names

---

### SOLVED-004: Aggregation Calculated Columns

**Original Bug**: BUG-007  
**Discovered**: 2025-11-13, CV_INVENTORY_ORDERS.xml  
**Resolved**: 2025-11-13

**Error**:
```
invalid column name: JOIN_4.MONTH (MONTH is calculated, not in join_4)
```

**Problem**:
Aggregation nodes with calculated columns (MONTH, YEAR) weren't rendering them - treating them as passthrough from input.

**Root Cause**:
`_render_aggregation()` only rendered:
- Group by columns
- Aggregation specs (SUM, COUNT, etc.)

But NOT `node.calculated_attributes`.

**Solution**:
Added calculated column rendering to aggregations:

```python
# Add calculated columns (computed in outer query after grouping)
for calc_name, calc_attr in node.calculated_attributes.items():
    calc_expr = _render_expression(ctx, calc_attr.expression, "agg_inner")
    outer_select.append(f"{calc_expr} AS {_quote_identifier(calc_name)}")
```

**Files Modified**:
- `src/xml_to_sql/sql/renderer.py::_render_aggregation()` - Lines 658-673

**Validation**: ✅ MONTH and YEAR now computed with SUBSTRING formulas

---

### SOLVED-005: GROUP BY Source Expression Mapping

**Original Bug**: BUG-008  
**Discovered**: 2025-11-13, CV_INVENTORY_ORDERS.xml  
**Resolved**: 2025-11-13

**Error**:
```
invalid column name: JOIN_4.WAERS_EKKO (GROUP BY uses alias, should use source)
```

**Problem**:
GROUP BY used output alias names (WAERS_EKKO) but aliases are created in same SELECT - can't reference them.

**SQL Before**:
```sql
SELECT join_4.WAERS AS WAERS_EKKO, ...
GROUP BY WAERS_EKKO  -- ERROR: alias doesn't exist yet
```

**SQL After**:
```sql
SELECT join_4.WAERS AS WAERS_EKKO, ...
GROUP BY join_4.WAERS  -- FIXED: source column
```

**Root Cause**:
`node.group_by` contains output column names, but GROUP BY needs to reference the source columns from the input CTE.

**Solution**:
Map GROUP BY column names through node.mappings to get source expressions:

```python
target_to_expr_map = {}
for mapping in node.mappings:
    target_to_expr_map[mapping.target_name.upper()] = mapping.expression

for col_name in node.group_by:
    if col_name.upper() in target_to_expr_map:
        expr = target_to_expr_map[col_name.upper()]
        group_by_cols.append(_render_expression(ctx, expr, from_clause))
```

**Files Modified**:
- `src/xml_to_sql/sql/renderer.py::_render_aggregation()` - Lines 588-603

**Validation**: ✅ GROUP BY now uses `join_4.WAERS`, `join_4.EINDT` (source columns)

---

### SOLVED-006: Aggregation Spec Source Mapping

**Original Bug**: BUG-009  
**Discovered**: 2025-11-13, CV_INVENTORY_ORDERS.xml  
**Resolved**: 2025-11-13

**Error**:
```
invalid column name: JOIN_4.WEMNG_EKET (aggregation spec uses renamed column)
```

**Problem**:
Aggregation specs trying to aggregate renamed columns instead of source columns.

**SQL Before**:
```sql
SELECT join_4.WEMNG AS WEMNG_EKET, ...
    SUM(join_4.WEMNG_EKET) AS ...  -- ERROR: WEMNG_EKET doesn't exist
```

**SQL After**:
```sql
SELECT join_4.WEMNG AS WEMNG_EKET, ...
    SUM(join_4.WEMNG) AS WEMNG_EKET  -- FIXED: source column
```

**Root Cause**:
Aggregation specs referenced column names, but if those columns were renamed in mappings, the specs used the new name instead of the original.

**Solution**:
Map aggregation spec column names through mappings to get source expressions:

```python
target_to_source_expr = {}
for mapping in node.mappings:
    target_to_source_expr[mapping.target_name.upper()] = mapping.expression

for agg_spec in node.aggregations:
    if agg_spec.expression.expression_type == ExpressionType.COLUMN:
        col_name = agg_spec.expression.value
        if col_name.upper() in target_to_source_expr:
            agg_expr = _render_expression(ctx, target_to_source_expr[col_name.upper()], from_clause)
```

**Files Modified**:
- `src/xml_to_sql/sql/renderer.py::_render_aggregation()` - Lines 611-631

**Validation**: ✅ SUM(join_4.WEMNG), SUM(join_4.MENGE) use source names

---

### SOLVED-007: Aggregation Subquery Wrapping

**Original Bug**: BUG-010  
**Discovered**: 2025-11-13, CV_INVENTORY_ORDERS.xml  
**Resolved**: 2025-11-13

**Error**:
```
invalid column name: MONTH (calculated column in GROUP BY of same SELECT)
```

**Problem**:
Calculated columns in aggregations were in GROUP BY of same SELECT that computes them.

**SQL Before**:
```sql
SELECT 
    ...,
    SUBSTRING("AEDAT_EKKO", 1, 6) AS MONTH
GROUP BY MONTH  -- ERROR: MONTH doesn't exist yet
```

**SQL After**:
```sql
SELECT
    agg_inner.*,
    SUBSTRING(agg_inner."AEDAT_EKKO", 1, 6) AS MONTH
FROM (
  SELECT ..., dimensions, aggregations
  GROUP BY dimensions
) AS agg_inner
```

**Root Cause**:
Can't reference column aliases in GROUP BY of same SELECT. Calculated columns need to be computed AFTER grouping.

**Solution**:
Wrap aggregation in subquery when it has calculated columns:
- Inner query: Dimensions + aggregations with GROUP BY
- Outer query: Add calculated columns

**Files Modified**:
- `src/xml_to_sql/sql/renderer.py::_render_aggregation()` - Lines 647-673

**Validation**: ✅ MONTH, YEAR computed in outer query after grouping

---

### SOLVED-008: Skip Aggregated Columns in Dimension Mappings

**Original Bug**: BUG-011  
**Discovered**: 2025-11-13, CV_INVENTORY_ORDERS.xml  
**Resolved**: 2025-11-13

**Error**:
```
column ambiguously defined: WKURS_EKKO (appears both as dimension and measure)
```

**Problem**:
Columns that are aggregated (SUM/COUNT/etc.) were also being added as passthrough dimensions, creating duplicates.

**SQL Before**:
```sql
SELECT 
    join_4.WKURS_EKKO AS WKURS_EKKO,  -- Dimension passthrough
    ...
    SUM(join_4.WKURS_EKKO) AS WKURS_EKKO  -- Aggregated measure
-- ERROR: WKURS_EKKO defined twice
```

**SQL After**:
```sql
SELECT 
    -- WKURS_EKKO NOT in dimensions (skipped)
    ...
    SUM(join_4.WKURS_EKKO) AS WKURS_EKKO  -- Only aggregated
```

**Root Cause**:
`node.mappings` includes ALL columns, but some are measures (to be aggregated) not dimensions (to be passed through). Renderer was adding all mappings as passthroughs, then adding aggregations, creating duplicates.

**Solution**:
Skip mappings that are also in aggregation specs:

```python
aggregated_col_names = set(agg.target_name.upper() for agg in node.aggregations)

for mapping in node.mappings:
    if (mapping.target_name.upper() not in calc_col_names and 
        mapping.target_name.upper() not in aggregated_col_names):
        # Add as dimension
```

**Files Modified**:
- `src/xml_to_sql/sql/renderer.py::_render_aggregation()` - Lines 597-606

**Validation**: ✅ WKURS_EKKO only appears once as SUM()

---

---

## Summary

**Total Bugs Solved**: 8 (in single session)  
**XML**: CV_INVENTORY_ORDERS.xml (BW, 220 lines)  
**Result**: ✅ Executes successfully in HANA BID (34ms)

**Common Pattern**: All bugs related to **target/alias vs source/actual** column name resolution in different contexts (WHERE, GROUP BY, JOIN, aggregations).

**Key Insight**: User naming convention adds table suffix to columns (e.g., LOEKZ→LOEKZ_EKPO, WEMNG→WEMNG_EKET) to distinguish columns from different sources. This creates systematic target≠source mismatches that require careful mapping throughout the rendering pipeline.

**Files Modified**:
- `src/xml_to_sql/parser/column_view_parser.py` - ColumnView JOIN parsing
- `src/xml_to_sql/sql/renderer.py` - Projection filters, aggregation rendering (dimensions, measures, GROUP BY, calculated columns)

**Validation**: ✅ Both XMLs execute successfully in HANA
- CV_CNCLD_EVNTS (ECC/MBD): 243 lines, 84ms
- CV_INVENTORY_ORDERS (BW/BID): 220 lines, 34ms

---

### SOLVED-011: `CURRENT_TIMESTAMP()` Parentheses Removed

**Original Bug**: BUG-011  
**Discovered**: 2025-11-16 (CV_EQUIPMENT_STATUSES)  
**Resolved**: 2025-11-16

**Error**:
```
SAP DBTech JDBC: [257]: sql syntax error: incorrect syntax near ")": line 82 col 63
```

**Root Cause**:
- ColumnView XML uses `now()` helper
- Catalog mapping with `handler: rename` generated `CURRENT_TIMESTAMP()`
- HANA expects `CURRENT_TIMESTAMP` (no parentheses) when called without arguments

**Fix**:
- Update `functions.yaml` to use `handler: template` with `template: "CURRENT_TIMESTAMP"`
- Remove legacy regex that uppercased `now()` manually
- Regenerate SQL to confirm `DAYS_BETWEEN(..., CURRENT_TIMESTAMP)`

**Files Changed**:
- `src/xml_to_sql/catalog/data/functions.yaml`
- `src/xml_to_sql/sql/function_translator.py`
- `Target (SQL Scripts)/CV_EQUIPMENT_STATUSES.sql`

**Validation**:
- ✅ CV_EQUIPMENT_STATUSES executes successfully (32ms)
- ✅ Functions catalog regression tests pass

---

### SOLVED-012: Schema-Qualified View Creation (`SAPABAP1.<view>`)

**Original Bug**: BUG-012  
**Discovered**: 2025-11-16 (BW XMLs)  
**Resolved**: 2025-11-16

**Error**:
```
SAP DBTech JDBC: [362]: invalid schema name: ABAP
```

**Root Cause**:
- ColumnView XML references data sources as `"ABAP"./BIC/...`
- Generated SQL created views without schema qualification and assumed ABAP schema for sources
- In BID system, actual schema is `SAPABAP1`, so view creation and SELECT statements failed

**Fix**:
1. Added configuration support for `defaults.view_schema` and per-scenario `overrides.schema`
2. CLI + API now qualify view names (e.g., `SAPABAP1.CV_EQUIPMENT_STATUSES`)
3. `_quote_identifier` updated to handle `schema.view` inputs without quoting the dot
4. Web converter + API models now accept `view_schema` (default `SAPABAP1`)
5. Regenerated validated SQL files with new header:
   ```
   DROP VIEW SAPABAP1.<name> CASCADE;
   CREATE VIEW SAPABAP1.<name> AS ...
   ```

**Files Changed**:
- `config.example.yaml`, `src/xml_to_sql/config/*`
- `src/xml_to_sql/cli/app.py`
- `src/xml_to_sql/web/api/models.py`, `web/api/routes.py`, `web/services/converter.py`
- `src/xml_to_sql/sql/renderer.py`
- `Target (SQL Scripts)/CV_{CNCLD_EVNTS,INVENTORY_ORDERS,PURCHASE_ORDERS,EQUIPMENT_STATUSES}.sql`

**Validation**:
- ✅ All four SQL files execute successfully in HANA
- ✅ DROP/CREATE statements now fully deterministic

---

### SOLVED-013: Legacy STRING() Function Not Recognized in HANA

**Original Bug**: BUG-013
**Discovered**: 2025-11-16, CV_TOP_PTHLGY.xml
**Resolved**: 2025-11-16

**Error**:
```
SAP DBTech JDBC: [328]: invalid name of function or procedure: STRING: line 50 col 33 (at pos 3285)
```

**Problem**:
Legacy `string()` helper function was being emitted verbatim in WHERE clauses, but HANA doesn't recognize `STRING` as a valid function name. The conversion succeeded but CREATE VIEW failed during HANA execution.

**Root Cause**:
The function catalog (`src/xml_to_sql/catalog/data/functions.yaml`) contained rewrites for other legacy helpers (LEFTSTR→SUBSTRING, RIGHTSTR→RIGHT, MATCH→REGEXP_LIKE, etc.) but was missing the `string()` → `TO_VARCHAR()` mapping.

**Solution**:
Added `STRING` → `TO_VARCHAR` mapping to the function catalog:

```yaml
  - name: STRING
    handler: rename
    target: "TO_VARCHAR"
    description: >
      Legacy STRING() function mapped to TO_VARCHAR() for type conversion to string/varchar.
```

The catalog rewrite system (via `_apply_catalog_rewrites()` in `function_translator.py`) automatically translates all `string(expr)` calls to `TO_VARCHAR(expr)` during formula translation.

**Associated Rules**:
- **Catalog System**: Centralized function mapping (handover line 170-178)
- **Legacy Helper Translation**: Systematic rewrite of deprecated HANA 1.x functions

**Files Changed**:
- `src/xml_to_sql/catalog/data/functions.yaml` (added STRING entry)

**Validation**:
- ⏳ Pending: User to re-run CV_TOP_PTHLGY conversion and verify HANA execution succeeds

**Code Flow**:
1. XML parser encounters `string(FIELD)` in filter expression
2. `translate_raw_formula()` calls `_apply_catalog_rewrites()` (line 219 for HANA mode)
3. Catalog rule rewrites `string(FIELD)` → `TO_VARCHAR(FIELD)`
4. Generated SQL uses HANA-compatible `TO_VARCHAR()` function

---

### SOLVED-014: Schema Name ABAP Not Recognized in HANA

**Original Bug**: New issue (CV_TOP_PTHLGY)
**Discovered**: 2025-11-16, CV_TOP_PTHLGY.xml
**Resolved**: 2025-11-16

**Error**:
```
SAP DBTech JDBC: [362]: invalid schema name: ABAP: line 13 col 10 (at pos 576)
```

**Problem**:
XML data sources use `ABAP` schema, but HANA instance uses `SAPABAP1` as the actual schema name. All table references generated as `ABAP.TABLE_NAME` causing "invalid schema name" errors.

**Root Cause**:
Different HANA instances use different schema naming conventions:
- Some use `ABAP` directly
- Others use `SAPABAP1`, `SAP<SID>`, etc.
- No schema mapping was configured

**Solution**:
Added schema override to `config.yaml`:

```yaml
schema_overrides:
  ABAP: "SAPABAP1"
```

The renderer's `schema_overrides` parameter now maps `ABAP` → `SAPABAP1` during SQL generation.

**Associated Rules**:
- **Schema Mapping**: Configuration-driven schema name translation
- **Instance-Specific Settings**: Each HANA instance may require different mappings

**Files Changed**:
- `config.yaml` / `config.example.yaml` - Added ABAP → SAPABAP1 mapping

**Validation**:
- ✅ All table references now use `SAPABAP1.TABLE_NAME`
- ✅ HANA accepts the schema name

---

### SOLVED-015: TIMESTAMP Arithmetic Not Supported in HANA

**Original Bug**: New issue (CV_TOP_PTHLGY)
**Discovered**: 2025-11-16, CV_TOP_PTHLGY.xml
**Resolved**: 2025-11-16 (✅ FULLY AUTOMATED via Pattern Matching System)

**Error**:
```
SAP DBTech JDBC: [266]: inconsistent datatype: the expression has incomputable datatype:
TIMESTAMP is invalid for subtraction operator: line 59 col 105 (at pos 4041)
```

**Problem**:
XML formula `date(NOW() - 365)` translates to `TO_DATE(CURRENT_TIMESTAMP - 365)`, but HANA doesn't allow direct arithmetic on TIMESTAMP types. Must use date functions like `ADD_DAYS()`.

**Root Cause**:
The catalog handles simple function replacements (`NOW()` → `CURRENT_TIMESTAMP`) but doesn't handle **expression pattern rewrites**:
- `NOW() - N` should become `ADD_DAYS(CURRENT_DATE, -N)` or `ADD_DAYS(CURRENT_TIMESTAMP, -N)`
- Current translator processes tokens sequentially, missing the arithmetic operator context

**Solution** (IMPLEMENTED):
Created **Pattern Matching System** with regex-based expression rewrites:

1. **Created `src/xml_to_sql/catalog/data/patterns.yaml`**:
   ```yaml
   - name: "date_now_minus_days"
     match: "date\\s*\\(\\s*NOW\\s*\\(\\s*\\)\\s*-\\s*(\\d+)\\s*\\)"
     hana: "ADD_DAYS(CURRENT_DATE, -$1)"

   - name: "now_minus_days"
     match: "NOW\\s*\\(\\s*\\)\\s*-\\s*(\\d+)"
     hana: "ADD_DAYS(CURRENT_DATE, -$1)"

   - name: "timestamp_minus_days"
     match: "CURRENT_TIMESTAMP\\s*-\\s*(\\d+)"
     hana: "ADD_DAYS(CURRENT_TIMESTAMP, -$1)"
   ```

2. **Created `src/xml_to_sql/catalog/pattern_loader.py`** with `PatternRule` dataclass and `get_pattern_catalog()` loader

3. **Added `_apply_pattern_rewrites()` to `function_translator.py`**:
   - Pattern rewrites applied BEFORE catalog function name rewrites
   - Regex-based with capture group substitution
   - Processes all patterns in order from patterns.yaml

4. **Integrated into `translate_raw_formula()` pipeline**:
   ```python
   # IMPORTANT ORDER:
   # 1. Apply PATTERN rewrites FIRST (NOW() - N → ADD_DAYS())
   # 2. Then catalog rewrites (function name mappings)
   result = _apply_pattern_rewrites(result, ctx, mode)
   result = _apply_catalog_rewrites(result, ctx)
   ```

**Associated Rules**:
- **Date Arithmetic**: HANA requires function calls (ADD_DAYS, ADD_MONTHS) not operators
- **Pattern Rewrites**: Regex-based expression transformation before function name mapping
- **Two-Phase Translation**: Pattern rewrites → Catalog rewrites → Mode-specific transforms

**Files Changed**:
- `src/xml_to_sql/catalog/data/patterns.yaml` - Pattern catalog (NEW)
- `src/xml_to_sql/catalog/pattern_loader.py` - Pattern loader module (NEW)
- `src/xml_to_sql/catalog/__init__.py` - Export pattern catalog
- `src/xml_to_sql/sql/function_translator.py` - Pattern rewrite integration
- `PATTERN_MATCHING_DESIGN.md` - Complete implementation design (NEW)
- `HANA_CONVERSION_RULES.md` - Rule 16 added

**Validation**:
- ✅ All pattern matching tests PASSED (test_pattern_matching.py)
- ✅ CV_TOP_PTHLGY.xml regenerated cleanly with 7 ADD_DAYS() transformations
- ✅ No manual patches needed
- ✅ HANA execution successful (198ms)

---

### SOLVED-016: Function Name Case Sensitivity (adddays vs ADD_DAYS)

**Original Bug**: New issue (CV_TOP_PTHLGY)
**Discovered**: 2025-11-16, CV_TOP_PTHLGY.xml
**Resolved**: 2025-11-16

**Error**:
```
SAP DBTech JDBC: [328]: invalid name of function or procedure: ADDDAYS: line 1681 col 10
```

**Problem**:
XML contains lowercase `adddays()` function calls, but HANA requires uppercase `ADD_DAYS()` (with underscore). Generated SQL had `adddays(TO_DATE(...), -3)`.

**Root Cause**:
XML formulas can contain legacy function names in various cases. The catalog system was missing the `ADDDAYS` entry.

**Solution**:
Added catalog entry:
```yaml
  - name: ADDDAYS
    handler: rename
    target: "ADD_DAYS"
    description: >
      Date arithmetic function - uppercase variant. HANA requires ADD_DAYS (with underscore).
```

**Associated Rules**:
- **Function Case Normalization**: All HANA built-in functions should be uppercase
- **Catalog Completeness**: Every legacy helper variant needs a catalog entry

**Files Changed**:
- `src/xml_to_sql/catalog/data/functions.yaml` - Added ADDDAYS entry

**Validation**:
- ✅ Catalog now handles `adddays()` → `ADD_DAYS()`
- ⚠️ Requires package reinstall (`pip install -e .`)

---

### SOLVED-017: INT() Function Not Recognized in HANA

**Original Bug**: New issue (CV_TOP_PTHLGY)
**Discovered**: 2025-11-16, CV_TOP_PTHLGY.xml
**Resolved**: 2025-11-16

**Error**:
```
SAP DBTech JDBC: [328]: invalid name of function or procedure: INT: line 1815 col 57
```

**Problem**:
XML formula uses `int(FIELD)` for integer casting, but HANA doesn't have an `INT()` function. HANA uses `TO_INTEGER()` or `CAST(... AS INTEGER)`.

**Root Cause**:
Legacy XML formulas use simplified type cast functions (`int()`, `string()`, etc.) that don't exist in standard HANA SQL.

**Solution**:
Added catalog entry:
```yaml
  - name: INT
    handler: rename
    target: "TO_INTEGER"
    description: >
      Legacy INT() type cast mapped to HANA TO_INTEGER() function for integer conversion.
```

**Associated Rules**:
- **Type Conversion Functions**: Map legacy casts to HANA equivalents
  - `int()` → `TO_INTEGER()`
  - `string()` → `TO_VARCHAR()`
  - `decimal()` → `TO_DECIMAL()`
  - `date()` → `TO_DATE()`

**Files Changed**:
- `src/xml_to_sql/catalog/data/functions.yaml` - Added INT entry

**Validation**:
- ✅ Catalog now handles `int()` → `TO_INTEGER()`
- ⚠️ Requires package reinstall (`pip install -e .`)

---

### SOLVED-021: Empty String IN Numeric Type Conversion Error

**Original Bug**: BUG-021 (CV_MCM_CNTRL_Q51)
**Discovered**: 2025-11-18, CV_MCM_CNTRL_Q51.xml
**Resolved**: 2025-11-18

**Error**:
```
SAP DBTech JDBC: [339]: invalid number: not a valid number string '' at implicit type conversion
Could not execute 'CREATE VIEW "_SYS_BIC"."EYAL.EYAL_CTL/CV_MCM_CNTRL_Q51" AS WITH projection_1 AS ( ...'
```

**Problem**:
Parameter substitution resulted in malformed WHERE clause:
```sql
WHERE ('' IN (0) OR calc."ZZTREAT_COMM_CD" IN (''))
```

HANA attempts implicit type conversion of empty string `''` to match numeric value `0` in IN clause, causing error [339].

**Root Cause**:
Variable parameters with empty defaults were not properly cleaned up, resulting in:
- `'' IN (0)` - empty string compared against numeric value
- HANA's strict type system requires compatible types for IN clause comparisons
- Empty parameters should be removed entirely from WHERE conditions

**Solution**:
Enhanced `_cleanup_hana_parameter_conditions()` in `renderer.py` (lines 1156-1193) to remove all `'' IN (numeric)` patterns:

```python
# BUG-021: Remove empty string IN numeric patterns
# Pattern: ('' IN (0) OR column IN (...)) → keep only second part
result = re.sub(
    r"\(\s*''\s+IN\s+\(\s*\d+\s*\)\s+OR\s+([^)]+)\)",
    r"(\1)",
    result,
    flags=re.IGNORECASE
)

# Remove standalone '' IN (number) patterns in various positions
# At start: ('' IN (0) AND ...) → (...)
# At end: (... AND '' IN (0)) → (...)
# Surrounded: AND '' IN (0) AND → AND
```

**Associated Rules**:
- **Parameter Cleanup**: Remove invalid parameter patterns before SQL generation
- **Type Safety**: HANA requires type-compatible comparisons in IN clauses
- **Empty String Handling**: Empty parameters should be removed, not compared

**Files Changed**:
- `src/xml_to_sql/sql/renderer.py` - Enhanced parameter cleanup (lines 1156-1193)

**Validation**:
- ✅ CV_MCM_CNTRL_Q51.xml: 82ms total (18ms DROP + 63ms CREATE)
- ✅ HANA Studio execution successful
- ✅ No type conversion errors

**Code Flow**:
1. XML parameter variables generate `($$param$$ IN (0) OR column IN (...))` patterns
2. Parameter substitution replaces `$$param$$` with `''`
3. Result: `('' IN (0) OR column IN (...))`
4. `_cleanup_hana_parameter_conditions()` detects and removes `'' IN (0)` pattern
5. Final SQL: `(column IN (...))`
6. HANA executes successfully without type conversion error

---

### SOLVED-022: Empty WHERE Clause After Parameter Cleanup

**Original Bug**: BUG-022 (CV_MCM_CNTRL_REJECTED)
**Discovered**: 2025-11-18, CV_MCM_CNTRL_REJECTED.xml
**Resolved**: 2025-11-18

**Error**:
```
SAP DBTech JDBC: [257]: sql syntax error: incorrect syntax near ")": line 22 col 12 (at pos 1052)
Could not execute 'CREATE VIEW "_SYS_BIC"."EYAL.EYAL_CTL/CV_MCM_CNTRL_REJECTED" AS WITH projection_5 AS ( ...'
```

**Problem**:
After BUG-021 cleanup removed invalid parameter patterns, empty WHERE clauses remained:
```sql
SELECT ...
FROM SAPABAP1.ZCACSM_DOCINV
WHERE ()
```

**Root Cause**:
1. BUG-021 fix successfully removed `'' IN (0)` patterns from WHERE clauses
2. When ALL conditions were removed, empty parentheses `()` remained
3. String `"()"` is truthy in Python, so `if where_clause:` still added `WHERE ()`
4. HANA rejects `WHERE ()` as invalid syntax
5. Cleanup function was called but didn't verify result was non-empty

**Solution**: Enhanced all rendering functions with post-cleanup validation

**Code Changes** (renderer.py):

1. **Projection with subquery** (lines 513-524):
```python
if ctx.database_mode == DatabaseMode.HANA:
    qualified_where = _cleanup_hana_parameter_conditions(qualified_where)
    # BUG-022: Check if WHERE clause is effectively empty after cleanup
    qualified_where_stripped = qualified_where.strip()
    if qualified_where_stripped in ('', '()'):
        qualified_where = ''

if qualified_where:
    sql = f"... WHERE {qualified_where}"
else:
    sql = f"... (no WHERE clause)"
```

2. **Projection without subquery** (lines 527-533):
```python
if ctx.database_mode == DatabaseMode.HANA and where_clause:
    where_clause = _cleanup_hana_parameter_conditions(where_clause)
    where_clause_stripped = where_clause.strip()
    if where_clause_stripped in ('', '()'):
        where_clause = ''
```

3. **Join rendering** (lines 591-596)
4. **Aggregation rendering** (lines 682-687)
5. **Union rendering** (lines 768-773)
6. **Calculation rendering** (lines 830-836)

7. **Cleanup function** (lines 1199-1204):
```python
# BUG-022: Remove empty WHERE clauses
result = re.sub(
    r'\bWHERE\s+\(\s*\)',
    '',
    result,
    flags=re.IGNORECASE
)
```

**Validation**:
- ✅ CV_MCM_CNTRL_REJECTED.xml: 53ms total (8ms DROP + 45ms CREATE)
- ✅ HANA Studio execution successful
- ✅ No syntax errors on empty WHERE clauses

**Related Issues**:
- BUG-021: Initial parameter cleanup that could leave empty WHERE clauses
- Demonstrates importance of validating cleanup results, not just performing cleanup

**Code Flow**:
1. XML datasource has filters with only parameter variables
2. Parameter substitution creates `WHERE ('' IN (0) OR ...)`
3. BUG-021 cleanup removes `'' IN (0)` pattern
4. Result after BUG-021: `WHERE ()`
5. BUG-022 cleanup detects empty/`()` result
6. WHERE clause omitted entirely
7. HANA executes successfully

---

### SOLVED-028: Join Table Not Qualified With Schema

**Original Bug**: BUG-028
**Discovered**: 2025-11-20, CV_COMMACT_UNION.xml (MBD)
**Resolved**: 2025-11-20

**Error**:
```
SAP DBTech JDBC: [259]: invalid table name: Could not find table/view _BIC_AZEKKO2 in schema _SYS_BIC: line 224 col 10 (at pos 11066)
```

**Problem**:
Join nodes with direct table entity inputs generated bare table aliases without schema qualification:
```sql
-- WRONG - bare alias without schema or CTE
FROM _bic_azekko2
RIGHT OUTER JOIN union_1 ON _bic_azekko2.EBELN = union_1.REF_DOC_NR

-- CORRECT - schema-qualified table with AS alias
FROM SAPABAP1."/BIC/AZEKKO2" AS _bic_azekko2
RIGHT OUTER JOIN union_1 AS union_1 ON _bic_azekko2.EBELN = union_1.REF_DOC_NR
```

**Root Cause**:
The `_render_join()` function in renderer.py used `ctx.get_cte_alias()` for both join inputs, which simply lowercases node IDs. This works for CTE references but fails for direct table references that need schema qualification.

**XML Structure** (lines 865-871 of CV_COMMACT_UNION.xml):
```xml
<input alias="_BIC_AZEKKO2">
  <entity>#//"ABAP"./BIC/AZEKKO2</entity>
  <mapping xsi:type="Type:ElementMapping" targetName="EBELN" sourceName="EBELN"/>
  <mapping xsi:type="Type:ElementMapping" targetName="LIFNR" sourceName="LIFNR"/>
</input>
<input>
  <viewNode xsi:type="View:Union">#//Union_1</viewNode>
```

The XML uses **column view format** (not scenario view), and column_view_parser.py correctly created a DataSource for the table entity. However, the join renderer didn't use the proper rendering function.

**Solution**:
Modified `_render_join()` function in renderer.py to use `_render_from()` instead of just `get_cte_alias()`:

**Code Changes** (renderer.py):

1. **Lines 549-558** - Get proper FROM clauses:
```python
left_id = node.inputs[0].lstrip("#")
right_id = node.inputs[1].lstrip("#")

# BUG-028: Render proper FROM clauses for both CTEs and data sources
left_from = _render_from(ctx, left_id)
right_from = _render_from(ctx, right_id)

# Get aliases for column references
left_alias = ctx.get_cte_alias(left_id)
right_alias = ctx.get_cte_alias(right_id)
```

2. **Line 616** - Use rendered FROM clauses with AS aliases:
```python
# BUG-028: Use proper FROM rendering for both CTEs and tables, with AS clauses for aliases
sql = f"SELECT\n    {select_clause}\nFROM {left_from} AS {left_alias}\n{join_type_str} JOIN {right_from} AS {right_alias} ON {on_clause}"
```

**Why This Works**:
The `_render_from()` function (lines 882-895) properly handles three cases:
1. **Data sources (tables)**: Returns schema-qualified name like `SAPABAP1."/BIC/AZEKKO2"`
2. **CTE references**: Returns the CTE alias
3. **Unknown references**: Falls back to lowercased alias

By using `_render_from()` to get the FROM clause, then explicitly adding `AS {alias}`, we ensure:
- Tables get schema qualification: `SAPABAP1."/BIC/AZEKKO2" AS _bic_azekko2`
- CTEs get proper aliasing: `union_1 AS union_1`
- Column references use the alias: `_bic_azekko2.EBELN`

**Files Modified**:
- `src/xml_to_sql/sql/renderer.py` (lines 549-558, 616)

**Impact**:
- Fixes ALL column view joins with direct table entity inputs
- Common pattern in BW calculation views that join DSO/InfoCubes with dimension tables
- Critical fix - affects any XML with `<input><entity>` in join nodes

**Validation**:
- ✅ CV_COMMACT_UNION.xml: 50ms total (12ms DROP + 36ms CREATE)
- ✅ HANA Studio execution successful
- ✅ Properly qualified table reference with schema and alias

**Related Rules**: Data source rendering in join contexts

**Code Flow**:
1. column_view_parser.py creates DataSource for table entity
2. `_render_join()` calls `_render_from()` for each input
3. `_render_from()` detects table data source, returns `SAPABAP1."/BIC/AZEKKO2"`
4. Join renderer adds `AS _bic_azekko2` for aliasing
5. Column references use alias: `_bic_azekko2.EBELN`
6. HANA executes successfully

---

## Resolved in Previous Sessions

*(Placeholder for bugs fixed before structured tracking began)*

**Count**: 13+ issues resolved during CV_CNCLD_EVNTS.xml testing
- IF to CASE conversion
- IN to OR conversion  
- Uppercase IF
- Calculated column expansion
- Subquery wrapping
- Column qualification
- Parameter removal (simple cases)
- String concatenation
- And more...

See: `EMPIRICAL_TEST_ITERATION_LOG.md` for historical fixes

---

### BUG-029: View Name Quoting in DROP/CREATE VIEW Statements

**⚠️ PERMANENT ID**: BUG-029 (kept throughout lifecycle per new numbering system)

**Discovered**: 2025-11-22, CV_ELIG_TRANS_01.xml
**Resolved**: 2025-11-22 (SESSION 7)
**Instance Type**: BW (MBD)

**Error**:
```
SAP DBTech JDBC: [321]: invalid view name: CV_ELIG_TRANS_01: line 1 col 22 (at pos 21)
```

**Problem**:
```sql
-- WRONG - View name not quoted
DROP VIEW "_SYS_BIC".CV_ELIG_TRANS_01 CASCADE;
CREATE VIEW "_SYS_BIC".CV_ELIG_TRANS_01 AS
```

HANA requires ALL identifiers in DROP/CREATE VIEW statements to be quoted. The view name `CV_ELIG_TRANS_01` was generated unquoted instead of `"CV_ELIG_TRANS_01"`.

**Root Cause**:
The `_quote_identifier_part()` function returned UNQUOTED UPPERCASE for alphanumeric identifiers to preserve case-insensitivity in column references. However, view names in DDL statements have different quoting requirements than column names in SELECT clauses.

**Initial Aggressive Fix Attempt (FAILED)**:
Modified `_quote_identifier_part()` to ALWAYS quote all identifiers. This fixed BUG-029 but broke CV_TOP_PTHLGY with:
```
SAP DBTech JDBC: [260]: invalid column name: RANK_1.RANK_COLUMN
```

Reason: Quoted identifiers are case-sensitive in HANA. Column defined as `"Rank_Column"` doesn't match reference to `"RANK_COLUMN"`. Before fix: both unquoted → case-insensitive → worked. After aggressive fix: both quoted → case-sensitive → broken.

**Surgical Solution Implemented**:
Added quoting ONLY in `_generate_view_statement()` for DDL statements, preserving case-insensitivity elsewhere:

```python
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

    # Rest of function unchanged...
```

**Key Insight - Case-Sensitivity**:
- Quoted identifiers: `"CV_Name"` ≠ `"CV_NAME"` (case-sensitive)
- Unquoted identifiers: `CV_Name` = `CV_NAME` (case-insensitive)
- View names in DDL: MUST be quoted
- Column names in SELECT: SHOULD remain unquoted for case-insensitive matching

**Result - CORRECT**:
```sql
DROP VIEW "_SYS_BIC"."CV_ELIG_TRANS_01" CASCADE;
CREATE VIEW "_SYS_BIC"."CV_ELIG_TRANS_01" AS
```

**Files Modified**:
- `src/xml_to_sql/sql/renderer.py` lines 1594-1606: `_generate_view_statement()` function
  - Added surgical quoting logic for view names in DDL
  - Preserved `_quote_identifier_part()` for column names (case-insensitivity)

**Impact**:
- Affects ALL Calculation View conversions - every DROP/CREATE VIEW statement
- Critical fix for HANA compatibility
- Surgical approach preserves case-insensitive column matching

**Validation**:
- ✅ CV_ELIG_TRANS_01: 28ms (BUG-029 + BUG-030 fixes)
- ✅ CV_TOP_PTHLGY: 201ms (no regression from surgical fix)
- ✅ All previously validated XMLs still working

**Affected XMLs**:
- CV_ELIG_TRANS_01.xml (discovered)
- All XMLs (affects view name generation for all CVs)

**Related Rules**: See HANA_CONVERSION_RULES.md PRINCIPLE #5 (View Name Quoting in DDL)

**Regression Testing**: Full regression test passed - no previously working XMLs broken

---

### BUG-030: CV Reference Package Path Incorrectly Split on Dot

**⚠️ PERMANENT ID**: BUG-030 (kept throughout lifecycle per new numbering system)

**Discovered**: 2025-11-22, CV_ELIG_TRANS_01.xml
**Resolved**: 2025-11-22 (SESSION 7)
**Instance Type**: BW (MBD)

**Error**:
```
SAP DBTech JDBC: [471]: invalid data source name: _SYS_BIC: line 133 col 16 (at pos 6815)
```

**Problem**:
```sql
-- WRONG - Three-level qualification (package path split on ".")
INNER JOIN "_SYS_BIC".MACABI_BI."Eligibility/CV_MD_EYPOSPER" AS cv_md_eyposper
           ↑ quoted    ↑ unquoted ↑ quoted (3 parts - wrong!)

-- CORRECT - Two-level qualification (package path as single identifier)
INNER JOIN "_SYS_BIC"."Macabi_BI.Eligibility/CV_MD_EYPOSPER" AS cv_md_eyposper
           ↑ quoted    ↑ entire package path + CV name (2 parts - correct!)
```

CV reference should have TWO parts:
1. Schema: `"_SYS_BIC"` (quoted)
2. View name with package path: `"Macabi_BI.Eligibility/CV_MD_EYPOSPER"` (quoted as single identifier)

But generated SQL had THREE parts because the "." in package path was split.

**Root Cause**:
The `_render_from()` function used `_quote_identifier()` which splits on "." to quote each part separately:

```python
# WRONG (original code):
view_name_with_package = f"{package}/{cv_name}"
# Example: "Macabi_BI.Eligibility/CV_MD_EYPOSPER"

return f'"_SYS_BIC".{_quote_identifier(view_name_with_package)}'
# _quote_identifier() splits on "." so:
# "Macabi_BI.Eligibility/CV_MD_EYPOSPER"
# → splits into: ["Macabi_BI", "Eligibility/CV_MD_EYPOSPER"]
# → quotes each: MACABI_BI (uppercase unquoted) + "Eligibility/CV_MD_EYPOSPER" (quoted)
# → result: "_SYS_BIC".MACABI_BI."Eligibility/CV_MD_EYPOSPER" ❌
```

**Why This Breaks**:
- Package paths contain "." as part of the hierarchical structure (e.g., `Macabi_BI.Eligibility`)
- This "." is NOT a schema separator - it's part of the package name
- `_quote_identifier()` incorrectly treats it as a separator
- HANA interprets this as THREE-level qualification instead of TWO-level

**Solution Implemented**:
Don't use `_quote_identifier()` for CV references. Quote the entire package path + CV name as a single identifier:

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

**Result - CORRECT**:
```sql
INNER JOIN "_SYS_BIC"."Macabi_BI.Eligibility/CV_MD_EYPOSPER" AS cv_md_eyposper
```

**Files Modified**:
- `src/xml_to_sql/sql/renderer.py` lines 954-962: `_render_from()` function
  - Changed from `_quote_identifier(view_name_with_package)` to direct quoting
  - Added BUG-030 comments explaining why not to use `_quote_identifier()`

**Impact**:
- Affects ALL XMLs that reference other Calculation Views
- Critical for CV-to-CV joins
- Without this fix, any XML referencing another CV will fail

**Validation**:
- ✅ CV_ELIG_TRANS_01: 28ms (references CV_MD_EYPOSPER successfully)
- ✅ All previously validated XMLs still working

**Affected XMLs**:
- CV_ELIG_TRANS_01.xml (references CV_MD_EYPOSPER)
- Any XML with CALCULATION_VIEW data sources

**Related Rules**: See HANA_CONVERSION_RULES.md PRINCIPLE #6 (CV Reference Quoting)

---

### BUG-032: Calculated Column Forward References in Aggregations

**⚠️ PERMANENT ID**: BUG-032 (kept throughout lifecycle per new numbering system)

**Discovered**: 2025-11-22, CV_INVENTORY_STO.xml
**Resolved**: 2025-11-22 (SESSION 8)
**Instance Type**: ColumnView

**Error**:
```
SAP DBTech JDBC: [260]: invalid column name: AGG_INNER.YEAR: line 351 col 9 (at pos 14310)
```

**Problem**:
```sql
-- WRONG - Forward reference to calculated column in same SELECT
SELECT
    agg_inner.*,
    SUBSTRING(agg_inner."AEDAT_EKKO", 1, 6) AS MONTH,
    SUBSTRING(agg_inner."AEDAT_EKKO", 1, 4) AS YEAR,
    week(agg_inner."AEDAT_EKKO") AS WEEK,
    agg_inner."YEAR"+CASE WHEN ... END AS WEEKDAY  -- ❌ References YEAR defined above
FROM (
  SELECT ...
) AS agg_inner
```

Calculated column `WEEKDAY` references `YEAR`, but `YEAR` is a calculated column defined in the SAME SELECT clause. HANA doesn't allow forward references to column aliases.

**Root Cause**:
Aggregation nodes with calculated columns rendered as:
1. Inner query: Regular aggregations with GROUP BY
2. Outer query: Adds calculated columns using `agg_inner.*` + calculated expressions

When calculated column formulas referenced OTHER calculated columns (e.g., `WEEKDAY` references `YEAR`), the code qualified the reference with `agg_inner."YEAR"`, but `YEAR` doesn't exist in the inner query - it's defined in the SAME outer SELECT.

**Solution Implemented**:
Expand calculated column references to their source expressions BEFORE qualifying with `agg_inner.`:

```python
# In _render_aggregation() function (renderer.py lines 730-771):
if has_calc_cols:
    # Wrap: inner query groups, outer query adds calculated columns
    inner_sql = f"SELECT\n    {select_clause}\nFROM {from_clause}"
    if where_clause:
        inner_sql += f"\nWHERE {where_clause}"
    if group_by_clause:
        inner_sql += f"\n{group_by_clause}"

    # BUG-032: Build calc_column_map for expansion
    calc_column_map = {}  # Maps calc column name → rendered expression

    # Outer SELECT adds calculated columns
    outer_select = ["agg_inner.*"]
    for calc_name, calc_attr in node.calculated_attributes.items():
        if calc_attr.expression.expression_type == ExpressionType.RAW:
            formula = calc_attr.expression.value
            import re

            # BUG-032: Expand references to previously defined calculated columns
            for prev_calc_name, prev_calc_expr in calc_column_map.items():
                pattern = rf'"{re.escape(prev_calc_name)}"'
                if re.search(pattern, formula, re.IGNORECASE):
                    formula = re.sub(pattern, f'({prev_calc_expr})', formula, flags=re.IGNORECASE)

            # Then qualify remaining column refs with agg_inner."COLUMN"
            formula = re.sub(r'(?<!\.)"([A-Z_][A-Z0-9_]*)"', r'agg_inner."\1"', formula)
            calc_expr = translate_raw_formula(formula, ctx)
        else:
            calc_expr = _render_expression(ctx, calc_attr.expression, "agg_inner")

        outer_select.append(f"{calc_expr} AS {_quote_identifier(calc_name)}")
        calc_column_map[calc_name.upper()] = calc_expr  # Store for future expansions

    outer_clause = ",\n    ".join(outer_select)
    sql = f"SELECT\n    {outer_clause}\nFROM (\n  {inner_sql.replace(chr(10), chr(10) + '  ')}\n) AS agg_inner"
```

**Result - CORRECT**:
```sql
SELECT
    agg_inner.*,
    SUBSTRING(agg_inner."AEDAT_EKKO", 1, 6) AS MONTH,
    SUBSTRING(agg_inner."AEDAT_EKKO", 1, 4) AS YEAR,
    week(agg_inner."AEDAT_EKKO") AS WEEK,
    (SUBSTRING(agg_inner."AEDAT_EKKO", 1, 4))+CASE WHEN ... END AS WEEKDAY  -- ✅ Expanded
FROM (
  SELECT ...
) AS agg_inner
```

**Files Modified**:
- `src/xml_to_sql/sql/renderer.py` lines 730-771: `_render_aggregation()` function
  - Added `calc_column_map` dictionary to track calculated column expressions
  - Expand references to other calculated columns before qualifying with `agg_inner.`

**Pattern**: Similar to projection calculated column expansion (lines 397-433)

**Impact**:
- Affects aggregation nodes with calculated columns that reference other calculated columns
- Common pattern in complex aggregations with date/time calculations

**Validation**:
- ✅ CV_INVENTORY_STO: 55ms (CREATE VIEW successful with BUG-032 fix)
- ✅ All previously validated XMLs still working

**Affected XMLs**:
- CV_INVENTORY_STO.xml (WEEKDAY references YEAR, both calculated columns)

**Related**: BUG-033 (same issue in JOIN nodes)

---

### BUG-033: Calculated Column Forward References in JOIN Nodes

**⚠️ PERMANENT ID**: BUG-033 (kept throughout lifecycle per new numbering system)

**Discovered**: 2025-11-22, CV_PURCHASING_YASMIN.xml
**Resolved**: 2025-11-22 (SESSION 8)
**Instance Type**: ColumnView

**Error**:
```
SAP DBTech JDBC: [260]: invalid column name: EBELN_EKKN: line 378 col 21 (at pos 18201)
```

**Problem**:
```sql
-- WRONG - Forward reference to column alias in same SELECT
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
```

Calculated column `CC_NETWR` references column aliases `EBELN_EKKN`, `EBELP_EKKN`, and `NETWR_EKKN` which are defined in the SAME SELECT clause. HANA doesn't allow forward references to column aliases.

**Root Cause**:
JOIN nodes render all columns (mappings + calculated columns) in a single SELECT. When calculated column formulas referenced mapped columns (e.g., `CC_NETWR` references `EBELN_EKKN`), the code didn't expand the alias to its source expression.

This is the same pattern as BUG-032, but occurs in JOIN nodes instead of aggregation nodes.

**Solution Implemented**:
Expand calculated column references to mapped column source expressions:

```python
# In _render_join() function (renderer.py lines 592-638):
columns: List[str] = []
seen_targets = set()
column_map = {}  # BUG-033: Map target column name → source expression

for mapping in node.mappings:
    # ... (skip hidden columns, duplicates, etc.)
    source_expr = _render_expression(ctx, mapping.expression, source_alias)
    columns.append(f"{source_expr} AS {_quote_identifier(mapping.target_name)}")

    # BUG-033: Store mapping for calculated column expansion
    column_map[mapping.target_name.upper()] = source_expr

# BUG-033: Expand calculated column references to mapped columns
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
```

**Result - CORRECT**:
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

**Files Modified**:
- `src/xml_to_sql/sql/renderer.py` lines 592-638: `_render_join()` function
  - Added `column_map` dictionary to track column mappings (target name → source expression)
  - For calculated columns with RAW expressions, expand references to mapped columns before rendering

**Impact**:
- Affects JOIN nodes with calculated columns that reference mapped column aliases
- Common pattern in JOINs with conditional logic (CASE statements)

**Validation**:
- ✅ CV_PURCHASING_YASMIN: 60ms (CREATE VIEW successful with BUG-033 fix)
- ✅ All previously validated XMLs still working

**Affected XMLs**:
- CV_PURCHASING_YASMIN.xml (CC_NETWR references EBELN_EKKN, EBELP_EKKN, NETWR_EKKN)

**Related**: BUG-032 (same issue in aggregation nodes)

---

### BUG-034: Filter `including="false"` Not Negating Operators

**⚠️ PERMANENT ID**: BUG-034 (kept throughout lifecycle per new numbering system)

**Discovered**: 2025-11-30, DATA_SOURCES.XML
**Resolved**: 2025-11-30 (SESSION 9)
**Instance Type**: ECC (ECC_DATA_SOURCES)

**Error**:
```
View compiled but returned NO DATA - filters incorrectly matching excluded values
```

**Problem**:
```sql
-- WRONG - Equality instead of inequality
WHERE SAPK5D.ROOSOURCE.TYPE = 'HIER'
WHERE SAPK5D.ROOSFIELD.NOTEXREL = 'N'

-- CORRECT - Should be exclusion (not equal)
WHERE SAPK5D.ROOSOURCE.TYPE <> 'HIER'
WHERE SAPK5D.ROOSFIELD.NOTEXREL <> 'N'
```

The XML contained `<filter ... including="false">` which means EXCLUDE matching values, but the generated SQL was using `=` (equality) instead of `<>` (inequality).

**Root Cause**:
The `_render_filters()` function in renderer.py was completely ignoring the `pred.including` attribute on filter predicates. It always rendered the operator as-is without checking if it should be negated.

**XML Structure** (DATA_SOURCES.XML):
```xml
<filter xsi:type="AccessControl:SingleValueFilter" including="false" columnName="TYPE">
  <value>HIER</value>
</filter>
```

The `including="false"` attribute indicates exclusion, but this was being ignored during SQL rendering.

**Solution Implemented**:
Added operator negation logic to handle `including=False` filters:

```python
# New function in renderer.py lines 1116-1151:
def _negate_operator(op: str) -> str:
    """Negate a comparison operator for including=False filters (BUG-034)."""
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
    op_upper = op.upper()
    if op_upper in negation_map:
        return negation_map[op_upper]
    return f"NOT {op}"

# In _render_filters() function (lines 1166-1169):
# BUG-034: Handle including=False by negating the operator
if not pred.including:
    op = _negate_operator(op)
```

**Result - CORRECT**:
```sql
WHERE SAPK5D.ROOSOURCE.TYPE <> 'HIER'
WHERE SAPK5D.ROOSFIELD.NOTEXREL <> 'N'
```

**Files Modified**:
- `src/xml_to_sql/sql/renderer.py` lines 1116-1151: Added `_negate_operator()` function
- `src/xml_to_sql/sql/renderer.py` lines 1166-1169: Added check in `_render_filters()`

**Impact**:
- Affects ALL XMLs with `including="false"` filters
- Critical for exclusion filters (TYPE <> 'HIER', etc.)
- Without this fix, views return incorrect data

**Validation**:
- ✅ DATA_SOURCES.XML: Generated correct SQL with exclusion operators
- ✅ User verified: "worked correctly"

**Affected XMLs**:
- DATA_SOURCES.XML (discovered - TYPE filter, NOTEXREL filter)
- Any XML with exclusion filters

**Related**: BUG-035 (ListValueFilter with operands parsing)

---

### BUG-035: ListValueFilter with `<operands>` Not Parsed

**⚠️ PERMANENT ID**: BUG-035 (kept throughout lifecycle per new numbering system)

**Discovered**: 2025-11-30, DATA_SOURCES.XML
**Resolved**: 2025-11-30 (SESSION 9)
**Instance Type**: ECC (ECC_DATA_SOURCES)

**Error**:
```
Missing NOT IN filter in projection_3 - entire filter clause skipped
```

**Problem**:
```sql
-- WRONG - Filter completely missing
projection_3 AS (
  SELECT ...
  FROM SAPK5D.ROOSFIELD
  -- No WHERE clause!
)

-- CORRECT - Should have NOT IN filter
projection_3 AS (
  SELECT ...
  FROM SAPK5D.ROOSFIELD
  WHERE "FIELDNAME" NOT IN ('LOGSYS', 'DATAPAKID', 'RECORD', 'REQUID', 'RECORDMODE')
)
```

The parser was skipping `<filter xsi:type="AccessControl:ListValueFilter">` elements that had `<operands>` children instead of a direct `value` attribute.

**Root Cause**:
The `_parse_filters()` function in scenario_parser.py only looked for a direct `value` attribute on filter elements. When the filter used `<operands>` children (each with their own `value` attribute), the parser skipped the entire filter.

**XML Structure** (DATA_SOURCES.XML):
```xml
<filter xsi:type="AccessControl:ListValueFilter" including="false" columnName="FIELDNAME">
  <operands xsi:type="SQL:NullExpression"/>
  <operands xsi:type="SQL:ValueExpression" value="LOGSYS"/>
  <operands xsi:type="SQL:ValueExpression" value="DATAPAKID"/>
  <operands xsi:type="SQL:ValueExpression" value="RECORD"/>
  <operands xsi:type="SQL:ValueExpression" value="REQUID"/>
  <operands xsi:type="SQL:ValueExpression" value="RECORDMODE"/>
</filter>
```

The parser was looking for `filter_el.get("value")` which returned None, so it skipped the filter entirely.

**Solution Implemented**:
Enhanced `_parse_filters()` to handle `<operands>` children:

```python
# In _parse_filters() function (scenario_parser.py lines 458-482):
# BUG-035: Check for ListValueFilter with <operands> children
operands = filter_el.findall("./acc:operands", namespaces=_NS)
if not operands:
    operands = filter_el.findall(".//operands")
if operands:
    values = []
    for operand in operands:
        op_value = operand.get("value")
        if op_value is not None:
            values.append(f"'{op_value}'")
    if values:
        in_list = f"({', '.join(values)})"
        right_expr = Expression(ExpressionType.RAW, in_list, "VARCHAR")
        predicates.append(
            Predicate(
                kind=PredicateKind.COMPARISON,
                left=left_expr,
                operator="IN",  # Will be negated to NOT IN if including=False
                right=right_expr,
                including=including,
            )
        )
```

**Logic**:
1. Check for `<operands>` children in the filter element
2. Try both namespaced (`acc:operands`) and unnamespaced (`operands`) XPath
3. Collect all `value` attributes from operands (skip NullExpression)
4. Build IN list: `('LOGSYS', 'DATAPAKID', 'RECORD', 'REQUID', 'RECORDMODE')`
5. Create predicate with `operator="IN"` and `including` flag from XML
6. BUG-034 fix negates to `NOT IN` when `including=False`

**Result - CORRECT**:
```sql
projection_3 AS (
  SELECT ...
  FROM SAPK5D.ROOSFIELD
  WHERE "FIELDNAME" NOT IN ('LOGSYS', 'DATAPAKID', 'RECORD', 'REQUID', 'RECORDMODE')
)
```

**Files Modified**:
- `src/xml_to_sql/parser/scenario_parser.py` lines 458-482: Added operands parsing

**Impact**:
- Affects XMLs with `ListValueFilter` elements using `<operands>` children
- Without this fix, entire filter clauses are silently skipped
- Critical for views that need to exclude multiple values

**Validation**:
- ✅ DATA_SOURCES.XML: Generated correct SQL with NOT IN filter
- ✅ User verified: "worked correctly"

**Affected XMLs**:
- DATA_SOURCES.XML (discovered - FIELDNAME exclusion list)
- Any XML with ListValueFilter using operands

**Related**: BUG-034 (operator negation for including=False)

---

### BUG-040: SUM Aggregation on NVARCHAR Column Causes Datatype Error

**⚠️ PERMANENT ID**: BUG-040 (kept throughout lifecycle per new numbering system)
**Discovered**: 2025-12-22, COPYOF_CV_ACOUSTIC_1_09072023.xml
**Resolved**: 2025-12-22
**Validation Time**: 127ms (DROP: 9ms, CREATE: 118ms)

**Error**:
```
SAP DBTech JDBC: [266]: inconsistent datatype: only numeric type is available for SUM/AVG/STDDEV/VAR function
```

**Root Cause**:
XML defined `aggregationBehavior="SUM"` on column `ZZHOUR_MIDL_ZPA0002` which has type `NVARCHAR(3)`. HANA cannot SUM non-numeric columns. The renderer applied aggregation functions directly without checking data type compatibility.

**XML Definition**:
```xml
<element name="ZZHOUR_MIDL_ZPA0002" aggregationBehavior="SUM" engineAggregation="COUNT">
  <inlineType primitiveType="NVARCHAR" length="3" precision="3" scale="0"/>
</element>
```

**Solution Implemented**:
Added automatic `TO_INTEGER()` cast when aggregating non-numeric columns with SUM/AVG/STDDEV/VAR:

```python
# In _render_aggregation() function (renderer.py lines 740-751):
# BUG-040: Check if aggregation function requires numeric type but column is VARCHAR/NVARCHAR
if agg_func in ('SUM', 'AVG', 'STDDEV', 'VAR') and ctx.database_mode == DatabaseMode.HANA:
    data_type = agg_spec.data_type or agg_spec.expression.data_type
    if data_type:
        type_str = str(data_type).upper() if data_type else ''
        if 'VARCHAR' in type_str or 'CHAR' in type_str or 'STRING' in type_str or 'NVARCHAR' in type_str:
            agg_expr = f"TO_INTEGER({agg_expr})"
```

**Files Modified**:
- `src/xml_to_sql/sql/renderer.py`: Lines 740-751 (_render_aggregation function)

**Generated SQL - CORRECT**:
```sql
SUM(TO_INTEGER(join_8.ZZHOUR_MIDL_ZPA0002)) AS ZZHOUR_MIDL_ZPA0002
```

**Validation**:
- ✅ COPYOF_CV_ACOUSTIC_1_09072023.XML: HANA validated, 127ms total execution

**Scope**: ⚠️ UNIVERSAL FIX - Applies to ALL XMLs automatically
- This fix is built into the renderer and runs on EVERY conversion
- No manual intervention needed - automatic detection and correction
- Not specific to any XML - applies universally

**Associated Conversion Rule**:
- **RULE**: When `aggregationBehavior` is SUM/AVG/STDDEV/VAR but column type is VARCHAR/NVARCHAR, wrap in TO_INTEGER()
- **Pattern**: Data model issue in source XML - numeric aggregation defined on string column
- **Trigger**: Renderer checks data type of EVERY aggregated column during SQL generation

**Discovery Example**:
- COPYOF_CV_ACOUSTIC_1_09072023.xml (where bug was first encountered)

---

### BUG-042: String Concatenation + Operator Causes Invalid Number Error in HANA SQL

**⚠️ PERMANENT ID**: BUG-042 (kept throughout lifecycle per new numbering system)
**Discovered**: 2025-02-24, TRANSFORMATIONS_DETAILS.xml
**Resolved**: 2025-02-24
**Validation Time**: SUCCESS (user confirmed)

**Error**:
```
SAP DBTech JDBC: [339]: invalid number: not a valid number string ''
```

**Root Cause**:
The `_translate_string_concat_to_hana()` function was **backwards** — converting `||` to `+` instead of `+` to `||`. In HANA SQL, `||` is string concatenation and `+` is arithmetic only. The XML Column Engine uses `+` for concatenation. When `+` remained in the generated SQL, HANA tried arithmetic on strings → [339].

**XML Formula**:
```
if(leftstr("PARAMNM",1)='0',rightstr("PARAMNM",strlen("PARAMNM")-1),'/BIC/'+"PARAMNM")
```

**Solution Implemented**:
Reversed the function to convert `+` → `||` when adjacent to string literals:

```python
# In function_translator.py lines 594-611:
def _translate_string_concat_to_hana(formula: str) -> str:
    result = formula
    # Pattern: 'string' + something → 'string' || something
    result = re.sub(r"'\s*\+\s*", "' || ", result)
    # Pattern: something + 'string' → something || 'string'
    result = re.sub(r"\s*\+\s*'", " || '", result)
    return result
```

**Files Modified**:
- `src/xml_to_sql/sql/function_translator.py`: Lines 594-611 (_translate_string_concat_to_hana function)

**Generated SQL - CORRECT**:
```sql
ELSE '/BIC/' || (projection_2.PARAMNM) END AS FIELDNM
```

**Scope**: ⚠️ UNIVERSAL FIX - Applies to ALL XMLs automatically
- Converts `+` to `||` whenever adjacent to string literals (single-quoted values)
- Preserves arithmetic `+` between non-string operands
- Built into HANA mode translation pipeline

**Associated Conversion Rule**:
- **RULE**: Column Engine `+` (string concatenation) must become `||` in HANA SQL
- **Pattern**: `'literal' + column` or `column + 'literal'` → `'literal' || column`
- **Trigger**: Applied in `translate_raw_formula()` for every formula in HANA mode

**Discovery Example**:
- TRANSFORMATIONS_DETAILS.xml (where bug was first encountered)

---

### BUG-043: UNION ALL Empty String '' Causes Type Conversion Error with INTEGER Columns

**⚠️ PERMANENT ID**: BUG-043 (kept throughout lifecycle per new numbering system)
**Discovered**: 2025-02-24, TRANSFORMATIONS_DETAILS.xml
**Resolved**: 2025-02-24
**Validation Time**: SUCCESS (user confirmed)

**Error**:
```
SAP DBTech JDBC: [339]: invalid number: not a valid number string ''
```

**Root Cause**:
XML `ConstantAttributeMapping` entries with `null="true"` and `value=""` should render as SQL `NULL`, not `''`. The parser ignored `null="true"` and always created empty string literals. In UNION ALL, HANA's type precedence promotes columns to INTEGER when any branch has an INT column — then `''` in other branches fails to convert.

**XML Pattern**:
```xml
<mapping xsi:type="Calculation:ConstantAttributeMapping" target="LINE_NO" null="true" value=""/>
```

**Solution Implemented**:
Two surgical changes:

1. **Parser** (scenario_parser.py lines 421-425): When `null="true"` and value is empty, create `Expression(RAW, "NULL")` instead of `Expression(LITERAL, "")`
2. **Renderer** (renderer.py lines 1080-1082): Exclude SQL keywords (NULL, TRUE, FALSE) from BUG-027's column qualification logic

```python
# Parser:
null_flag = mapping_el.get("null", "false").lower() == "true"
if null_flag and not constant_value:
    expr = Expression(ExpressionType.RAW, "NULL")

# Renderer:
if result.upper() not in ('NULL', 'TRUE', 'FALSE'):
    return f"{table_alias}.{result}"
```

**Files Modified**:
- `src/xml_to_sql/parser/scenario_parser.py`: Lines 421-425 (_parse_mappings function)
- `src/xml_to_sql/sql/renderer.py`: Lines 1080-1082 (_render_expression function)

**Generated SQL - CORRECT**:
```sql
-- Before: '' AS LINE_NO (type conflict with INT)
-- After:  NULL AS LINE_NO (type-compatible with anything)
```

**Scope**: ⚠️ UNIVERSAL FIX - Applies to ALL XMLs automatically
- Handles any `ConstantAttributeMapping` with `null="true"` in any UNION node
- Also protects RAW "NULL" expressions from incorrect column qualification
- Built into parser and renderer — no manual intervention needed

**Associated Conversion Rule**:
- **RULE**: `ConstantAttributeMapping null="true"` must render as SQL `NULL`, never `''`
- **Pattern**: UNION branches padding missing columns
- **Trigger**: Parser checks `null` attribute on every ConstantAttributeMapping during XML parsing

**Discovery Example**:
- TRANSFORMATIONS_DETAILS.xml (where bug was first encountered)

**Applies To**:
- ALL XMLs with numeric aggregations (SUM/AVG/STDDEV/VAR) on non-numeric columns

**⚠️ REGRESSION NOTE**: This fix introduced BUG-045 — the `null_flag` branch forgot to assign `data_type`, causing `UnboundLocalError` when `ConstantAttributeMapping null="true"` was the first mapping processed (e.g., DSO.xml). Fixed in same session. See BUG-045.

---

### BUG-044: RIGHTSTRU / LEFTSTRU Unicode Functions Not Recognized in HANA SQL

**⚠️ PERMANENT ID**: BUG-044 (kept throughout lifecycle per new numbering system)
**Discovered**: 2025-02-26, INFOOBJECTS.xml
**Resolved**: 2025-02-26
**Validation Time**: HANA validated 2025-02-26

**Error**:
```
SAP DBTech JDBC: [328]: invalid name of function or procedure: RIGHTSTRU: line 12 col 110 (at pos 545)
```

**Root Cause**:
`rightstru()` and `leftstru()` are Unicode-aware variants of `rightstr()` and `leftstr()` from SAP Column Engine. The function catalog had mappings for `RIGHTSTR` → `RIGHT` and `LEFTSTR` → `LEFT`, but was missing the Unicode variants.

HANA SQL's `RIGHT()` and `LEFT()` functions already handle Unicode (NVARCHAR) natively, so the mapping is identical.

**⚠️ CRITICAL LESSON LEARNED — DUPLICATE CATALOG FILES**:
This project has TWO `functions.yaml` files:
1. `src/xml_to_sql/catalog/data/functions.yaml` — **THIS IS THE ONE THE CODE USES** (loaded via `xml_to_sql.catalog.data` Python package)
2. `catalog/hana/data/functions.yaml` — **DOCUMENTATION MIRROR ONLY** (NOT used by running code)

Initial fix attempt was applied to file #2 (wrong file), causing the fix to have no effect. After discovering the mismatch, fix was applied to file #1 (correct file). **Always edit `src/xml_to_sql/catalog/data/functions.yaml` for catalog changes.**

**Solution Implemented**:
Added two entries to `src/xml_to_sql/catalog/data/functions.yaml` (the CORRECT file):
```yaml
- name: LEFTSTRU
  handler: rename
  target: "LEFT"

- name: RIGHTSTRU
  handler: rename
  target: "RIGHT"
```

Also mirrored to `catalog/hana/data/functions.yaml` for documentation consistency.

**Files Modified**:
- `src/xml_to_sql/catalog/data/functions.yaml`: Added LEFTSTRU and RIGHTSTRU mappings (PRIMARY)
- `catalog/hana/data/functions.yaml`: Added same (mirror copy)

**Scope**: ⚠️ UNIVERSAL FIX - Catalog-only, applies automatically to all future XMLs

**Associated Conversion Rule**:
- **RULE**: SAP Column Engine Unicode functions (`*STR` + `U` suffix) map to same HANA SQL target as non-Unicode variants
- **Pattern**: `LEFTSTRU()` → `LEFT()`, `RIGHTSTRU()` → `RIGHT()`, potentially `STRLENU()` → `LENGTH()` if encountered
- **Generalization**: Any future `*U` variant should be checked against existing catalog and mapped identically

**Discovery Example**:
- INFOOBJECTS.xml (where bug was first encountered)

---

### BUG-045: BUG-043 Regression — UnboundLocalError for data_type in Null Mapping Branch

**⚠️ PERMANENT ID**: BUG-045 (kept throughout lifecycle per new numbering system)
**Discovered**: 2025-02-26, DSO.xml
**Resolved**: 2025-02-26
**Validation Time**: Conversion successful (awaiting HANA validation)

**Error**:
```
Conversion failed: cannot access local variable 'data_type' where it is not associated with a value
```

**Root Cause**:
BUG-043 fix added a new branch in `_parse_mappings()` for `ConstantAttributeMapping null="true"` that created `Expression(ExpressionType.RAW, "NULL")` but **forgot to assign `data_type`**. Line 438 (`data_type=data_type` in `AttributeMapping()`) then raised `UnboundLocalError`.

This only manifested when `null="true"` was the **first** mapping processed in a UNION input — if any previous mapping in the same loop iteration had already assigned `data_type`, the variable would carry over from the prior iteration (Python scoping), masking the bug. TRANSFORMATIONS_DETAILS.xml didn't trigger this because `data_type` was always assigned by an earlier mapping before reaching the null branch. DSO.xml has `ConstantAttributeMapping null="true"` as an early mapping in Union_2 (4 entries: KYFTP, AGGRGEN, AGGRCHA, UNINM), exposing the uninitialized variable.

**XML Pattern**:
```xml
<!-- DSO.xml Union_2 — null="true" mappings appear early in the mapping list -->
<mapping xsi:type="Calculation:ConstantAttributeMapping" target="KYFTP" null="true" value=""/>
<mapping xsi:type="Calculation:ConstantAttributeMapping" target="AGGRGEN" null="true" value=""/>
```

**Solution Implemented**:
One surgical line added — assign `data_type` in the null branch (identical to the other two branches):

```python
# scenario_parser.py line 425 (inside _parse_mappings)
if null_flag and not constant_value:
    data_type = guess_attribute_type(target)  # BUG-045: was missing, caused UnboundLocalError
    expr = Expression(ExpressionType.RAW, "NULL")
```

**Before (BUG-043 fix, incomplete)**:
```python
if null_flag and not constant_value:
    # data_type NOT assigned here — UnboundLocalError!
    expr = Expression(ExpressionType.RAW, "NULL")
```

**After (BUG-045 fix)**:
```python
if null_flag and not constant_value:
    data_type = guess_attribute_type(target)  # Now assigned in ALL three branches
    expr = Expression(ExpressionType.RAW, "NULL")
```

**Files Modified**:
- `src/xml_to_sql/parser/scenario_parser.py`: Line 425 — added `data_type = guess_attribute_type(target)` in the `null_flag` branch

**Scope**: ⚠️ UNIVERSAL FIX — Prevents crash for ANY XML with `ConstantAttributeMapping null="true"` appearing as first mapping in a UNION input.

**Associated Conversion Rule**:
- **RULE**: All three branches in `_parse_mappings()` (null mapping, constant mapping, column mapping) MUST assign `data_type` before the `AttributeMapping()` constructor on line 438
- **Pattern**: BUG-043 regression — incomplete variable initialization in new code branch

**Discovery Example**:
- DSO.xml (721-line Calculation:scenario, 10 Projections, 6 Joins, 2 Unions, 8 data sources in SAPK5D schema, dataCategory="DIMENSION")

**Key Lesson**:
When adding a new branch to existing code, ensure ALL variables used after the if/elif/else block are initialized in EVERY branch. Python variable scoping allows loop-variable leakage that can mask uninitialized variables in testing.

---

### BUG-046: SAP case() Function Not Converted to SQL CASE WHEN Expression

**Bug ID**: BUG-046
**Discovered**: 2025-02-28, SESSION 13
**XML**: INFOOBJECTS.xml
**Status**: ✅ VALIDATED (51ms)
**Instance Type**: BW (SAPK5D)

**Error**:
```
SAP DBTech JDBC: [257]: sql syntax error: incorrect syntax near ",": line 60 col 36 (at pos 2296)
```

**Root Cause**:
SAP Calculation View COLUMN_ENGINE formulas use `case(value, match1, result1, ..., default)` — a function-call syntax for simple CASE expressions. This is NOT valid SQL syntax. The `translate_raw_formula()` pipeline had handlers for `IF()`, `IN()`, string concatenation, etc., but no handler for `case()`. The formula passed through literally as `case(...)` in the generated SQL.

**XML Pattern**:
```xml
<calculatedViewAttribute datatype="NVARCHAR" id="INTLEN" length="6" expressionLanguage="COLUMN_ENGINE">
  <formula>case("DATATP",'CURR','000015','DATS','000008','DEC','000017','FLTP','000016','INT4','000010','QUAN','000017','TIMS','000006','000000')</formula>
</calculatedViewAttribute>
```

**Before** (invalid SQL):
```sql
case(SAPABAP1.RSDKYF.DATATP,'CURR','000015','DATS','000008','DEC','000017',...,'000000') AS INTLEN
```

**After** (valid HANA SQL):
```sql
CASE SAPABAP1.RSDKYF.DATATP WHEN 'CURR' THEN '000015' WHEN 'DATS' THEN '000008' WHEN 'DEC' THEN '000017' ... ELSE '000000' END AS INTLEN
```

**Fix**:
Added `_convert_case_function_to_sql()` function to `function_translator.py`. Uses same parenthesis-counting argument extraction pattern as `_convert_if_to_case_for_hana()`. First argument is the value expression, subsequent pairs are WHEN/THEN, optional last odd arg is ELSE default.

**Files Modified**:
- `src/xml_to_sql/sql/function_translator.py`:
  - Lines 628-706: New function `_convert_case_function_to_sql()`
  - Line 241: Added call in HANA mode pipeline (before IF→CASE conversion)
  - Line 250: Added call in Snowflake mode pipeline (before IF→IFF conversion)

**Scope**: ⚠️ UNIVERSAL FIX — Applies to ANY XML with COLUMN_ENGINE `case()` function in calculated view attributes. Both HANA and Snowflake modes covered.

**Associated Conversion Rule**:
- **RULE**: SAP `case(value, match1, result1, ..., default)` → SQL `CASE value WHEN match1 THEN result1 ... ELSE default END`
- **Priority**: 38 (before IF→CASE at Priority 40)

**Discovery Example**:
- INFOOBJECTS.xml: Projection_7 (RSDKYF table) had 3 calculated columns using `case()` for INTLEN, OUTPUTLEN, DECIMAL — all mapping DATATP column to numeric string codes.

**Key Lesson**:
When encountering a new SAP formula function, check whether `translate_raw_formula()` has a handler for it. The existing `CASE` handler in the function translator (lines 135-145) only handles `ExpressionType.FUNCTION` nodes, not raw formula text.

---

## BUG-047: Single-Input Union Node Generates Broken Placeholder SQL

**Status**: ✅ VALIDATED IN HANA (2026-03-03)
**Discovered**: 2026-03-03, ADSO.xml
**Fixed**: 2026-03-03, SESSION 14

**Error**:
```
SAP DBTech JDBC: [257]: sql syntax error: incorrect syntax near ")": line 75 col 3 (at pos 2590)
```

**Root Cause**:
`_render_union()` in renderer.py had `if len(node.inputs) < 2:` which blocked ALL unions with fewer than 2 inputs, including single-input unions. A single-input Union is a valid SAP BW design pattern — used to rename columns (ADSONM → INFOCUBE) and inject constant values (SOURCE_TYPE = 'ADSO'). The early return generated `SELECT 1 AS placeholder`, orphaning the real data CTE.

**Solution**:
Changed `if len(node.inputs) < 2:` → `if len(node.inputs) == 0:` at renderer.py line 835.
With exactly 1 input, the normal rendering loop executes: `"\nUNION ALL\n".join([single_query])` = `single_query` (no UNION keyword added), producing a clean pass-through SELECT with column mappings.

**Files Modified**:
- `pipelines/xml-to-sql/src/xml_to_sql/sql/renderer.py` line 835: `< 2` → `== 0`

**Associated Rule**: Single-input Union = pass-through projection with column remapping. No new HANA_CONVERSION_RULES entry needed (renderer behavior, not SQL translation rule).

**Scope**: UNIVERSAL — affects any XML where a Union node has exactly 1 input branch.

---

## BUG-048: DECFLOAT Column Engine Function Not Recognized in HANA SQL

**Status**: ✅ VALIDATED IN HANA (2026-03-03)
**Discovered**: 2026-03-03, ADSO.xml
**Fixed**: 2026-03-03, SESSION 14

**Error**:
```
SAP DBTech JDBC: [328]: invalid name of function or procedure: DECFLOAT: line 37 col 9 (at pos 1289)
```

**Root Cause**:
`decfloat()` is a SAP Column Engine type-cast function (cast to decimal floating point). It is not a HANA SQL function. The function catalog had no mapping for it, so it passed through unchanged and HANA rejected it with [328].

**XML Formula**:
```
decfloat(format(adddays(now(),-365),'YYYYMMDD') + '000000')
```

**Generated SQL (broken)**:
```sql
decfloat(TO_VARCHAR(ADD_DAYS(CURRENT_TIMESTAMP, -365), 'YYYYMMDD') || '000000') AS EXECUTED_AFTER
```

**Solution**:
Added catalog entry to `src/xml_to_sql/catalog/data/functions.yaml`:
```yaml
- name: DECFLOAT
  handler: rename
  target: "TO_DECIMAL"
```
Also mirrored to `catalog/hana/data/functions.yaml`.

**Generated SQL (fixed)**:
```sql
TO_DECIMAL(TO_VARCHAR(ADD_DAYS(CURRENT_TIMESTAMP, -365), 'YYYYMMDD') || '000000') AS EXECUTED_AFTER
```

**Files Modified**:
- `pipelines/xml-to-sql/src/xml_to_sql/catalog/data/functions.yaml`: Added DECFLOAT → TO_DECIMAL
- `pipelines/xml-to-sql/catalog/hana/data/functions.yaml`: Mirror copy updated

**Scope**: UNIVERSAL — any XML using `decfloat()` in calculated view attributes (common in BW metadata views with the Executed_After / LASTUSED comparison pattern).

---

### BUG-051: BOOLEAN Calculated Columns Rendered as Bare Expressions in HANA SQL

**Original Bug**: BUG-051
**Discovered**: 2026-03-26, TRANFORMATIONS.xml
**Resolved**: 2026-03-26 (awaiting HANA validation)

**Error**:
```
SAP DBTech JDBC: [257]: sql syntax error: incorrect syntax near "=": line 35 col 39 (at pos 1301)
```

**Problem**:
Calculated columns with `datatype="BOOLEAN"` in XML render boolean expressions directly in SELECT:
```sql
-- WRONG: bare boolean expression
LEFT(TABLE.LINE, 1)='*' or LEFT(TABLE.LINE, 5) = '... "' AS COMMENTS
-- CORRECT: wrapped in CASE WHEN
CASE WHEN (LEFT(TABLE.LINE, 1)='*' or LEFT(TABLE.LINE, 5) = '... "') THEN 1 ELSE 0 END AS COMMENTS
```

**Root Cause**:
HANA SQL does not support bare boolean expressions in SELECT lists. The Column Engine `datatype="BOOLEAN"` is valid in XML but needs translation to integer via CASE WHEN.

**Solution**:
Added BOOLEAN detection in all 3 calculated column rendering paths in `renderer.py`:
```python
# BUG-051: HANA SQL doesn't support bare boolean expressions in SELECT.
if (ctx.database_mode == DatabaseMode.HANA
        and calc_attr.data_type is not None
        and calc_attr.data_type.type.value == "BOOLEAN"):
    calc_expr = f"CASE WHEN ({calc_expr}) THEN 1 ELSE 0 END"
```

**Files Modified**:
- `pipelines/xml-to-sql/src/xml_to_sql/sql/renderer.py`: Lines 443-448 (projection), 657-661 (JOIN), 825-829 (aggregation)

**Scope**: UNIVERSAL — any XML with `datatype="BOOLEAN"` calculated view attributes.

---

### BUG-052: SqlScriptView Nodes Generate Placeholder Instead of Embedded SQL

**Original Bug**: BUG-052
**Discovered**: 2026-03-26, USED_HIERARCHIES.xml
**Resolved**: 2026-03-26 (awaiting HANA validation)

**Error**:
```
SAP DBTech JDBC: [257]: sql syntax error: incorrect syntax near ")": line 5 col 3 (at pos 104)
SAP DBTech JDBC: [362]: invalid schema name: SAPK5D: line 31 col 12 (at pos 846)
```

**Problem**:
Script-based calculation views (`calculationScenarioType="SCRIPT_BASED"`, `xsi:type="Calculation:SqlScriptView"`) contain embedded SQL procedure bodies in `<definition>`. The converter ignored this and generated `SELECT 1 AS placeholder`.

**Root Cause**:
1. Parser: `SqlScriptView` type not recognized — falls to generic CALCULATION node
2. `<definition>` element never parsed
3. Renderer: CALCULATION nodes with no inputs return placeholder
4. Schema mismatch: script SQL has hardcoded schemas from authoring system

**Solution** (three parts):
1. **Model** (`models.py`): Added `default_schema` field to `ScenarioMetadata`
2. **Parser** (`scenario_parser.py`): Extract `<definition>` text into `node.properties["script_definition"]`; parse `<defaultSchema schemaName="..."/>` into metadata
3. **Renderer** (`renderer.py`): New `_extract_select_from_script()` helper extracts SELECT from procedure body, resolves `defaultSchema` through `schema_overrides` to auto-replace hardcoded schemas

**Auto Schema Resolution** (no manual config needed for hardcoded schemas):
- XML `<defaultSchema schemaName="ABAP"/>` → resolve via overrides → `SAPABAP1`
- Detect `"SAPK5D"` in script FROM clauses → auto-replace with `"SAPABAP1"`

**Files Modified**:
- `pipelines/xml-to-sql/src/xml_to_sql/domain/models.py`: Added `default_schema` to ScenarioMetadata
- `pipelines/xml-to-sql/src/xml_to_sql/parser/scenario_parser.py`: Lines 99-104, 255-260
- `pipelines/xml-to-sql/src/xml_to_sql/sql/renderer.py`: Lines 953-957, 1309-1349

**Scope**: Any XML with `calculationScenarioType="SCRIPT_BASED"` and `SqlScriptView` nodes.

---

### BUG-053: Integer-Declared Calc Columns Returning String Literals Break Downstream SUM/AVG

**Original Bug**: BUG-053
**Discovered**: 2026-05-10, CV_E2E_VST.xml (Maccabi BW_ON_HANA)
**Resolved**: 2026-05-10 ✅ VALIDATED in HANA (CREATE VIEW: 75ms)

**Error**:
```
SAP DBTech JDBC: [266]: inconsistent datatype: only numeric type is available for SUM/AVG/STDDEV/VAR function: line 677 col 9
```

**Problem**:
Calculated column declared as integer (`<inlineType primitiveType="SMALLINT"/>`) has formula returning string literals:
```xml
<element name="CC_PATTEST">
  <inlineType primitiveType="SMALLINT"/>
  <calculationDefinition language="COLUMN_ENGINE">
    <formula>if("_BIC_EYHERAZ01"='0000001115','1','0')</formula>
  </calculationDefinition>
</element>
```
Generated SQL was:
```sql
-- WRONG: actual SQL type is VARCHAR despite declared SMALLINT
CASE WHEN ... THEN '1' ELSE '0' END AS CC_PATTEST
SUM(CC_PATTEST)  -- ERROR [266]
```

**Root Cause**:
HANA Column Engine auto-coerces string literals to declared type, but standard SQL doesn't. Renderer ignored the declared XML type at calc column level.

**Solution**:
Wrap rendered calc expression with `TO_INTEGER()` when declared type is integer-class (NUMBER with scale=0):
```python
# BUG-053: Wrap integer-declared calc columns with TO_INTEGER so downstream SUM/AVG works.
elif (ctx.database_mode == DatabaseMode.HANA
        and calc_attr.data_type is not None
        and calc_attr.data_type.type.value == "NUMBER"
        and calc_attr.data_type.scale == 0):
    calc_expr = f"TO_INTEGER({calc_expr})"
```
Generated SQL becomes:
```sql
-- CORRECT: TO_INTEGER coerces string literals to integers
TO_INTEGER(CASE WHEN ... THEN '1' ELSE '0' END) AS CC_PATTEST
SUM(CC_PATTEST)  -- works
```

**Files Modified**:
- `pipelines/xml-to-sql/src/xml_to_sql/sql/renderer.py`: 3 locations (projection ~449, JOIN ~671, aggregation ~845)

**Scope**: UNIVERSAL — any XML with integer-typed calc columns (SMALLINT/INTEGER/BIGINT/TINYINT). Same pattern as BUG-040 but applied at calc column level (BUG-040 applies at SUM/AVG level for VARCHAR source columns).

---

### BUG-054: HANA Studio Exports Malformed XML with Unescaped Quotes in leftInput/rightInput

**Original Bug**: BUG-054
**Discovered**: 2026-05-10 (recurrence of SESSION 16 manual fix — durable converter-side solution)
**Resolved**: 2026-05-10 (awaiting validation on fresh HANA Studio re-export)

**Error**:
```
XML parsing error: attributes construct error, line 514, column 69
This file is not valid XML. Please check: ...
```

**Problem**:
HANA Studio exports `leftInput`/`rightInput` attribute values with unescaped literal `"` quotes around schema names:
```xml
<join leftInput="#//Join_2/Projection_1"
      rightInput="#//Join_2/"ABAP"./BIC/QEYPOSPER"
      joinType="leftOuter">
```
lxml (and any standards-compliant XML parser) correctly rejects this — the `"ABAP"` characters prematurely terminate the attribute value. HANA Studio's own parser is lenient with its own export bugs, but the converter (and browsers) aren't.

This was first encountered in SESSION 16 and fixed manually by editing the source XML. The second occurrence (fresh HANA Studio re-export, same XML) confirmed it would recur for every user, every re-export. A converter-side fix is required.

**Root Cause**:
HANA Studio export bug — should emit `&quot;` for inner quotes but emits literal `"`. The converter previously passed XML bytes directly to lxml.parse() with no pre-processing.

**Solution**:
New module `parser/xml_sanitizer.py` exporting `sanitize_hana_xml_bytes(xml_content: bytes) -> bytes`:
```python
HANA_MALFORMED_QUOTE_PATTERN = re.compile(
    rb'((?:left|right)Input="[^"]*?)"([A-Z][A-Z0-9_]*)"([^"]*?")'
)

def sanitize_hana_xml_bytes(xml_content: bytes) -> bytes:
    if not xml_content:
        return xml_content
    if b'leftInput' not in xml_content and b'rightInput' not in xml_content:
        return xml_content  # fast bail-out for clean XMLs
    return HANA_MALFORMED_QUOTE_PATTERN.sub(rb'\1&quot;\2&quot;\3', xml_content)
```

**Injection points** (all 4 XML entry points covered):
1. `parser/scenario_parser.py:85` — `parse_scenario()` reads bytes → sanitize → `etree.parse(BytesIO(...))`. Covers CLI + web temp file path AND ColumnView dispatch (CV_E2E_VST is a ColumnView).
2. `web/api/routes.py:90, 214, 436` — 3 FastAPI handlers sanitize right after `await file.read()`. Covers entire web upload surface including downstream `prettify_xml` and `converter.py` validation parse.
3. `web/services/converter.py:172` — defensive sanitize before validation `etree.parse()`. Idempotent if route handlers already sanitized.
4. `cli/app.py:139` — CLI secondary parse for format detection.

**False-positive analysis** (verified across 64 source XMLs):
- `<entity>#//"ABAP"./BIC/X</entity>` — text content with literal quotes is valid XML, regex doesn't match (anchored to `leftInput=` / `rightInput=` only).
- `<comment text="&quot;X&quot; = '00'"/>` — different attribute, regex doesn't match.
- Already-escaped `&quot;` — no literal `"` to match → mathematically idempotent.
- Zero legitimate uses of literal `"` inside `leftInput`/`rightInput` found anywhere in source tree.

**Files Modified**:
- `pipelines/xml-to-sql/src/xml_to_sql/parser/xml_sanitizer.py` — NEW MODULE
- `pipelines/xml-to-sql/src/xml_to_sql/parser/scenario_parser.py` (parse_scenario)
- `pipelines/xml-to-sql/src/xml_to_sql/web/api/routes.py` (3 FastAPI handlers)
- `pipelines/xml-to-sql/src/xml_to_sql/web/services/converter.py` (validation parse)
- `pipelines/xml-to-sql/src/xml_to_sql/cli/app.py` (format detection parse)

**Tests run**:
- Sanitizer unit: malformed → escaped output ✓
- Idempotence: twice == once ✓
- No-op on clean XML: unchanged ✓
- End-to-end on user's failing CV_E2E_VST (1).xml from Downloads: parses + renders successfully ✓
- Regression on 7 validated XMLs (CV_EQUIPMENT_STATUSES, CV_INVENTORY_ORDERS, CV_TOP_PTHLGY, CV_PURCHASE_ORDERS, INFOOBJECTS, ADSO, USED_HIERARCHIES): zero malformed segments detected, all render identically ✓

**Scope**: UNIVERSAL — any future HANA Studio re-export with this pattern is auto-fixed. No source XML editing needed by users.

---

## Statistics

**Total Solved**: 40 (SOLVED-001 through SOLVED-028, BUG-029, BUG-030, BUG-032, BUG-033, BUG-034, BUG-035, BUG-040, BUG-042, BUG-043, BUG-044, BUG-045, BUG-046, BUG-047, BUG-048, BUG-051, BUG-052, BUG-053) + BUG-054 awaiting validation
**Total Pending**: 3 (BUG-019, BUG-002, BUG-003)
**XMLs Validated**: 22 (CV_E2E_VST validated 2026-05-10, 75ms)
**Latest Fix**: BUG-054 ✅ FIXED (SESSION 17, 2026-05-10) — HANA Studio XML pre-processor (xml_sanitizer module)

**Time to Resolution**:
- BUG-004: < 1 hour (same session)
- BUG-029: Same session (discovered and fixed with surgical precision)
- BUG-030: Same session
- BUG-032: Same session (discovered and fixed)
- BUG-033: Same session (discovered and fixed)

---

**Process**: Bug discovered → Ticket created in BUG_TRACKER.md → Solution implemented → Moved to SOLVED_BUGS.md with full documentation

