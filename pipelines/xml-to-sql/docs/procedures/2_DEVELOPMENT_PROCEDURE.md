# 2. Development Procedure

**Version**: 1.0
**Created**: 2025-12-10
**Purpose**: Guidelines for writing and modifying code in the XML-to-SQL pipeline

---

## When to Use This Procedure

- When writing new code
- When modifying existing code
- When implementing bug fixes that require code changes
- Before ANY modification to core SQL generation files

---

## Core Development Rules

### From CLAUDE.md

| Rule | Summary | Enforcement |
|------|---------|-------------|
| **Rule 13** | MINIMAL CODE CHANGES - Surgical precision | MANDATORY |
| **Rule 14** | REGRESSION TESTING MANDATE | MANDATORY |
| **Rule 15** | CHANGE DOCUMENTATION PROTOCOL | MANDATORY |
| **Rule 16** | CORE SQL GENERATION PROTECTION | MANDATORY |
| **Rule 17** | IF IT WORKS, DON'T TOUCH IT | MANDATORY |

---

## PROCEDURE: Code Development

### STEP 1: Planning

**Before touching ANY code:**

1. **Identify exact scope:**
   - What specific problem needs solving?
   - Which files need modification?
   - Which lines need to change?

2. **Check existing solutions:**
   - Read `BUG_TRACKER.md` for known issues
   - Read `SOLVED_BUGS.md` for past solutions
   - Check if a catalog fix can work instead

3. **Impact assessment:**
   - Reference `CONVERSION_FLOW_MAP.md` for architecture
   - What could this change break?
   - Which XMLs might be affected?

4. **Document plan:**
   ```markdown
   CHANGE PLAN:
   - Problem: [description]
   - Files affected: [list]
   - Lines to change: [list]
   - Risk level: [LOW/MEDIUM/HIGH]
   - Regression potential: [assessment]
   ```

### STEP 2: Pre-Implementation Checklist

**Before making ANY code change:**

- [ ] Read the target file(s) completely
- [ ] Understand existing logic
- [ ] Identify insertion point for change
- [ ] Backup current state: `git stash` or `git commit -m "WIP"`
- [ ] Verify server is running for testing

### STEP 3: Surgical Implementation

**Golden Rules:**

```
1. Change ONLY what's needed - nothing more
2. One change at a time - test after each
3. Add comments explaining WHY (not what)
4. Use BUG-XXX references in comments
5. Track every line you modify
```

**Comment Format:**
```python
# BUG-XXX: Brief explanation of why this change is needed
# Before: what the code did
# After: what the code does now
```

### STEP 4: Immediate Verification

**After EACH modification:**

1. Save the file
2. Read the file to verify change was applied
3. Run `utilities\restart_server.bat`
4. Test with target XML
5. Check HANA result

**If test fails:**
- STOP
- Analyze why
- Fix or REVERT
- Do NOT proceed to next change

### STEP 5: Regression Testing

**MANDATORY before claiming fix complete:**

```powershell
utilities\validate_all_xmls.bat
```

Test against all 13 validated XMLs from `GOLDEN_COMMIT.yaml`:

| # | XML | Expected Result |
|---|-----|-----------------|
| 1 | CV_CNCLD_EVNTS.xml | PASS |
| 2 | CV_INVENTORY_ORDERS.xml | PASS |
| 3 | CV_PURCHASE_ORDERS.xml | PASS |
| 4 | CV_EQUIPMENT_STATUSES.xml | PASS |
| 5 | CV_TOP_PTHLGY.xml | PASS |
| 6 | CV_MCM_CNTRL_Q51.xml | PASS |
| 7 | CV_MCM_CNTRL_REJECTED.xml | PASS |
| 8 | CV_UPRT_PTLG.xml | PASS |
| 9 | CV_ELIG_TRANS_01.xml | PASS |
| 10 | CV_COMMACT_UNION.xml | PASS |
| 11 | CV_INVENTORY_STO.xml | PASS |
| 12 | CV_PURCHASING_YASMIN.xml | PASS |

**If ANY regression:**
```powershell
git checkout -- <modified_file>
```
- STOP immediately
- Analyze what broke
- Find alternative approach

