# VALIDATED SQL Scripts - GOLDEN COPIES

This folder contains **HANA-VALIDATED** SQL scripts that have been successfully executed in HANA Studio.

## ⚠️ CRITICAL: This is Your Source of Truth

- These are **GOLDEN COPIES** - Byte-level regression reference
- **DO NOT modify** these files unless re-validated in HANA Studio
- **DO NOT trust documentation** over these actual working SQL files
- See `GOLDEN_COMMIT.yaml` in project root for commit tracking

## Purpose

1. **Golden copies** for byte-level comparison (regression testing)
2. **Backup** before making risky changes
3. **Source of truth** when documentation conflicts with reality
4. **Proof of working state** for rollback scenarios

## Protection Workflow

### Before ANY Code Change to Critical Files:

1. **Read `GOLDEN_COMMIT.yaml`** to see last validated commit
2. **Regenerate SQL** from current code for all validated XMLs
3. **Compare byte-by-byte** with files in this folder
4. **If different**: Document WHY and get user HANA validation
5. **If same**: Proceed with confidence

### After Successful HANA Studio Execution:

1. Copy SQL to this folder
2. Update execution time in table below
3. Update `GOLDEN_COMMIT.yaml` with new commit hash
4. Commit both files together

### Comparison Command:

```bash
# Regenerate SQL and compare
python regression_test.py --compare-with-golden

# Show differences if any
diff "UI_GENERATED_SQL.txt" "Target (SQL Scripts)/VALIDATED/CV_FILENAME.sql"
```

## Validated Files

### BW_ON_HANA Instance ✅ 4/4 Working

| File | Source Folder | HANA Package | Execution | Date Validated |
|------|--------------|--------------|-----------|----------------|
| CV_TOP_PTHLGY.sql | BW_ON_HANA | Macabi_BI.EYAL.EYAL_CDS | ✅ Success | 2025-11-17 |
| CV_EQUIPMENT_STATUSES.sql | BW_ON_HANA | Macabi_BI.EYAL.EYAL_CDS | ✅ Success | 2025-11-17 |
| CV_INVENTORY_ORDERS.sql | BW_ON_HANA | Macabi_BI.EYAL.EYAL_CDS | ✅ Success | 2025-11-17 |
| CV_PURCHASE_ORDERS.sql | BW_ON_HANA | Macabi_BI.EYAL.EYAL_CDS | ✅ Success | 2025-11-17 |

**Result**: All BW_ON_HANA views work perfectly!

### ECC_ON_HANA Instance ⚠️ 1/2 Working

| File | Source Folder | HANA Package | Execution | Date Validated |
|------|--------------|--------------|-----------|----------------|
| CV_CNCLD_EVNTS.sql | ECC_ON_HANA | EYAL.EYAL_CTL | ✅ Success (74ms) | 2025-11-17 |

## Known Issues

| File | Source Folder | Issue | Root Cause |
|------|--------------|-------|------------|
| CV_CT02_CT03.sql | ECC_ON_HANA | Syntax error in REGEXP_LIKE filters | Calculated columns in WHERE need subquery alias 'calc' |

**Details**: See `docs/bugs/BUG_TRACKER.md` for full analysis. Validated XMLs tracked in `GOLDEN_COMMIT.yaml`.

---

## Session 7 Lessons Learned (2025-11-18)

**Incident**: False documentation claimed CREATE OR REPLACE VIEW works in HANA
**Impact**: Code was changed, broke ALL SQL generation
**Resolution**: Reverted to commit 4eff5fb, reapplied BUG-019 & BUG-020 fixes
**Lesson**: **THESE SQL FILES ARE TRUTH, DOCUMENTATION MAY LIE**

**Protection Added**:
- `GOLDEN_COMMIT.yaml` tracks last validated commit
- Critical code sections have warning comments
- This README updated with strict protection workflow

**References**:
- `GOLDEN_COMMIT.yaml` - Commit tracking, validation status, and incident log (includes Session 7 details)

---

**Last Updated**: 2025-11-18 (Updated with protection workflow)
