# 3. Testing Procedure

**Version**: 1.0
**Created**: 2025-12-10
**Purpose**: Systematic testing process for XML to SQL conversions

---

## When to Use This Procedure

- After ANY code change
- After ANY catalog change (functions.yaml, patterns.yaml)
- Before claiming a fix works
- Before committing changes

---

## Testing Types

| Type | When | Scope |
|------|------|-------|
| **Single XML Test** | Testing specific XML | One XML file |
| **Regression Test** | After code changes | All 13 validated XMLs |
| **New XML Test** | Validating untested XML | One new XML |

---

## PROCEDURE: Single XML Test

### STEP 1: Prepare Environment

**If code/catalog changed:**
```powershell
# Run from project root
utilities\restart_server.bat
```

**If only testing (no changes):**
- Ensure server is running at http://localhost:8000

### STEP 2: Convert XML

1. Open http://localhost:8000
2. Upload XML file
3. Click Convert
4. Wait for completion

### STEP 3: Check Auto-Save

Verify SQL was auto-saved:
```
C:\Users\iliya\OneDrive\Desktop\X2S\xsodus_converter\LATEST_SQL_FROM_DB.txt
```

### STEP 4: Execute in HANA

1. Open HANA Studio or HANA CLI
2. Copy SQL from LATEST_SQL_FROM_DB.txt
3. Execute
4. Record result:
   - **SUCCESS**: Note execution time (e.g., "26ms")
   - **ERROR**: Note full error message with line/column

### STEP 5: Determine Next Action

| Result | Next Procedure |
|--------|----------------|
| SUCCESS | → `SUCCESS_PROCEDURE.md` |
| ERROR (new XML) | → `ERROR_PROCEDURE_NO_BASELINE.md` |
| ERROR (has baseline) | → `SQL_ERROR_INVESTIGATION_PROCEDURE.md` |

---

## PROCEDURE: Regression Test (All 13 XMLs)

**MANDATORY before committing any code change to renderer.py or function_translator.py**

### STEP 1: Get Validated XML List

From `GOLDEN_COMMIT.yaml`:

| # | XML File | Expected Time | Location |
|---|----------|---------------|----------|
| 1 | CV_CNCLD_EVNTS.xml | 74ms | HANA 1.XX XML Views/BW_ON_HANA/ |
| 2 | CV_INVENTORY_ORDERS.xml | 42ms | HANA 1.XX XML Views/BW_ON_HANA/ |
| 3 | CV_PURCHASE_ORDERS.xml | 46ms | HANA 1.XX XML Views/BW_ON_HANA/ |
| 4 | CV_EQUIPMENT_STATUSES.xml | 26ms | HANA 1.XX XML Views/BW_ON_HANA/ |
| 5 | CV_TOP_PTHLGY.xml | 195ms | HANA 1.XX XML Views/BW_ON_HANA/ |
| 6 | CV_MCM_CNTRL_Q51.xml | 82ms | HANA 1.XX XML Views/ECC_ON_HANA/ |
| 7 | CV_MCM_CNTRL_REJECTED.xml | 53ms | HANA 1.XX XML Views/ECC_ON_HANA/ |
| 8 | CV_UPRT_PTLG.xml | 27ms | HANA 1.XX XML Views/BW_ON_HANA/ |
| 9 | CV_ELIG_TRANS_01.xml | 28ms | HANA 1.XX XML Views/BW_ON_HANA/ |
| 10 | CV_COMMACT_UNION.xml | - | HANA 1.XX XML Views/ECC_ON_HANA/ |
| 11 | CV_INVENTORY_STO.xml | 59ms | HANA 1.XX XML Views/BW_ON_HANA/ |
| 12 | CV_PURCHASING_YASMIN.xml | 70ms | HANA 1.XX XML Views/BW_ON_HANA/ |
| 13 | (additional) | - | - |

### STEP 2: Run Automated Regression (if available)

```powershell
utilities\validate_all_xmls.bat
```

### STEP 3: Manual Regression (if needed)

For each XML in the list:
1. Convert via web UI
2. Compare generated SQL with `VALIDATED/hana/{XML_NAME}.sql`
3. Execute in HANA
4. Verify same result as baseline

### STEP 4: Record Results

| XML | Generated | Matches Baseline | HANA Result | Time |
|-----|-----------|------------------|-------------|------|
| CV_EQUIPMENT_STATUSES | ✅ | ✅ | ✅ | 26ms |
| CV_TOP_PTHLGY | ✅ | ✅ | ✅ | 195ms |
| ... | | | | |

### STEP 5: Handle Failures

**If ANY XML fails that previously worked:**
1. STOP immediately
2. DO NOT commit
3. REVERT changes
4. Investigate why regression occurred
5. Fix without breaking working XMLs

**Rule (CLAUDE.md Rule 14):**
> Working code > Fixed new bug - preserving working functionality is HIGHEST priority

---

## SQL Validation Checks

**From MANDATORY_PROCEDURES.md - run these checks on generated SQL:**

### Check 1: String Column Quoting (BUG-026)
```sql
-- WRONG: WHERE COLUMN = ABC
-- CORRECT: WHERE COLUMN = 'ABC'
```

### Check 2: No Empty WHERE Clauses (BUG-022)
```sql
-- WRONG: WHERE AND COLUMN = 'X'
-- WRONG: WHERE OR COLUMN = 'X'
-- WRONG: WHERE ()
```

### Check 3: No Package Paths in CREATE VIEW (BUG-023)
```sql
-- WRONG: CREATE VIEW "schema"."package/subpackage/ViewName"
-- CORRECT: CREATE VIEW "schema"."ViewName"
```

### Check 4: No Empty String IN Numeric (BUG-021)
```sql
-- WRONG: WHERE ('' IN (0) OR column IN (...))
```

---

## Post-Generation Validation Checks

### Check 1: Parameter Cleanup
- No `$$param$$` remaining in SQL
- No malformed `('')` patterns

### Check 2: CTE Ordering
- Each CTE defined before it's referenced
- No forward references

### Check 3: Column Qualification in JOINs
- All columns in JOINs qualified with table alias

### Check 4: Empty WHERE Patterns
- No `WHERE AND`, `WHERE OR`, `WHERE ()`

---

## Automation Scripts

### restart_server.bat
**Location**: `utilities/restart_server.bat`
**Purpose**: Kill processes, clear cache, reinstall packages, start server

### validate_all_xmls.bat
**Location**: `utilities/validate_all_xmls.bat`
**Purpose**: Run all 13 validated XMLs and compare with baseline

---

## Quick Reference

### Before Code Change
1. Note current working state
2. Understand what you're changing

### After Code Change
1. Run `restart_server.bat`
2. Test the target XML
3. Run regression test on ALL validated XMLs
4. Only commit if ALL tests pass

### Test Result Actions
| Result | Action |
|--------|--------|
| All pass | Commit changes |
| Target fails | Debug and fix |
| Regression fails | REVERT immediately |

---

## Related Documents

- `GOLDEN_COMMIT.yaml` - Baseline configuration
- `VALIDATED/hana/*.sql` - Golden SQL files for comparison
- `MANDATORY_PROCEDURES.md` - SQL validation checks
- `CLAUDE.md` Rule 14 - Regression testing mandate

---

**Last Updated**: 2025-12-10
