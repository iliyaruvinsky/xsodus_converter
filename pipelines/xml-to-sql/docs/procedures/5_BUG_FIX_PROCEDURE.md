# 5. Bug Fix Implementation Procedure

**Version**: 1.0
**Created**: 2025-12-10
**Purpose**: Systematic procedure for implementing bug fixes safely

---

## When to Use This Procedure

- After debugging has identified the root cause
- When ready to implement a fix
- AFTER reading ERROR_PROCEDURE_NO_BASELINE.md or SQL_ERROR_INVESTIGATION_PROCEDURE.md

**PREREQUISITE**: Debugging procedure must be completed first (Steps 1-8 of ERROR_PROCEDURE_NO_BASELINE.md or Steps 1-9 of SQL_ERROR_INVESTIGATION_PROCEDURE.md)

---

## Fix Types (In Order of Safety)

| Priority | Type | Risk | Location | When to Use |
|----------|------|------|----------|-------------|
| 1 | **CATALOG FIX** | LOW | `catalog/hana/data/` | Function mapping, pattern rewrite |
| 2 | **CONFIG FIX** | LOW | `config.yaml` | Schema override, mode setting |
| 3 | **CODE FIX** | HIGH | `src/xml_to_sql/sql/` | Logic change, new feature |

**RULE (CLAUDE.md Rule 13)**: Always prefer catalog/config fixes over code fixes.

---

## PROCEDURE: Catalog Fix (SAFE)

### STEP 1: Identify Fix Location

| Error Type | Catalog File | Section |
|------------|--------------|---------|
| Unknown function | `functions.yaml` | Function mappings |
| Expression pattern | `patterns.yaml` | Pattern rewrites |
| Boolean check | `patterns.yaml` | Conditional patterns |

### STEP 2: Add Catalog Entry

**For functions.yaml:**
```yaml
- name: LEGACY_FUNCTION_NAME
  handler: rename
  target: "HANA_FUNCTION_NAME"
  description: >
    Description of mapping.
    Discovered in [XML_NAME] ([BUG-XXX]).
```

**For patterns.yaml (simple):**
```yaml
- name: pattern_name
  pattern: "regex_pattern_here"
  replacement: "replacement_here"
  description: "Description"
```

**For patterns.yaml (complex):**
```yaml
- name: pattern_name
  pattern: "regex_with_(capture_groups)"
  replacement: "replacement_with_$1_backrefs"
  flags: ["IGNORECASE"]
  description: "Description"
```

### STEP 3: Document Change

Add BUG-XXX reference to description field.

### STEP 4: Apply Change

```powershell
cd pipelines\xml-to-sql
pip install -e .
```

### STEP 5: Restart Server

```powershell
utilities\restart_server.bat
```

### STEP 6: Test

1. Convert target XML via web UI
2. Execute in HANA
3. If SUCCESS → Continue to Documentation Procedure
4. If ERROR → Analyze and adjust catalog entry

---

## PROCEDURE: Config Fix (SAFE)

### STEP 1: Identify Config Issue

Common issues:
- `database_mode` not set to `hana`
- Missing `schema_overrides`
- Wrong `hana_version`

### STEP 2: Edit config.yaml

```yaml
defaults:
  database_mode: "hana"
  hana_version: "2.0"

schema_overrides:
  ABAP: "SAPABAP1"
  # Add other schema mappings as needed
```

### STEP 3: Restart Server

```powershell
utilities\restart_server.bat
```

### STEP 4: Test

1. Convert target XML
2. Verify in HANA
3. If SUCCESS → Continue to Documentation Procedure
4. If ERROR → Investigate further

---

## PROCEDURE: Code Fix (DANGEROUS)

### MANDATORY RULES

From CLAUDE.md:
- **Rule 13**: MINIMAL CODE CHANGES - Surgical precision
- **Rule 14**: REGRESSION TESTING MANDATE
- **Rule 16**: CORE SQL GENERATION PROTECTION
- **Rule 17**: IF IT WORKS, DON'T TOUCH IT

### STEP 1: Scope Assessment

**Ask these questions:**
1. Is this REALLY needed? Can a catalog fix work?
2. What is the MINIMUM change required?
3. Which files must be modified?
4. What could break?

### STEP 2: Backup Current State

```powershell
git stash
# or
git commit -m "WIP: Before BUG-XXX fix"
```

### STEP 3: Identify Exact Location

Common fix locations:

| Issue Type | File | Function |
|------------|------|----------|
| Function translation | `function_translator.py` | `translate_formula()` |
| SQL rendering | `renderer.py` | Various `_render_*()` |
| Parameter cleanup | `renderer.py` | `_cleanup_hana_parameter_conditions()` |
| Column qualification | `renderer.py` | `_render_expression()` |
| CTE ordering | `renderer.py` | `_topological_sort()` |
| View name handling | `renderer.py` | `_generate_view_statement()` |

