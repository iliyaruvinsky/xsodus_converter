# Success Procedure - After HANA Validation

**When an XML successfully validates in HANA, follow these steps:**

---

## STEP 1: Update Productive Scripts

### 1.1 Check functions.yaml
- [ ] Verify all function mappings used in this XML are present
- [ ] Check if any NEW functions were discovered
- [ ] Add missing mappings if needed
- [ ] Document in description field

**Location**: `src/xml_to_sql/catalog/data/functions.yaml`

**Command**:
```powershell
# Find all function calls in SQL
findstr /R "\b[A-Z_]+\(" LATEST_SQL_FROM_DB.txt | findstr /V "SELECT FROM WHERE"
# Verify each is in functions.yaml or is standard HANA function
```

### 1.2 Check patterns.yaml
- [ ] Verify all pattern rewrites applied correctly
- [ ] Check if any NEW patterns were needed
- [ ] Add missing patterns if needed

**Location**: `src/xml_to_sql/catalog/data/patterns.yaml`

### 1.3 Verify config.yaml
- [ ] Confirm schema_overrides are correct
- [ ] Verify view_schema setting
- [ ] Check all settings used in conversion

**Location**: `config.yaml`

---

## STEP 2: Update Documentation

### 2.1 Update GOLDEN_COMMIT.yaml

Add XML to validated list:
```yaml
validated_xmls:
  files:
    - name: "CV_EQUIPMENT_STATUSES.xml"
      source: "Source (XML Files)/HANA 1.XX XML Views/BW_ON_HANA/"
      execution_time: "26ms"
      notes: "Working - DATE, DAYSBETWEEN mappings added"
      validation_date: "2025-12-08"
```

**Location**: `GOLDEN_COMMIT.yaml`

### 2.2 Update BUG_TRACKER.md or SOLVED_BUGS.md

**If bug fixes were applied:**

- [ ] Move bug from BUG_TRACKER.md to SOLVED_BUGS.md
- [ ] Document solution details
- [ ] Reference code changes
- [ ] Update statistics

**If new bug discovered and fixed:**

- [ ] Create BUG-XXX entry
- [ ] Document in SOLVED_BUGS.md
- [ ] Update bug statistics

**Locations**:
- `docs/bugs/BUG_TRACKER.md`
- `docs/bugs/SOLVED_BUGS.md`

### 2.3 Update HANA_CONVERSION_RULES.md (if applicable)

**If new rule or principle discovered:**

- [ ] Add new rule with priority
- [ ] Document transformation pattern
- [ ] Reference implementation location
- [ ] Add validation status

**Location**: `docs/rules/HANA_CONVERSION_RULES.md`

### 2.4 Copy SQL to VALIDATED Folder

- [ ] Copy LATEST_SQL_FROM_DB.txt to `Target (SQL Scripts)/VALIDATED/{XML_NAME}.sql`
- [ ] Update VALIDATED/README.md with execution time
- [ ] Verify file is readable

**Command**:
```powershell
copy LATEST_SQL_FROM_DB.txt "Target (SQL Scripts)\VALIDATED\CV_EQUIPMENT_STATUSES.sql"
```

### 2.5 Update llm_handover.md

- [ ] Add to session update
- [ ] Document what was fixed
- [ ] Update statistics (XMLs validated count)
- [ ] Note any architectural decisions

**Location**: `docs/llm_handover.md`

---

## STEP 3: Commit Changes

**Before testing next XML, commit the fixes:**

```powershell
git add -A
git commit -m "BUGFIX: CV_EQUIPMENT_STATUSES validation - Add DATE, DAYSBETWEEN, fix view_schema

## What Was Fixed
- functions.yaml: Added DATE → TO_DATE mapping
- functions.yaml: Added DAYSBETWEEN → DAYS_BETWEEN mapping
- functions.yaml: Changed NOW to template handler (removes parentheses)
- models.py: Changed view_schema default to SAPABAP1
- converter.py: Changed view_schema default to SAPABAP1

## Validation
- CV_EQUIPMENT_STATUSES: 26ms in HANA (2025-12-08)
- All function calls correct (TO_DATE, DAYS_BETWEEN, CURRENT_TIMESTAMP)
- View created in SAPABAP1 schema

## Files Modified
- src/xml_to_sql/catalog/data/functions.yaml
- src/xml_to_sql/web/api/models.py
- src/xml_to_sql/web/services/converter.py

Co-Authored-By: Claude <noreply@anthropic.com>"
```

**Tag the commit:**
```powershell
git tag -a v3.0.1-working -m "Working baseline with complete function catalog"
```

---

## STEP 4: Move to Next XML

### 4.1 Checklist Before Next Test
- [x] Current XML validated and documented
- [x] Changes committed
- [x] Baseline tagged
- [ ] Server restarted (if needed)
- [ ] Ready for next XML

### 4.2 Select Next XML

**Priority order** (from GOLDEN_COMMIT.yaml):
1. CV_TOP_PTHLGY (most complex, highest priority)
2. CV_INVENTORY_ORDERS
3. CV_PURCHASE_ORDERS
4. CV_CNCLD_EVNTS
5. CV_MCM_CNTRL_Q51
6. Others...

### 4.3 Test Next XML

**Repeat entire procedure:**
1. Upload XML via web UI
2. Convert
3. Check LATEST_SQL_FROM_DB.txt
4. Test in HANA
5. If error → SQL_ERROR_INVESTIGATION_PROCEDURE.md
6. If success → THIS PROCEDURE

---

## CHECKLIST SUMMARY

**After each successful HANA validation:**

- [ ] **Step 1.1**: functions.yaml updated
- [ ] **Step 1.2**: patterns.yaml updated (if needed)
- [ ] **Step 1.3**: config.yaml verified
- [ ] **Step 2.1**: GOLDEN_COMMIT.yaml updated
- [ ] **Step 2.2**: Bug docs updated
- [ ] **Step 2.3**: Rules updated (if new rule)
- [ ] **Step 2.4**: SQL copied to VALIDATED/
- [ ] **Step 2.5**: llm_handover.md updated
- [ ] **Step 3**: Changes committed and tagged
- [ ] **Step 4**: Ready for next XML

---

**This procedure ensures:**
- Every success is documented
- Catalogs stay complete
- VALIDATED folder stays current
- Git history is clean
- Ready for migration to new repo

**Current Status**: CV_EQUIPMENT_STATUSES ✅ validated, now following this procedure before testing CV_TOP_PTHLGY.

