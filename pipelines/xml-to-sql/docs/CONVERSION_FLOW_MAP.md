# XML-to-SQL Conversion Flow Map

**Purpose**: Complete visual representation of the conversion pipeline
**Date**: 2025-11-20
**Session**: 8

---

## High-Level Pipeline Overview

```
┌─────────────┐
│   INPUT     │
│ (XML File)  │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│    ENTRY POINTS                     │
│  ┌────────────┐  ┌──────────────┐  │
│  │  Web UI    │  │  CLI Tool    │  │
│  └─────┬──────┘  └──────┬───────┘  │
└────────┼─────────────────┼──────────┘
         │                 │
         └────────┬────────┘
                  ▼
┌─────────────────────────────────────┐
│   STAGE 1: PARSING                  │
│   XML → Intermediate Representation │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   STAGE 2: SQL GENERATION           │
│   IR → SQL String                   │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   STAGE 3: POST-PROCESSING          │
│   Cleanup, Validation, Corrections  │
└──────────────┬──────────────────────┘
               │
               ▼
┌──────────────┴──────────────┐
│   OUTPUT                    │
│   (SQL Script + Metadata)   │
└─────────────────────────────┘
```

---

## Detailed Stage-by-Stage Flow

### ENTRY POINTS

```
┌─────────────────────────────────────────────────────────────┐
│  A. WEB UI ENTRY POINT                                      │
├─────────────────────────────────────────────────────────────┤
│  Location: src/xml_to_sql/web/app.py                       │
│  Endpoint: POST /api/convert/single                         │
│  Handler:  convert_single_xml_endpoint()                    │
│                                                              │
│  Input Parameters:                                          │
│    - file: UploadFile (XML content)                         │
│    - database_mode: "HANA" | "SNOWFLAKE"                   │
│    - hana_version: Optional                                 │
│    ✗ - hana_package: NOT USED (BUG-023 fix)               │
│    - auto_fix: boolean                                      │
│                                                              │
│  Calls: converter.convert_xml_to_sql()                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  B. CLI ENTRY POINT                                         │
├─────────────────────────────────────────────────────────────┤
│  Location: src/xml_to_sql/cli/app.py                       │
│  Command:  python -m xml_to_sql.cli.app convert            │
│                                                              │
│  Input Parameters:                                          │
│    --file: Path to XML                                      │
│    --mode: HANA | SNOWFLAKE                                 │
│    --hana-version: Optional                                 │
│    ✗ --hana-package: NOT USED (BUG-023 fix)               │
│    --output: Output file path                               │
│                                                              │
│  Calls: converter.convert_xml_to_sql()                     │
└─────────────────────────────────────────────────────────────┘
```

**Key Document**: None specific - entry points are straightforward

**Note**: Both entry points converge at `converter.convert_xml_to_sql()`

---

### STAGE 1: PARSING (XML → IR)

```
┌──────────────────────────────────────────────────────────────────┐
│  STAGE 1.1: XML FORMAT DETECTION                                 │
├──────────────────────────────────────────────────────────────────┤
│  Script: src/xml_to_sql/parser/xml_format_detector.py           │
│  Function: detect_xml_format()                                   │
│                                                                   │
│  Detects:                                                         │
│    - HANA 1.x vs HANA 2.x format                                 │
│    - BW vs ECC instance type                                     │
│    - Recommends HANA version                                     │
│                                                                   │
│  Document: None - heuristic-based detection                      │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  STAGE 1.2: XML PARSING                                          │
├──────────────────────────────────────────────────────────────────┤
│  Script: src/xml_to_sql/parser/calculation_view_parser.py       │
│  Main Class: CalculationViewParser                               │
│                                                                   │
│  Parses XML sections:                                            │
│    1. DataSources (tables, views, other CVs)                    │
│    2. Nodes (Projection, Join, Aggregation, etc.)               │
│    3. Mappings (column transformations)                          │
│    4. Filters (WHERE conditions)                                 │
│    5. Calculated Attributes (computed columns)                   │
│    6. Logical Model (final output structure)                     │
│                                                                   │
│  ⚠️ CRITICAL: DataSource.source_type identification             │
│     - TABLE                                                      │
│     - VIEW                                                       │
│     - CALCULATION_VIEW ← (BUG-025 fix location)                 │
│                                                                   │
│  Document: None - follows SAP XML schema                         │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  STAGE 1.3: INTERMEDIATE REPRESENTATION CREATION                 │
├──────────────────────────────────────────────────────────────────┤
│  Script: src/xml_to_sql/domain/*.py                             │
│  Data Classes:                                                    │
│    - Scenario (top-level IR)                                     │
│    - DataSource                                                  │
│    - ProjectionNode, JoinNode, AggregationNode, etc.            │
│    - Mapping, Filter, CalculatedAttribute                        │
│                                                                   │
│  Output: Scenario IR object                                      │
│                                                                   │
│  Document: None - internal data structures                       │
└──────────────────────────────────────────────────────────────────┘
```

