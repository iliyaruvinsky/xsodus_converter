# SQL Error Investigation Procedure
**Version**: 1.0  
**Created**: 2025-12-08  
**Purpose**: Systematic procedure for investigating HANA SQL errors

---

## 🚨 MANDATORY INVESTIGATION STEPS

### STEP 1: Capture the Generated SQL

**Command:**
```powershell
python -c "lines = open('LATEST_SQL_FROM_DB.txt', encoding='utf-8').readlines(); print('Line 0:', lines[0][:100]); print('Line 1:', lines[1][:100]); print('Total lines:', len(lines))"
```

**Purpose**: Verify SQL was auto-saved and check first lines (CREATE VIEW statement)

**Expected Output**:
- Line 0: `-- Last generated: [timestamp]` OR `DROP VIEW...`
- Line 1: Scenario comment OR `CREATE VIEW...`
- Total lines: Should match VALIDATED version

**Record**:
- [ ] Auto-save working? Yes/No
- [ ] CREATE VIEW schema: _________
- [ ] CREATE VIEW view name quoted? Yes/No
- [ ] Total lines: _________

---

### STEP 2: Identify Error Location

**Command:**
```powershell
python -c "lines = open('LATEST_SQL_FROM_DB.txt', encoding='utf-8').readlines(); line_num = [ERROR_LINE_NUM]; print(f'Line {line_num}: {lines[line_num-1]}')"
```
*(Replace [ERROR_LINE_NUM] with the line number from HANA error)*

**Purpose**: Read exact line where HANA error occurred

**Record**:
- [ ] Error line number: _________
- [ ] Error message: _________
- [ ] SQL fragment at error: _________

---

### STEP 3: Compare with VALIDATED Working SQL

**Command:**
```powershell
fc.exe "LATEST_SQL_FROM_DB.txt" "Target (SQL Scripts)\VALIDATED\[XML_NAME].sql"
```
*(Replace [XML_NAME] with the XML being tested)*

**Purpose**: Find exact differences between broken and working SQL

**Record Differences**:
- [ ] CREATE VIEW schema different? _________
- [ ] View name quoting different? _________
- [ ] Table schema different? (ABAP vs SAPABAP1)
- [ ] Functions different? (date vs TO_DATE, etc.)
- [ ] WHERE clauses different?
- [ ] Other: _________

---

### STEP 4: Check Conversion Catalogs Exist

**Commands:**
```powershell
dir src\xml_to_sql\catalog\data\patterns.yaml
dir src\xml_to_sql\catalog\data\functions.yaml
```

**Purpose**: Verify pattern matching and function catalogs are present

**Record**:
- [ ] patterns.yaml exists? Yes/No
- [ ] functions.yaml exists? Yes/No
- [ ] If NO: This commit predates pattern matching system

---

### STEP 5: Verify Configuration

**Command:**
```powershell
type config.yaml
```

**Purpose**: Check if config.yaml has correct settings

**Check For**:
- [ ] `database_mode: "hana"` (not sqlserver/snowflake)
- [ ] `hana_version: "2.0"`
- [ ] `schema_overrides:` section exists
- [ ] `ABAP: "SAPABAP1"` mapping exists

**Record Issues**: _________

---

### STEP 6: Map Errors to Rules

**For each HANA error, identify which RULE was violated:**

| Error Message | Line | Rule Violated | Rule File Location |
|---------------|------|---------------|-------------------|
| [321] invalid view name | 1 | PRINCIPLE #5 (BUG-029) | HANA_CONVERSION_RULES.md line 358 |
| [328] invalid function DATE | XX | Rule 14 (Legacy casts) | HANA_CONVERSION_RULES.md line 910 |
| [362] invalid schema ABAP | XX | Rule 17 (Schema mapping) | HANA_CONVERSION_RULES.md line 1034 |
| [257] syntax error | XX | Check patterns.yaml | - |

**Record**:
- [ ] Error 1: _________ → Rule: _________
- [ ] Error 2: _________ → Rule: _________
- [ ] Error 3: _________ → Rule: _________

---

### STEP 7: Check if Rules Are Implemented

**For each violated rule, verify implementation exists:**

**Example for BUG-029 (View name quoting):**
```powershell
findstr /N "BUG-029" src\xml_to_sql\sql\renderer.py
```

**Example for DATE function:**
```powershell
findstr /C:"DATE" src\xml_to_sql\catalog\data\functions.yaml
```

**Record**:
- [ ] Rule implementation found in code? Yes/No
- [ ] Code location: _________
- [ ] If NO: Rule not implemented at this commit

---

### STEP 8: Root Cause Analysis

**Based on Steps 1-7, determine root cause:**

**Checklist**:
- [ ] Missing catalog entries (functions.yaml or patterns.yaml)?
- [ ] Wrong config.yaml settings?
- [ ] Code doesn't implement the rule?
- [ ] Code implements rule but doesn't apply it?
- [ ] Web UI not passing correct parameters?

**Root Cause**: _________

---

### STEP 9: Check Commit Date vs Rule Implementation Date

**Command:**
```powershell
git log --oneline --date=iso-strict --pretty=format:"%h | %ad | %s" -1
```

**Purpose**: If commit predates rule/fix, that's why it's broken

**Check**:
- [ ] Commit date: _________
- [ ] Rule documentation date: _________ (from HANA_CONVERSION_RULES.md)
- [ ] Is commit BEFORE rule was implemented? Yes/No

---

### STEP 10: Determine Fix Strategy

**Based on root cause:**

**OPTION A: This commit predates the fix**
→ Move to newer commit that has the fix

**OPTION B: This commit should have the fix but doesn't**
→ Check if catalogs need reinstalling: `pip install -e .`

**OPTION C: Config.yaml wrong**
→ Fix config.yaml

**OPTION D: Code broken**
→ Surgical fix needed (DANGEROUS - document carefully)

**Selected Strategy**: _________

---

## 📊 INVESTIGATION TEMPLATE

**Date**: _________  
**Commit**: _________  
**XML Tested**: _________  
**HANA Errors**: _________

### Step 1: SQL Capture
- Auto-save: ☐ Yes ☐ No
- CREATE VIEW schema: _________
- View name quoted: ☐ Yes ☐ No
- Total lines: _________

### Step 2: Error Location
- Error line: _________
- Error type: _________
- SQL fragment: _________

### Step 3: Comparison
- Differences from VALIDATED: _________

### Step 4: Catalogs
- patterns.yaml: ☐ Exists ☐ Missing
- functions.yaml: ☐ Exists ☐ Missing

### Step 5: Configuration
- database_mode: _________
- schema_overrides: _________
- Issues: _________

### Step 6: Rules Violated
1. _________
2. _________

### Step 7: Implementation Check
- Rule code found: ☐ Yes ☐ No
- Location: _________

### Step 8: Root Cause
_________

### Step 9: Commit Timeline
- Commit date: _________
- Rule implemented: _________
- Commit is too old: ☐ Yes ☐ No

### Step 10: Fix Strategy
_________

---

## 🎯 INVESTIGATION LOG

### Investigation #1: [Date]
*Record findings here after each investigation*

---

**Usage**: Follow steps 1-10 for EVERY HANA error. Update this document with findings.