### STEP 6: Change Documentation

**Before reporting completion, document:**

```markdown
CHANGES MADE:
1. File: renderer.py
   - Lines: 645-654
   - Change: Added column qualification in JOIN calculated columns
   - Reason: BUG-027 - prevent column ambiguity error

2. File: function_translator.py
   - Lines: 312-318
   - Change: Added DATE function mapping
   - Reason: BUG-XXX - HANA requires TO_DATE
```

---

## Key Files and Their Sensitivity

### EXTREME CAUTION (Core SQL Generation)

| File | Purpose | Risk |
|------|---------|------|
| `src/xml_to_sql/sql/renderer.py` | Main SQL generation | EXTREME |
| `src/xml_to_sql/sql/function_translator.py` | Formula translation | EXTREME |

**Rules for these files:**
- Treat like brain surgery
- Test after EVERY single line change
- Never make multiple changes before testing
- One mistake breaks EVERYTHING

### MEDIUM CAUTION (Catalog/Config)

| File | Purpose | Risk |
|------|---------|------|
| `catalog/hana/data/functions.yaml` | Function mappings | MEDIUM |
| `catalog/hana/data/patterns.yaml` | Pattern rewrites | MEDIUM |
| `config.yaml` | Runtime configuration | MEDIUM |

**Rules for these files:**
- Changes are safer but still require testing
- Reinstall after catalog changes: `pip install -e .`
- Test affected XMLs

### LOW CAUTION (Documentation/Utilities)

| File | Purpose | Risk |
|------|---------|------|
| `docs/*.md` | Documentation | LOW |
| `utilities/*.bat` | Utility scripts | LOW |

---

## Pipeline Isolation Rules

From `PIPELINE_ISOLATION_RULES.md`:

### Import Rules
```python
# CORRECT - Use local imports
from xml_to_sql.sql.renderer import HanaSqlRenderer

# WRONG - Never import from core or other pipelines
from x2s_core.something import ...  # NO!
from sql_to_abap.something import ...  # NO!
```

### Context Isolation
- Each pipeline is self-contained
- Never reference files outside `pipelines/xml-to-sql/`
- Use configuration, not hard-coded paths

---

## Development Anti-Patterns

| Anti-Pattern | Why Bad | Correct Approach |
|--------------|---------|------------------|
| "While I'm here" changes | Introduces new bugs | Fix ONLY target issue |
| Large refactoring | Hard to test/debug | Small incremental changes |
| No verification after edit | Don't know if it worked | Read file after every edit |
| Skipping regression test | Breaks validated XMLs | ALWAYS test all 13 XMLs |
| Undocumented changes | Can't debug later | Document every line changed |
| Guessing at solutions | Wastes time | Complete debugging first |

---

## Development Workflow Summary

```
PLAN
  │
  ▼
BACKUP STATE (git stash or commit)
  │
  ▼
MAKE SINGLE CHANGE
  │
  ▼
VERIFY CHANGE (Read file)
  │
  ▼
TEST CHANGE (Target XML)
  │
  ├── FAIL → REVERT → Analyze → Try different approach
  │
  ▼ PASS
REGRESSION TEST (All 13 XMLs)
  │
  ├── FAIL → REVERT → Analyze → Try different approach
  │
  ▼ PASS
DOCUMENT CHANGES
  │
  ▼
COMMIT
```

---

## Pre-Commit Checklist

- [ ] All changes are documented with line numbers
- [ ] All changes have BUG-XXX comments where applicable
- [ ] Target XML passes HANA validation
- [ ] All 13 validated XMLs still pass (regression test)
- [ ] Change summary prepared for commit message
- [ ] `docs/llm_handover.md` updated if needed
- [ ] Bug tracker updated if applicable

---

## Related Documents

- `.claude/CLAUDE.md` - Mandatory behavior rules (13-17)
- `.claude/MANDATORY_PROCEDURES.md` - Code change procedure details
- `.claude/PIPELINE_ISOLATION_RULES.md` - Import and isolation rules
- `docs/CONVERSION_FLOW_MAP.md` - Pipeline architecture
- `GOLDEN_COMMIT.yaml` - Regression baseline

---

**Last Updated**: 2025-12-10