**Key Documents for Stage 1**:
- None specific - parser follows SAP HANA Calculation View XML schema
- Internal: `src/xml_to_sql/domain/types.py` defines enums and types

---

### STAGE 2: SQL GENERATION (IR → SQL)

This is where most conversion logic lives and where our BUG fixes are located.

```
┌──────────────────────────────────────────────────────────────────┐
│  STAGE 2.1: VIEW NAME & SCHEMA DETERMINATION                     │
├──────────────────────────────────────────────────────────────────┤
│  Script: src/xml_to_sql/web/services/converter.py               │
│  Location: Lines 304-319                                         │
│  Function: convert_xml_to_sql()                                  │
│                                                                   │
│  Logic:                                                           │
│    1. Get scenario_id from IR                                    │
│    2. Set effective_view_schema:                                 │
│       - HANA mode: "_SYS_BIC" (default)                         │
│       - Other: from parameter or None                            │
│                                                                   │
│    ⚠️ BUG-023 FIX LOCATION (Lines 312-319):                    │
│       CRITICAL: NO package path in CREATE VIEW                   │
│       qualified_view_name = f"{schema}.{scenario_id}"           │
│       NOT: f"{schema}.{package}/{scenario_id}"                  │
│                                                                   │
│  Document: BUG_TRACKER.md (BUG-023)                             │
│            llm_handover.md (SESSION 8)                           │
│            HANA_CONVERSION_RULES.md (PRINCIPLE #1)              │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  STAGE 2.2: SQL RENDERING - MAIN ORCHESTRATION                   │
├──────────────────────────────────────────────────────────────────┤
│  Script: src/xml_to_sql/sql/renderer.py                         │
│  Function: render_scenario()                                     │
│  Location: Lines 1133-1215                                       │
│                                                                   │
│  ⚠️ BUG-028: CTE Topological Sort Ordering                      │
│  Discovery: 2025-11-22 SESSION 7                                 │
│  Validated: CV_ELIG_TRANS_01.xml (awaiting final validation)     │
│                                                                   │
│  Problem: CTEs generated in wrong order causing "table not found"│
│  errors when CTE referenced another CTE defined later            │
│                                                                   │
│  Fix: _topological_sort() function (Lines 298-313)               │
│  - Uses _clean_ref() to normalize input IDs                      │
│  - Removes digit+slash prefixes: "#/0/prj_visits" → "prj_visits"│
│  - Ensures dependencies appear BEFORE referencing CTEs           │
│                                                                   │
│  Input ID Normalization Examples:                                │
│    "#/0/prj_visits" → _clean_ref() → "0/prj_visits"            │
│                     → regex       → "prj_visits" ✅             │
│    "#//prj_visits"  → _clean_ref() → "prj_visits" ✅           │
│    "#/prj_visits"   → _clean_ref() → "prj_visits" ✅           │
│                                                                   │
│  Orchestrates:                                                    │
│    1. CREATE VIEW statement generation                           │
│    2. CTE (WITH clause) generation (topologically sorted)        │
│    3. Final SELECT generation                                    │
│    4. Parameter cleanup (BUG-026 comprehensive fix)              │
│                                                                   │
│  Critical Patterns (from GOLDEN_COMMIT.yaml):                    │
│    - DROP VIEW ... CASCADE; CREATE VIEW ... AS                   │
│    - NO "CREATE OR REPLACE VIEW"                                 │
│    - CTE dependency order MUST be correct                        │
│    - Parameter cleanup for empty strings                         │
│                                                                   │
│  Document: GOLDEN_COMMIT.yaml (critical_patterns section)       │
│            HANA_CONVERSION_RULES.md (PRINCIPLE #3)               │
│            BUG_TRACKER.md (BUG-028)                              │
│            MANDATORY_PROCEDURES.md (Check 2)                     │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  STAGE 2.3: NODE RENDERING - TYPE-SPECIFIC                       │
├──────────────────────────────────────────────────────────────────┤
│  Script: src/xml_to_sql/sql/renderer.py                         │
│  Functions (different handlers for each node type):              │
│                                                                   │
│  A. PROJECTION NODES → _render_projection()                     │
│     Lines: 413-525                                               │
│     - Generates: SELECT columns FROM source WHERE filters        │
│     - Maps source columns to target aliases                      │
│     - Applies filters                                            │
│                                                                   │
│  B. JOIN NODES → _render_join()                                 │
│     Lines: 527-768                                               │
│     - Generates: SELECT ... FROM left JOIN right ON ...          │
│     ⚠️ BUG-024 FIX LOCATION (Lines 645-654):                   │
│        Qualifies calculated column references in JOINs           │
│        Pattern: ^"[A-Z_/0-9]+"$ → left_alias."COLNAME"         │
│     - Handles: INNER, LEFT OUTER, RIGHT OUTER, FULL OUTER       │
│                                                                   │
│  C. AGGREGATION NODES → _render_aggregation()                  │
│     Lines: 830-890                                               │
│     - Generates: SELECT agg_cols, GROUP BY ...                   │
│     - Handles: SUM, COUNT, AVG, MIN, MAX, etc.                  │
│                                                                   │
│  D. UNION NODES → _render_union()                              │
│     Lines: 770-828                                               │
│     - Generates: SELECT ... UNION ALL SELECT ...                │
│                                                                   │
│  Document: HANA_CONVERSION_RULES.md (transformation rules)      │
│            BUG_TRACKER.md (BUG-024)                              │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  STAGE 2.4: FROM CLAUSE RENDERING - DATA SOURCE RESOLUTION       │
├──────────────────────────────────────────────────────────────────┤
│  Script: src/xml_to_sql/sql/renderer.py                         │
│  Function: _render_from()                                        │
│  Location: Lines 942-970                                         │
│                                                                   │
│  ⚠️ BUG-025 FIX LOCATION:                                       │
│  Determines how to reference a data source:                      │
│                                                                   │
│  IF DataSource in scenario.data_sources:                         │
│    IF database_mode == HANA AND source_type == CALCULATION_VIEW:│
│      → Use package mapper to get package path                    │
│      → Return "_SYS_BIC"."Package.Path/CV_NAME"                 │
│         (WITH package path - for REFERENCES)                     │
│    ELSE (TABLE or VIEW):                                         │
│      → Return "SCHEMA"."TABLE_NAME"                             │
│                                                                   │
│  ELIF input_id in ctx.cte_aliases:                              │
│    → Return CTE alias (e.g., "prj_visits", "join_1")           │
│                                                                   │
│  Package Lookup:                                                 │
│    Script: src/xml_to_sql/package_mapper.py                     │
│    Function: get_package(cv_name)                                │
│    Database: data/package_mappings.db (SQLite)                   │
│    Fallback: package_mapping.json                                │
│                                                                   │
│  Document: HANA_CONVERSION_RULES.md (PRINCIPLE #1)              │
│            BUG_TRACKER.md (BUG-025)                              │
│            llm_handover.md (SESSION 8)                           │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  STAGE 2.5: EXPRESSION RENDERING                                 │
├──────────────────────────────────────────────────────────────────┤
│  Script: src/xml_to_sql/sql/renderer.py                         │
│  Function: _render_expression()                                  │
│  Location: Lines 996-1007                                        │
│                                                                   │
│  ⚠️ BUG-027: Column Qualification in JOIN Contexts              │
│  Discovery: 2025-11-22 SESSION 7                                 │
│  Validated: CV_ELIG_TRANS_01.xml (awaiting final validation)     │
│                                                                   │
│  Problem: RAW expressions in calculated columns didn't qualify   │
│  simple column names with table aliases in multi-table contexts  │
│                                                                   │
│  Fix: When table_alias provided AND expression is simple column: │
│    "CALDAY" AS CC_CALDAY → prj_visits."CALDAY" AS CC_CALDAY    │
│                                                                   │
│  Logic:                                                           │
│    IF expr.type == RAW:                                          │
│      AND table_alias provided (multi-table context)              │
│      AND result.strip('"').isidentifier() (simple column name)   │
│      AND not '(' in result (not a function)                      │
│    THEN: qualify with table_alias.result                         │
│                                                                   │
│  Handles expression types:                                       │
│    - COLUMN: Simple column reference                             │
│    - RAW: Raw SQL expressions (now qualified when needed)        │
│    - LITERAL: Constant values                                    │
│    - FUNCTION: Function calls (needs translation)                │
│    - OPERATION: Arithmetic, comparison, logical ops              │
│                                                                   │
│  Delegates to: function_translator.py for HANA functions         │
│                                                                   │
│  Document: HANA_CONVERSION_RULES.md (PRINCIPLE #4)              │
│            BUG_TRACKER.md (BUG-027)                              │
│            MANDATORY_PROCEDURES.md (Check 3)                     │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  STAGE 2.6: FUNCTION TRANSLATION                                 │
├──────────────────────────────────────────────────────────────────┤
│  Script: src/xml_to_sql/sql/function_translator.py              │
│  Main Function: translate_function()                             │
│                                                                   │
│  Critical Patterns (from GOLDEN_COMMIT.yaml):                    │
│    - IN() function: Converts XML IN(col, val1, val2)            │
│      to HANA: col IN (val1, val2)                               │
│      Function: _convert_in_function_to_operator()                │
│      Location: Line 639                                          │
│      Bug Reference: BUG-020 (SOLVED)                             │
│                                                                   │
│  Handles ~50+ SAP BEx functions:                                 │
│    - Date: datediff(), adddays(), addmonths(), etc.             │
│    - String: midstr(), left(), right(), length(), etc.          │
│    - Math: round(), ceil(), floor(), etc.                       │
│    - Logical: and(), or(), not(), match() [→ REGEXP_LIKE]      │
│                                                                   │
│  Document: HANA_CONVERSION_RULES.md (Rule #4: Function Mapping) │
│            docs/functions/ (function reference)                  │
└──────────────────────────────────────────────────────────────────┘
```

