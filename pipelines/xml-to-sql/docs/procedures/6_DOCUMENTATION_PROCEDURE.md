# 6. Documentation Procedure

**Version**: 1.0
**Created**: 2025-12-10
**Purpose**: Systematic documentation requirements after successful validation or significant changes

---

## When to Use This Procedure

- After HANA validation succeeds (SUCCESS_PROCEDURE.md)
- After implementing bug fixes
- After adding new features
- Before committing any changes
- At session end

---

## Documentation Artifacts

| Artifact | Purpose | Update Frequency |
|----------|---------|------------------|
| `GOLDEN_COMMIT.yaml` | Baseline tracking | After each XML validation |
| `BUG_TRACKER.md` | Active bugs | When new bugs discovered |
| `SOLVED_BUGS.md` | Solved bugs archive | When bugs resolved |
| `HANA_CONVERSION_RULES.md` | Conversion rules | When new patterns found |
| `llm_handover.md` | Session state | Every session |
| `VALIDATED/*.sql` | Golden SQL files | After each validation |

---

## PROCEDURE: Post-Success Documentation

### STEP 1: Update GOLDEN_COMMIT.yaml

**Location**: `pipelines/xml-to-sql/GOLDEN_COMMIT.yaml`

**Add validated XML entry:**
```yaml
validated_xmls:
  files:
    - name: "CV_EXAMPLE.xml"
      source: "Source (XML Files)/HANA 1.XX XML Views/BW_ON_HANA/"
      execution_time: "XXms"
      validation_date: "YYYY-MM-DD"
      notes: "Description of any bugs fixed or special handling"
```

**Update count:**
```yaml
validated_xmls:
  count: [INCREMENT BY 1]
  success_rate: "100%"
```

### STEP 2: Archive Solved Bugs

**If bugs were fixed during validation:**

1. **Read BUG_TRACKER.md** to find related bug entries
2. **Move to SOLVED_BUGS.md** with solution details:

```markdown
### BUG-XXX: [Title]

**Status**: RESOLVED
**Discovered**: [Original date] in [XML name]
**Resolved**: [Current date]
**Affected**: [List of XMLs]

**Problem**:
[Description of the bug]

**Root Cause**:
[Analysis of why it happened]

**Solution**:
[How it was fixed]
- File: [filename]
- Lines: [line numbers]
- Change: [description]

**Validation**:
- XML: [name]
- HANA execution: [time]ms
```

