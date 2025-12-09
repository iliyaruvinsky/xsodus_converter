# Snowflake Conversion Rules

**Target Database**: Snowflake  
**Version**: 2.3.0  
**Last Updated**: 2025-11-13  

---

## Purpose

This document contains **ONLY** the transformation rules for converting HANA Calculation View XMLs to **Snowflake SQL**.

**Use this when**: `database_mode: snowflake` (default)

---

## Rule Execution Order

Rules applied in priority order:

1. **Priority 10**: Legacy function rewrites (LEFTSTR→SUBSTRING, RIGHTSTR→RIGHT)
2. **Priority 20**: No uppercase requirement (Snowflake is case-insensitive)
3. **Priority 30**: IN operator preserved (fully supported)
4. **Priority 40**: IF → IFF
5. **Priority 50**: String concatenation (+ → ||)

---

## Snowflake-Specific Transformation Rules

### Rule 1: IF() to IFF() (Priority 40)

**Rule ID**: `SNOWFLAKE_IF_TO_IFF`  
**Applies To**: All Snowflake versions  
**Category**: Conditional expressions

**Transformation**:
```
Source:  IF(condition, then_value, else_value)
Target:  IFF(condition, then_value, else_value)
```

**Example**:
```sql
-- HANA XML
if(RIGHT("CALMONTH", 2) = '01', '2015' + '1', '')

-- Snowflake SQL
IFF(RIGHT("CALMONTH", 2) = '01', SUBSTRING("ZZTREAT_DATE", 1, 4) || '1', '')
```

**Implementation**: `function_translator.py::_translate_if_statements()`

**Note**: Snowflake uses `IFF()` (with double F), not `IF()`.

---

### Rule 2: String Concatenation (Priority 50)

**Rule ID**: `SNOWFLAKE_STRING_CONCAT`  
**Applies To**: All Snowflake versions  
**Category**: Operators

**Transformation**:
```
Source:  string1 + string2
Target:  string1 || string2
```

**Example**:
```sql
-- HANA XML
leftstr("ZZTREAT_DATE",4)+'1'

-- Snowflake SQL
SUBSTRING("ZZTREAT_DATE", 1, 4) || '1'
```

**Implementation**: `function_translator.py::_translate_string_concatenation()`

---

### Rule 3: LEFTSTR Function (Priority 10)

**Rule ID**: `SNOWFLAKE_LEFTSTR`  
**Applies To**: All Snowflake versions  
**Category**: Legacy function conversion

**Transformation**:
```
Source:  leftstr(string, length)
Target:  SUBSTRING(string, 1, length)
```

**Implementation**: Catalog rewrite in `catalog/data/functions.yaml`

---

### Rule 4: RIGHTSTR Function (Priority 10)

**Rule ID**: `SNOWFLAKE_RIGHTSTR`  
**Applies To**: All Snowflake versions  
**Category**: Legacy function conversion

**Transformation**:
```
Source:  rightstr(string, length)
Target:  RIGHT(string, length)
```

**Implementation**: Catalog rewrite in `catalog/data/functions.yaml`

---

### Rule 5: IN Operator (Priority 30)

**Rule ID**: `SNOWFLAKE_IN_PRESERVE`  
**Applies To**: All Snowflake versions  
**Category**: Operators

**Transformation**:
```
Source:  (expression IN (val1, val2))
Target:  Keep as-is (fully supported)
```

**Note**: Snowflake fully supports `IN` operator in all contexts, including inside conditional expressions.

---

## Snowflake-Specific Features

### Data Types

**HANA** → **Snowflake**:
- `DECIMAL(p,s)` → `NUMBER(p,s)`
- `TIMESTAMP` → `TIMESTAMP_NTZ`
- `NVARCHAR(n)` → `VARCHAR(n)`

### View Syntax

**Snowflake**: `CREATE OR REPLACE VIEW` (supported)  
**HANA**: `CREATE VIEW` (no OR REPLACE in all versions)

---

## What Snowflake Does NOT Need

❌ **IF to CASE conversion** - Snowflake uses IFF(), not CASE  
❌ **IN to OR conversion** - IN fully supported  
❌ **Subquery wrapping** - Can reference calculated cols (with limitations)  
❌ **Parameter removal** - Parameters handled differently (not in scope yet)

---

## Files Reference

**Rules Catalog**: `src/xml_to_sql/catalog/data/conversion_rules.yaml`  
**Function Catalog**: `src/xml_to_sql/catalog/data/functions.yaml`  
**Implementation**: `src/xml_to_sql/sql/function_translator.py::_translate_for_snowflake()`

---

**Status**: Snowflake mode is simpler than HANA mode. Most transformations are function-level rewrites.