**Key Documents for Stage 2**:
- **HANA_CONVERSION_RULES.md**: All transformation rules (Priority 0-30)
- **BUG_TRACKER.md**: BUG-023, BUG-024, BUG-025 details
- **GOLDEN_COMMIT.yaml**: Critical patterns that must not change
- **llm_handover.md**: SESSION 8 - PRINCIPLE #1 explanation

---

### STAGE 3: POST-PROCESSING

```
┌──────────────────────────────────────────────────────────────────┐
│  STAGE 3.1: PARAMETER CLEANUP (BUG-026 COMPREHENSIVE FIX)        │
├──────────────────────────────────────────────────────────────────┤
│  Script: src/xml_to_sql/sql/renderer.py                         │
│  Function: _cleanup_hana_parameter_conditions()                  │
│  Location: Lines 1383-1491                                       │
│                                                                   │
│  ⚠️ BUG-026: Comprehensive Parameter Substitution Cleanup       │
│  Discovery: 2025-11-22 SESSION 7                                 │
│  Validated: CV_UPRT_PTLG.xml ✅ (27ms)                          │
│                                                                   │
│  Problem: HANA parameters ($IP_PARAM$) replaced with '' create   │
│  malformed SQL patterns                                          │
│                                                                   │
│  **12 Cleanup Patterns Applied:**                                │
│                                                                   │
│  Pattern 1: Remove orphaned IN keyword                           │
│    "CALMONTH" IN  = '000000' → "CALMONTH" = '000000'            │
│                                                                   │
│  Pattern 2: Remove TO_DATE/DATE comparisons with NULL            │
│    TO_DATE(column) >= NULL → (removed)                          │
│                                                                   │
│  Pattern 3: Clean orphaned OR/AND before closing paren           │
│    (condition OR ) → (condition)                                 │
│                                                                   │
│  Pattern 4: Clean double opening parens with operators           │
│    (( OR condition → (condition                                  │
│                                                                   │
│  Pattern 5: Clean orphaned AND/OR after opening paren            │
│    ( AND condition → (condition                                  │
│                                                                   │
│  Pattern 6: Remove malformed comparisons missing left operand    │
│    ( = '00000000') → (removed)                                  │
│                                                                   │
│  Pattern 7: Remove empty parentheses with just operators         │
│    ( AND ) → (removed)                                          │
│                                                                   │
│  Pattern 8: Remove empty string comparisons (4-quote patterns)   │
│    ( '''' = '') → (removed)                                     │
│                                                                   │
│  Pattern 9: Remove "COLUMN" IN ('') patterns                     │
│    "COLUMN" IN ('') or → (removed)                              │
│                                                                   │
│  Pattern 10: Remove empty WHERE with nested parentheses          │
│    WHERE (()) → (removed)                                       │
│                                                                   │
│  Pattern 11: Remove empty WHERE clauses                          │
│    WHERE () → (removed)                                         │
│                                                                   │
│  Pattern 12: Balance parentheses in WHERE condition              │
│    WHERE ((condition) → WHERE ((condition))                     │
│    Counts opening/closing parens and adds missing ones           │
│                                                                   │
│  Related Bugs: BUG-021, BUG-022 (partial fixes)                  │
│               BUG-026 (comprehensive fix)                        │
│                                                                   │
│  Document: HANA_CONVERSION_RULES.md (PRINCIPLE #2)              │
│            BUG_TRACKER.md (BUG-026)                              │
│            MANDATORY_PROCEDURES.md (Check 1)                     │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  STAGE 3.2: SQL VALIDATION                                       │
├──────────────────────────────────────────────────────────────────┤
│  Script: src/xml_to_sql/sql/validator.py                        │
│  Functions:                                                       │
│    - validate_sql(): Overall validation                          │
│    - validate_sql_structure(): Syntax checks                     │
│    - validate_query_completeness(): Required clauses             │
│    - validate_expressions(): Expression validity                 │
│    - validate_performance(): Optimization hints                  │
│    - validate_hana_sql(): HANA-specific checks                  │
│                                                                   │
│  Returns: ValidationResult with warnings/errors                  │
│                                                                   │
│  Document: None - internal validation logic                      │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  STAGE 3.3: AUTO-CORRECTION (Optional)                           │
├──────────────────────────────────────────────────────────────────┤
│  Script: src/xml_to_sql/sql/corrector.py                        │
│  Function: auto_correct_sql()                                    │
│                                                                   │
│  Corrections:                                                     │
│    - Fix common syntax errors                                    │
│    - Add missing parentheses                                     │
│    - Correct quote escaping                                      │
│    - Fix CASE statement structure                                │
│                                                                   │
│  Only runs if auto_fix=True                                      │
│                                                                   │
│  Document: None - heuristic corrections                          │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  STAGE 3.4: METADATA GENERATION                                  │
├──────────────────────────────────────────────────────────────────┤
│  Script: src/xml_to_sql/web/services/converter.py               │
│                                                                   │
│  Generates ConversionResult:                                     │
│    - sql: Final SQL string                                       │
│    - metadata: Statistics (nodes, filters, etc.)                 │
│    - validation_result: Warnings/errors                          │
│    - stages: Timeline of conversion stages                       │
│    - warnings: Issues found                                      │
│                                                                   │
│  Document: None - internal result structure                      │
└──────────────────────────────────────────────────────────────────┘
```