3. **Remove from BUG_TRACKER.md** (move, don't duplicate)

### STEP 3: Update Conversion Rules (If New Pattern Found)

**Location**: `pipelines/xml-to-sql/rules/hana/HANA_CONVERSION_RULES.md`

**If new transformation rule discovered:**

```markdown
### Rule #XX: [Rule Name]

**Priority**: [1-5]
**Status**: IMPLEMENTED
**Added**: [Date]
**Reference**: BUG-XXX

**Transformation**:
```
BEFORE: [input pattern]
AFTER:  [output pattern]
```

**Implementation**:
- File: [location]
- Function: [name]

**Validated In**:
- [XML name] - [execution time]ms
```

### STEP 4: Copy SQL to VALIDATED Folder

**Location**: `pipelines/xml-to-sql/Target (SQL Scripts)/VALIDATED/hana/`

```powershell
copy "C:\Users\iliya\OneDrive\Desktop\X2S\xsodus_converter\LATEST_SQL_FROM_DB.txt" ^
     "pipelines\xml-to-sql\Target (SQL Scripts)\VALIDATED\hana\CV_EXAMPLE.sql"
```

**Purpose**: Golden reference for regression testing

### STEP 5: Update llm_handover.md

**Location**: `docs/llm_handover.md`

**Required updates:**
- Session summary
- XMLs validated (add new one)
- Bugs fixed (list BUG-XXX numbers)
- Code changes (files modified)
- Next steps
- Any architectural decisions made

**Template:**
```markdown
## Session Update [YYYY-MM-DD]

### Validated XMLs
- CV_EXAMPLE.xml - XXms (new)
- [Previous XMLs...]

### Bugs Fixed
- BUG-XXX: [description]

### Changes Made
- File: [name] - [description]

### Next Steps
1. [Next action]
```

---

## PROCEDURE: Bug Documentation

### New Bug Discovery

**When HANA returns an error for a new pattern:**

1. **Assign BUG-XXX number** (check SOLVED_BUGS.md for last number)
2. **Add to BUG_TRACKER.md**:

```markdown
### BUG-XXX: [Short Title]

**Priority**: [Critical/High/Medium/Low]
**Status**: Active
**Discovered**: [Date] in [XML name]
**Affects**: [List of affected XMLs]

**Error**:
```
[Exact HANA error message]
```

**Problem SQL**:
```sql
[SQL fragment showing the issue]
```

**Root Cause**:
[Analysis]

**Proposed Solution**:
[How to fix]

**Next Steps**:
1. [Action items]
```

### Bug Resolution

1. **Keep original BUG-XXX number** (NEVER renumber)
2. **Move to SOLVED_BUGS.md** with solution
3. **Remove from BUG_TRACKER.md**
4. **Add BUG-XXX comment in code** where fix was applied

---

## PROCEDURE: Session End Documentation

### STEP 1: Review Session Work

**Check what was accomplished:**
- [ ] Which XMLs were tested?
- [ ] Which bugs were encountered?
- [ ] What fixes were implemented?
- [ ] What files were modified?

### STEP 2: Update llm_handover.md

**Mandatory per CLAUDE.md Rule 11:**

```markdown
## Session [N] Summary - [Date]

### Work Completed
- [List of tasks completed]

### XMLs Validated
| XML | Status | Time | Notes |
|-----|--------|------|-------|
| CV_EXAMPLE | PASS | XXms | [notes] |

### Bugs Fixed
| Bug | Status | Solution |
|-----|--------|----------|
| BUG-XXX | RESOLVED | [brief] |

### Files Modified
- [file1]: [change description]
- [file2]: [change description]

### Next Steps
1. [Priority 1 task]
2. [Priority 2 task]

### Notes for Next Session
- [Important context]
```

### STEP 3: Commit Changes

**If changes were made:**

```powershell
git add -A
git status  # Review what's being committed
git commit -m "TYPE: Summary

## Changes
- [list changes]

## Validation
- [test results]

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Documentation Checklist

### After HANA Success:
- [ ] GOLDEN_COMMIT.yaml updated with new XML
- [ ] SQL copied to VALIDATED folder
- [ ] Bugs moved to SOLVED_BUGS.md
- [ ] Rules updated if new pattern found
- [ ] llm_handover.md updated

### After Bug Fix:
- [ ] BUG-XXX documented in tracker
- [ ] Code comments added with BUG-XXX reference
- [ ] SOLVED_BUGS.md updated with solution

### At Session End:
- [ ] llm_handover.md has session summary
- [ ] All changes committed
- [ ] Next steps documented

---

## Document Locations

| Document | Path |
|----------|------|
| GOLDEN_COMMIT.yaml | `pipelines/xml-to-sql/GOLDEN_COMMIT.yaml` |
| BUG_TRACKER.md | `pipelines/xml-to-sql/docs/BUG_TRACKER.md` |
| SOLVED_BUGS.md | `pipelines/xml-to-sql/docs/SOLVED_BUGS.md` |
| HANA_CONVERSION_RULES.md | `pipelines/xml-to-sql/rules/hana/HANA_CONVERSION_RULES.md` |
| llm_handover.md | `docs/llm_handover.md` |
| VALIDATED SQL | `pipelines/xml-to-sql/Target (SQL Scripts)/VALIDATED/hana/` |

---

## Related Documents

- `SUCCESS_PROCEDURE.md` - Post-success workflow (references this)
- `.claude/CLAUDE.md` Rule 11 - llm_handover.md maintenance
- `.claude/CLAUDE.md` Rule 15 - Change documentation protocol
- `.claude/MANDATORY_PROCEDURES.md` - Bug ID preservation rules

---

**Last Updated**: 2025-12-10