### STEP 4: Make SURGICAL Change

**Guidelines:**
- Change ONLY the lines needed for THIS bug
- Add BUG-XXX comment explaining the change
- NO refactoring, NO "improvements", NO cleanup
- If unsure, change LESS not MORE

**Example:**
```python
# BUG-XXX: Fix column qualification in JOIN calculated columns
# Before: column_expr was used directly
# After: qualified with table alias to avoid ambiguity
if join_context:
    column_expr = f"{table_alias}.{column_expr}"  # BUG-XXX fix
```

### STEP 5: Single Change Test

**IMMEDIATELY after change:**
1. Save file
2. Restart server: `utilities\restart_server.bat`
3. Test target XML
4. Check HANA result

**If ERROR:**
- REVERT immediately
- Analyze what went wrong
- Try smaller change

### STEP 6: Regression Test

**MANDATORY before claiming fix works:**

```powershell
utilities\validate_all_xmls.bat
```

Test ALL 13 validated XMLs from GOLDEN_COMMIT.yaml:
1. CV_CNCLD_EVNTS.xml
2. CV_INVENTORY_ORDERS.xml
3. CV_PURCHASE_ORDERS.xml
4. CV_EQUIPMENT_STATUSES.xml
5. CV_TOP_PTHLGY.xml
6. CV_MCM_CNTRL_Q51.xml
7. CV_MCM_CNTRL_REJECTED.xml
8. CV_UPRT_PTLG.xml
9. CV_ELIG_TRANS_01.xml
10. CV_COMMACT_UNION.xml
11. CV_INVENTORY_STO.xml
12. CV_PURCHASING_YASMIN.xml
(13. CV_CT02_CT03.xml - known limitation, skip)

**If ANY regression:**
- STOP immediately
- REVERT: `git checkout -- <file>`
- Do NOT proceed
- Find alternative approach

### STEP 7: Document Code Change

Record:
- File modified
- Lines changed (before/after)
- BUG-XXX reference
- Why change was necessary

---

## Fix Documentation Checklist

After ANY successful fix:

- [ ] BUG-XXX documented in BUG_TRACKER.md
- [ ] If catalog change: entry has description with BUG-XXX reference
- [ ] If code change: inline BUG-XXX comment added
- [ ] Regression test passed (all 13 XMLs)
- [ ] Ready for SUCCESS_PROCEDURE.md

---

## Fix Strategy Decision Tree

```
Root Cause Identified
        │
        ▼
┌───────────────────────┐
│ Missing function      │ ──► CATALOG FIX (functions.yaml)
│ mapping?              │
└───────────────────────┘
        │ NO
        ▼
┌───────────────────────┐
│ Missing pattern       │ ──► CATALOG FIX (patterns.yaml)
│ rewrite?              │
└───────────────────────┘
        │ NO
        ▼
┌───────────────────────┐
│ Wrong schema/mode?    │ ──► CONFIG FIX (config.yaml)
└───────────────────────┘
        │ NO
        ▼
┌───────────────────────┐
│ Code logic issue?     │ ──► CODE FIX (DANGEROUS)
│                       │     Follow surgical procedure
└───────────────────────┘
        │ NO
        ▼
┌───────────────────────┐
│ Known limitation?     │ ──► DEFER
│                       │     Document in BUG_TRACKER
│                       │     Mark as "Active - Deferred"
└───────────────────────┘
```

---

## Post-Fix Workflow

After fix is verified:

1. **If fix worked** → Go to `SUCCESS_PROCEDURE.md`
   - Update SOLVED_BUGS.md
   - Update GOLDEN_COMMIT.yaml
   - Copy SQL to VALIDATED folder
   - Commit changes

2. **If fix failed** → Return to debugging
   - Re-analyze root cause
   - Try alternative approach
   - Consider deferring if no safe fix exists

---

## Anti-Patterns (AVOID)

| Anti-Pattern | Why Bad | Correct Approach |
|--------------|---------|------------------|
| "While I'm here" fixes | Breaks unrelated code | Fix ONLY the target bug |
| Refactoring during fix | Introduces new bugs | Refactor AFTER bug confirmed fixed |
| Large changes | Hard to debug | Small, surgical changes |
| No regression test | Breaks validated XMLs | ALWAYS test all 13 XMLs |
| Guessing at fix | Wastes time | Complete debugging first |

---

## Related Documents

- `ERROR_PROCEDURE_NO_BASELINE.md` - Debugging (new XMLs)
- `SQL_ERROR_INVESTIGATION_PROCEDURE.md` - Debugging (has baseline)
- `SUCCESS_PROCEDURE.md` - Post-fix documentation
- `.claude/CLAUDE.md` Rules 13-17 - Code change rules
- `.claude/MANDATORY_PROCEDURES.md` - Bug checking procedure
- `GOLDEN_COMMIT.yaml` - Regression baseline

---

**Last Updated**: 2025-12-10