**Key Documents for Stage 3**:
- **GOLDEN_COMMIT.yaml**: Parameter cleanup patterns (BUG-021, BUG-022), incident log, validated XMLs
- **SOLVED_BUGS.md**: Historical bug fixes

---

### STAGE 4: ABAP GENERATION (Optional)

```
┌──────────────────────────────────────────────────────────────────┐
│  STAGE 4.1: ABAP REPORT GENERATION                               │
├──────────────────────────────────────────────────────────────────┤
│  Script: src/xml_to_sql/abap/generator.py                       │
│  Function: generate_abap_report()                                │
│  Entry Point: /api/convert/abap endpoint                         │
│                                                                   │
│  Purpose: Generate ABAP Report that exports CV data to CSV       │
│                                                                   │
│  Input:                                                           │
│    - sql_content: Generated SQL (DROP VIEW + CREATE VIEW)        │
│    - scenario_id: View name (e.g., "DSO")                        │
│    - column_names: Optional (auto-extracted if not provided)     │
│                                                                   │
│  Output: Complete ABAP Report source code for SE38               │
│                                                                   │
│  Generated Program Structure:                                     │
│    1. REPORT statement                                           │
│    2. SELECTION-SCREEN (parameters: path, GUI, header, delim)    │
│    3. TYPES: ty_data (matching SQL columns)                      │
│    4. DATA declarations                                          │
│    5. START-OF-SELECTION (main processing)                       │
│    6. FORM create_view (TRY-CATCH EXEC SQL)                     │
│    7. FORM fetch_data (cursor-based SELECT)                      │
│    8. FORM export_csv (CONCATENATE + header)                     │
│    9. FORM download_gui (GUI_DOWNLOAD)                           │
│    10. FORM download_server (OPEN DATASET)                       │
│    11. FORM cleanup_view (optional DROP)                         │
│                                                                   │
│  Document: docs/implementation/ABAP_GENERATOR_GUIDE.md           │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  STAGE 4.2: ABAP SYNTAX RULES (Critical Fixes)                   │
├──────────────────────────────────────────────────────────────────┤
│  5 Critical fixes implemented in generator.py:                   │
│                                                                   │
│  FIX 1: CONCATENATE - Space-Separated Operands                  │
│    Wrong:  CONCATENATE 'A', 'B' INTO lv_line.                   │
│    Right:  CONCATENATE 'A' 'B' INTO lv_line.                    │
│    Location: Line 240 (header_parts generation)                  │
│                                                                   │
│  FIX 2: TYPES - Comma Required on All Fields                    │
│    Wrong:  FIELD TYPE string    " No comma                      │
│    Right:  FIELD TYPE string,   " Comma required                │
│    Location: Line 234 (type_fields generation)                   │
│                                                                   │
│  FIX 3: No INITIALIZATION Block                                  │
│    Wrong:  INITIALIZATION. text-001 = 'value'.                  │
│    Right:  (removed entirely - TEXT symbols are read-only)      │
│    Location: Template - removed                                  │
│                                                                   │
│  FIX 4: TRY-CATCH for Native SQL                                │
│    Wrong:  EXEC SQL. DROP VIEW ... ENDEXEC.  " Crashes          │
│    Right:  TRY. EXEC SQL... CATCH cx_sy_native_sql_error.       │
│    Location: Lines 356-385 (CREATE_VIEW form)                    │
│                                                                   │
│  FIX 5: No Quote Escaping in EXEC SQL                           │
│    Wrong:  WHERE col = ''A''  " ABAP string escaping            │
│    Right:  WHERE col = 'A'    " Direct SQL                      │
│    Location: Lines 267-269 (no .replace("'", "''"))             │
│                                                                   │
│  Document: docs/implementation/ABAP_GENERATOR_GUIDE.md           │
└──────────────────────────────────────────────────────────────────┘
```

