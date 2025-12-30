# SQL-to-ABAP Bug Tracker

## Overview

This document tracks active bugs in the SQL-to-ABAP pipeline. Bugs are numbered sequentially with prefix `ABAP-`.

---

## Active Bugs

| ID | Summary | Status | Priority | Assigned |
|----|---------|--------|----------|----------|
| ABAP-001 | Calculated columns incorrectly typed | Fixed | Critical | Claude |
| ABAP-002 | FAE uses wrong source table for join key | Fixed | Critical | Claude |

---

### ABAP-001: Calculated columns use TYPE table-field instead of TYPE string

**Status**: Fixed

**Priority**: Critical

**Reported**: 2025-12-10

**Component**: CTE Parser + ABAP Generator

#### Description
When SQL contains calculated columns (function calls, arithmetic expressions, or literals), the ABAP generator incorrectly tries to use `TYPE table-field` syntax which fails because the column doesn't exist in the dictionary table.

#### Example
SQL: `TO_VARCHAR(ADD_DAYS(...)) AS FROMDATE`
Generated (wrong): `fromdate TYPE rspclogchain-fromdate` (field doesn't exist!)
Should be: `fromdate TYPE string` (calculated column)

#### Root Cause
`_parse_columns()` regex patterns only matched simple column references. Function calls like `TO_VARCHAR(...)` would match only the function name (`TO_VARCHAR`) and miss the `AS FROMDATE` alias.

#### Solution
1. Added expression detection in `_parse_columns()` (pattern 2b)
2. Detect expressions: `(`, `+`, `*`, `/`, or numeric literals
3. Extract alias using `\s+AS\s+(\w+)$` pattern
4. Mark calculated columns with `source=""`
5. Updated `_collect_table_info()` to separate real vs calculated columns
6. Updated `_gen_type_definitions()` to use `TYPE string` for calculated columns
7. Updated SELECT generation to exclude calculated columns from SELECT

#### Files Modified
- `sql_to_abap.py:401-424` - Pattern 2b for expressions
- `sql_to_abap.py:780-802` - `_collect_table_info()` returns {'real': [], 'calculated': []}
- `sql_to_abap.py:805-826` - `_gen_type_definitions()` uses TYPE string for calculated
- `sql_to_abap.py:958-960` - `_find_column_source_in_cte()` returns None for calculated columns
- `sql_to_abap.py:975-977` - `_find_column_source()` returns None for calculated columns
- `sql_to_abap.py:1218-1219` - SELECT excludes calculated columns

#### Validation
- [ ] SE38 syntax check passed
- [ ] Tested with ASSESSMENT_REPORT.xml

---

### ABAP-002: FAE uses wrong source table for join key

**Status**: Fixed

**Priority**: Critical

**Reported**: 2025-12-11

**Component**: FAE Dependency Mapper

#### Description
When building FOR ALL ENTRIES dependency map for JOIN CTEs where the left side is another JOIN (not a base table), the code picks ANY resolved table as FAE source without checking if that table has the required join column.

#### Example
SQL: `join_2 ... INNER JOIN projection_2 ON join_1.LOG_ID = projection_2.LOG_ID`
Generated (wrong): `FROM rspcprocesslog FOR ALL ENTRIES IN lt_rsbkdtpt WHERE log_id = lt_rsbkdtpt-log_id`
Problem: RSBKDTPT doesn't have LOG_ID field!
Should use: `lt_rspclogchain` which HAS LOG_ID

#### Root Cause
In `_build_fae_dependency_map()`, when left_table is None (because left side is a JOIN CTE), the code at lines 1050-1054 just picked the first resolved table:
```python
for resolved in resolved_tables:
    fae_source = resolved
    break
```

#### Solution
1. Added `_find_table_with_column()` helper function
2. When left side is JOIN CTE, trace the join column to find which resolved table has it
3. Only use a table as FAE source if it actually has the required join column

#### Files Modified
- `sql_to_abap.py:983-1007` - Added `_find_table_with_column()` helper
- `sql_to_abap.py:1051-1061` - Call helper instead of picking any table

#### Validation
- [ ] SE38 syntax check passed
- [ ] Tested with ASSESSMENT_REPORT.xml

---

### ABAP-003: CTE Case Sensitivity Causes Missing Internal Table Declarations

**Status**: Fixed

**Priority**: Critical

**Reported**: 2025-12-15

**Component**: CTE Parser (sql_to_abap.py)

#### Description
Generated ABAP code references internal tables (`lt_aggregation_1`) that are never declared, while similar tables (`lt_aggregation_2`) exist. This causes SAP syntax errors:
```
The field 'LT_AGGREGATION_1' is unknown, but there is a field with the similar name 'LT_AGGREGATION_2'
```

#### Root Cause
Case mismatch between CTE dictionary keys and input references:
1. CTE names stored with **original case** from SQL: `result.ctes['Aggregation_1']`
2. Input references stored **lowercased**: `union_inputs = ['aggregation_1']`
3. Dictionary lookup `'Aggregation_1' in {'aggregation_1'}` = **FALSE**
4. Result: CTE not recognized as needing intermediate table, so DATA not generated

#### Solution
1. Lowercase CTE keys in `parse_sql()` for consistent lookup
2. Change `result.ctes[cte_name]` to `result.ctes[cte_name.lower()]`

#### Files Modified
- `sql_to_abap.py:184` - Lowercase CTE keys for consistent lookup

#### Cross-Reference
Also tracked as BUG-039 in xml-to-sql pipeline docs

#### Validation
- [ ] SE38 syntax check passed
- [ ] Tested with Transformations.XML

---

## Bug Template

### ABAP-XXX: [Title]

**Status**: Open | In Progress | Fixed | Won't Fix

**Priority**: Critical | High | Medium | Low

**Reported**: YYYY-MM-DD

**Component**: CTE Parser | ABAP Generator | FOR ALL ENTRIES | Output

#### Description
[What is the bug?]

#### Steps to Reproduce
1. Step 1
2. Step 2
3. Step 3

#### Expected Behavior
[What should happen]

#### Actual Behavior
[What actually happens]

#### Root Cause Analysis
[Why does this happen?]

#### Proposed Solution
[How to fix it]

#### Files to Modify
- `file1.py` - description
- `file2.py` - description

#### Test Case
```sql
-- SQL that triggers the bug
```

#### Validation
- [ ] Fix implemented
- [ ] Unit test added
- [ ] Tested with real XML
- [ ] SE38 syntax check passed
- [ ] Added to SOLVED_BUGS.md

---

## Statistics

- Total Bugs: 0
- Open: 0
- In Progress: 0
- Fixed: 0
- Won't Fix: 0

---

**Last Updated**: 2025-12-10
