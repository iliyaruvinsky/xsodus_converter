# SQL-to-ABAP Solved Bugs Archive

## Overview

This document archives solved bugs from the SQL-to-ABAP pipeline. Reference this before implementing new fixes to avoid reinventing solutions.

---

## Solved Bugs Index

| ID | Summary | Solution Type | Date Fixed |
|----|---------|---------------|------------|
| - | No solved bugs yet | - | - |

---

## Solved Bug Template

### ABAP-XXX: [Title]

**Date Fixed**: YYYY-MM-DD

**Original Symptom**: [What was broken]

**Root Cause**: [Why it broke]

**Solution**: [How it was fixed]

**Files Modified**:
- `file.py:line` - change description

**Code Change**:
```python
# Before
old_code()

# After
new_code()
```

**Validation**:
- XML validated: [name]
- SE38 result: [pass/fail]

**Lessons Learned**:
[What to remember for future]

---

## Solution Patterns

### Pattern 1: FOR ALL ENTRIES Empty Table

**Problem**: FOR ALL ENTRIES on empty table returns all rows

**Solution**: Always check IS NOT INITIAL before FOR ALL ENTRIES

```abap
IF lt_keys IS NOT INITIAL.
  SELECT ... FOR ALL ENTRIES IN lt_keys WHERE ...
ENDIF.
```

### Pattern 2: Duplicate Key Extraction

**Problem**: FOR ALL ENTRIES with duplicate keys causes performance issues

**Solution**: Use SELECT DISTINCT for key extraction

```abap
SELECT DISTINCT key INTO TABLE lt_keys FROM lt_source.
```

---

**Last Updated**: 2025-12-10