**Key Documents for Stage 4**:
- **ABAP_GENERATOR_GUIDE.md**: Complete ABAP generator reference with all syntax rules
- **llm_handover.md**: SESSION 12 notes

---

## Critical Decision Tree: Package Path Usage

This is where BUG-023 and BUG-025 fixes operate:

```
┌─────────────────────────────────────────────────────────────┐
│  PACKAGE PATH DECISION TREE                                 │
│  (PRINCIPLE #1 from HANA_CONVERSION_RULES.md)              │
└─────────────────────────────────────────────────────────────┘

Question: Where are we using a Calculation View name?

┌─────────────────────────────────────────────────────────────┐
│  CONTEXT A: CREATE VIEW Statement                           │
│  Location: converter.py lines 312-319                       │
├─────────────────────────────────────────────────────────────┤
│  Decision: NO PACKAGE PATH                                  │
│                                                              │
│  Format:                                                     │
│    CREATE VIEW "_SYS_BIC"."CV_NAME" AS                     │
│                                                              │
│  Why: Views are created DIRECTLY in _SYS_BIC catalog        │
│       Package structure is SOURCE location, not TARGET      │
│                                                              │
│  Bug Fixed: BUG-023                                         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  CONTEXT B: REFERENCING Another CV (in FROM/JOIN)          │
│  Location: renderer.py lines 942-970 (_render_from)        │
├─────────────────────────────────────────────────────────────┤
│  Decision: WITH PACKAGE PATH                                │
│                                                              │
│  Format:                                                     │
│    INNER JOIN "_SYS_BIC"."Package.Path/CV_NAME" ON ...     │
│                                                              │
│  Why: References must specify full path to locate CV        │
│       Package structure indicates SOURCE location           │
│                                                              │
│  How: Call get_package(cv_name) from package_mapper.py     │
│       Returns: "Macabi_BI.Eligibility"                      │
│       Construct: f"{package}/{cv_name}"                     │
│                                                              │
│  Bug Fixed: BUG-025                                         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  CONTEXT C: Base Table References                           │
│  Location: renderer.py lines 942-970 (_render_from)        │
├─────────────────────────────────────────────────────────────┤
│  Decision: USE SCHEMA.TABLE FORMAT                          │
│                                                              │
│  Format:                                                     │
│    FROM SAPABAP1."/BIC/AEZO_RW0200"                        │
│                                                              │
│  Why: Regular tables use standard schema.table format       │
│                                                              │
│  No bugs here - always worked correctly                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  CONTEXT D: CTE References                                  │
│  Location: renderer.py lines 942-970 (_render_from)        │
├─────────────────────────────────────────────────────────────┤
│  Decision: USE ALIAS ONLY                                   │
│                                                              │
│  Format:                                                     │
│    FROM prj_visits                                          │
│    INNER JOIN join_1 ON ...                                 │
│                                                              │
│  Why: CTEs are defined in WITH clause, use simple alias     │
│                                                              │
│  No bugs here - always worked correctly                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Documentation Cross-Reference Map

```
┌─────────────────────────────────────────────────────────────────┐
│  DOCUMENT                        │  GOVERNS STAGE/ASPECT         │
├──────────────────────────────────┼───────────────────────────────┤
│  HANA_CONVERSION_RULES.md        │  Stage 2: All SQL generation  │
│   - PRINCIPLE #1                 │    → Package path usage       │
│   - Rules 0-30                   │    → Transformation logic     │
│   - Priority system              │    → Decision making          │
├──────────────────────────────────┼───────────────────────────────┤
│  BUG_TRACKER.md                  │  Active bugs & investigation  │
│   - BUG-023 (Package path)       │    → converter.py fix         │
│   - BUG-024 (Column ambiguity)   │    → renderer.py JOIN fix     │
│   - BUG-025 (CV references)      │    → renderer.py FROM fix     │
├──────────────────────────────────┼───────────────────────────────┤
│  SOLVED_BUGS.md                  │  Historical bug fixes         │
│   - BUG-001 to BUG-022           │    → Pattern library          │
│   - Solutions & patterns         │    → Reference for new bugs   │
├──────────────────────────────────┼───────────────────────────────┤
│  GOLDEN_COMMIT.yaml              │  Critical protected patterns  │
│   - critical_patterns section    │    → Must not change          │
│   - Validated XMLs list          │    → Regression baseline      │
│   - Incident log                 │    → Lessons learned          │
├──────────────────────────────────┼───────────────────────────────┤
│  llm_handover.md                 │  Session history & context    │
│   - SESSION 1-8                  │    → Evolution of fixes       │
│   - Key decisions                │    → Architectural insights   │
│   - Lessons learned              │    → Future LLM reference     │
├──────────────────────────────────┼───────────────────────────────┤
│  BUG_TRACKER.md / SOLVED_BUGS.md │  Test results & validation    │
│   - Bug statuses and details     │    → Active and solved bugs   │
│   - Known issues                 │    → Limitations              │
│   (See GOLDEN_COMMIT.yaml for validated XMLs and execution times) │
├──────────────────────────────────┼───────────────────────────────┤
│  MANDATORY_PROCEDURES.md         │  Process enforcement          │
│   (.claude directory)            │    → Bug checking workflow    │
│                                  │    → Non-negotiable steps     │
├──────────────────────────────────┼───────────────────────────────┤
│  package_mappings.db             │  CV-to-package mapping data   │
│   (SQLite database)              │    → Used by get_package()    │
│                                  │    → Managed via Web UI       │
└──────────────────────────────────┴───────────────────────────────┘
```

---

## Bug Fix Location Map

```
┌─────────────────────────────────────────────────────────────────┐
│  BUG-023: CREATE VIEW Package Path                              │
├─────────────────────────────────────────────────────────────────┤
│  File: src/xml_to_sql/web/services/converter.py                │
│  Lines: 312-319                                                  │
│  Stage: 2.1 (View name determination)                           │
│  Fix: Removed package path logic from CREATE VIEW               │
│  Impact: ALL HANA Calculation View conversions                  │
│  Document: BUG_TRACKER.md lines 42-107                          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  BUG-024: Column Ambiguity in JOIN Calculated Columns           │
├─────────────────────────────────────────────────────────────────┤
│  File: src/xml_to_sql/sql/renderer.py                          │
│  Lines: 645-654                                                  │
│  Stage: 2.3 (JOIN node rendering)                               │
│  Fix: Qualify unqualified column refs with left_alias           │
│  Impact: JOINs with calculated columns referencing ambiguous cols│
│  Document: BUG_TRACKER.md lines 189-243                         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  BUG-025: CALCULATION_VIEW References                           │
├─────────────────────────────────────────────────────────────────┤
│  File: src/xml_to_sql/sql/renderer.py                          │
│  Lines: 942-970 (+ import at line 13)                           │
│  Stage: 2.4 (FROM clause rendering)                             │
│  Fix: Detect CALCULATION_VIEW type, add package path            │
│  Impact: XMLs that reference other Calculation Views            │
│  Document: BUG_TRACKER.md lines 110-187                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Diagram

```
┌──────────┐
│   XML    │ (bytes)
└────┬─────┘
     │
     ▼
┌─────────────────────┐
│  XML Parser         │ → detect_xml_format()
│  (lxml + custom)    │ → CalculationViewParser.parse()
└─────────┬───────────┘
          │
          ▼ (Scenario IR object)
┌─────────────────────────────────────────────────────────┐
│  Intermediate Representation (IR)                       │
│  - scenario.metadata (id, version)                      │
│  - scenario.data_sources {id → DataSource}              │
│  - scenario.nodes {id → Node}                           │
│  - scenario.logical_model (optional)                    │
└─────────┬───────────────────────────────────────────────┘
          │
          ▼ (IR + qualified_view_name)
┌─────────────────────────────────────────────────────────┐
│  SQL Renderer                                            │
│                                                          │
│  Context Setup:                                          │
│    - database_mode: DatabaseMode enum                   │
│    - hana_version: HanaVersion enum                     │
│    - schema mappings                                     │
│    - cte_aliases: {node_id → alias}                    │
│                                                          │
│  Rendering Loop:                                         │
│    FOR EACH node IN execution_order:                    │
│      CASE node.type:                                     │
│        Projection → _render_projection()                │
│        Join       → _render_join()                      │
│        Aggregation→ _render_aggregation()               │
│        Union      → _render_union()                     │
│      Store CTE in ctes[]                                │
│                                                          │
│  Output Assembly:                                        │
│    DROP VIEW {qualified_view_name} CASCADE;             │
│    CREATE VIEW {qualified_view_name} AS                 │
│    WITH                                                  │
│      {cte_1},                                            │
│      {cte_2},                                            │
│      ...                                                 │
│    SELECT * FROM {final_cte}                            │
└─────────┬───────────────────────────────────────────────┘
          │
          ▼ (SQL string)
┌─────────────────────────────────────────────────────────┐
│  Post-Processing                                         │
│  - _cleanup_hana_parameter_conditions()                 │
│  - validate_sql()                                        │
│  - auto_correct_sql() (optional)                        │
└─────────┬───────────────────────────────────────────────┘
          │
          ▼ (Final SQL + metadata)
┌─────────────────────────────────────────────────────────┐
│  ConversionResult                                        │
│  - sql: str                                              │
│  - metadata: dict                                        │
│  - validation_result: ValidationResult                   │
│  - stages: List[ConversionStage]                        │
│  - warnings: List[str]                                   │
└─────────┬───────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────┐
│  Return to caller   │
│  (Web UI or CLI)    │
└─────────────────────┘
```

---

## Summary: Where to Look for Issues

| Issue Type | Primary Location | Secondary Location | Document |
|-----------|-----------------|-------------------|----------|
| CREATE VIEW wrong format | converter.py 312-319 | - | BUG_TRACKER.md BUG-023 |
| CV reference wrong | renderer.py 942-970 | package_mapper.py | BUG_TRACKER.md BUG-025 |
| Column ambiguity in JOIN | renderer.py 645-654 | - | BUG_TRACKER.md BUG-024 |
| Function translation | function_translator.py | - | HANA_CONVERSION_RULES.md Rule #4 |
| Parameter cleanup | renderer.py 1156-1193 | - | GOLDEN_COMMIT.yaml |
| Empty WHERE clause | renderer.py (6 locations) | - | GOLDEN_COMMIT.yaml |
| Node rendering logic | renderer.py 413-890 | - | HANA_CONVERSION_RULES.md |
| Expression evaluation | renderer.py 974-1022 | - | - |
| Package lookup | package_mapper.py | package_mappings.db | llm_handover.md |

---

**Last Updated**: 2025-11-22 (Session 8B - Calculated Column Forward References)
**Author**: Claude Code Assistant
**Purpose**: Complete conversion pipeline reference for debugging and understanding
