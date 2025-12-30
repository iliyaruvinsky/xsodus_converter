# 1. Planning Procedure

**Version**: 1.0
**Created**: 2025-12-10
**Purpose**: Systematic planning for new features, significant changes, and bug fixes

---

## When to Use This Procedure

- Before starting any new feature
- Before significant code changes
- Before implementing complex bug fixes
- When impact is unclear
- When multiple approaches exist

---

## Planning Principles

### From CLAUDE.md

| Rule | Application to Planning |
|------|------------------------|
| **Rule 13** | Plan for MINIMAL changes - scope correctly from start |
| **Rule 14** | Plan regression testing - know what could break |
| **Rule 17** | Plan to NOT touch working code |

---

## PROCEDURE: Feature/Change Planning

### STEP 1: Define the Change

**Answer these questions:**

1. **What is the goal?**
   - [ ] Specific outcome expected
   - [ ] Success criteria defined

2. **What problem does this solve?**
   - [ ] Bug fix (BUG-XXX reference)
   - [ ] New feature
   - [ ] Enhancement
   - [ ] Refactoring

3. **What is the scope?**
   - [ ] Single XML affected
   - [ ] Multiple XMLs affected
   - [ ] All XMLs affected

### STEP 2: Impact Analysis

**Reference**: `docs/CONVERSION_FLOW_MAP.md`

**Identify affected components:**

| Component | File(s) | Impact |
|-----------|---------|--------|
| XML Parsing | `parser/*.py` | LOW/MEDIUM/HIGH |
| IR Model | `domain/*.py` | LOW/MEDIUM/HIGH |
| SQL Rendering | `sql/renderer.py` | LOW/MEDIUM/HIGH |
| Function Translation | `sql/function_translator.py` | LOW/MEDIUM/HIGH |
| Catalog | `catalog/data/*.yaml` | LOW/MEDIUM/HIGH |
| Configuration | `config.yaml` | LOW/MEDIUM/HIGH |

**Impact Levels:**
- **LOW**: Isolated change, affects only specific XML patterns
- **MEDIUM**: Affects multiple XMLs or core components
- **HIGH**: Affects all SQL generation, high regression risk

### STEP 3: Risk Assessment

**Risk Matrix:**

| Risk Factor | Assessment |
|-------------|------------|
| Core file modification? | YES = HIGH RISK |
| Could break validated XMLs? | YES = HIGH RISK |
| Multiple files affected? | YES = MEDIUM RISK |
| Catalog-only change? | YES = LOW RISK |
| Config-only change? | YES = LOW RISK |

**Risk Level**: _______________

### STEP 4: Identify Files to Modify

**List EXACTLY which files need changes:**

```markdown
FILES TO MODIFY:
1. [file_path] - [reason]
   - Lines: [approximate location]
   - Change type: [add/modify/remove]

2. [file_path] - [reason]
   ...
```

**Rule**: If you can't list the files, you haven't understood the problem.

### STEP 5: Choose Implementation Strategy

**Strategy Selection:**

| Condition | Strategy | Risk |
|-----------|----------|------|
| Missing function mapping | Catalog Fix | LOW |
| Missing pattern rewrite | Catalog Fix | LOW |
| Wrong configuration | Config Fix | LOW |
| Logic error in existing code | Code Fix | MEDIUM |
| New capability needed | Code Addition | HIGH |
| Multiple interacting bugs | Phased Approach | HIGH |

**Selected Strategy**: _______________

### STEP 6: Define Success Criteria

**Before implementation, define:**

1. **What must work after change?**
   - Target XML validates in HANA
   - All 13 baseline XMLs still validate

2. **What tests will prove success?**
   - [ ] Target XML HANA execution time: ____ms
   - [ ] Regression test: all 13 XMLs pass

3. **What documentation needs updating?**
   - [ ] BUG_TRACKER.md / SOLVED_BUGS.md
   - [ ] GOLDEN_COMMIT.yaml
   - [ ] llm_handover.md
   - [ ] HANA_CONVERSION_RULES.md

### STEP 7: Get Approval

**For HIGH RISK changes:**
- Present plan to user
- Get explicit approval before implementation
- Document any constraints or requirements

---

## Planning Templates

### Template A: Bug Fix Plan

```markdown
## BUG-XXX Fix Plan

### Problem
[Description of the bug]

### Root Cause
[Why it happens]

### Proposed Fix
[How to fix it]

### Files to Modify
1. [file]: [change]
2. [file]: [change]

### Risk Assessment
- Risk Level: [LOW/MEDIUM/HIGH]
- Could affect: [list XMLs]
- Regression potential: [assessment]

### Success Criteria
- Target XML: [name] validates with time: ____ms
- Regression: All 13 baseline XMLs pass

### Approval
- [ ] User approved plan
```

### Template B: Feature Plan

```markdown
## Feature: [Name]

### Objective
[What this feature does]

### Scope
- Affects: [which XMLs/components]
- Does not affect: [what stays unchanged]

### Implementation Steps
1. [Step 1]
2. [Step 2]
3. [Step 3]

### Files to Modify
1. [file]: [change]
2. [file]: [change]

### Risk Assessment
- Risk Level: [LOW/MEDIUM/HIGH]
- Dependencies: [list]
- Regression potential: [assessment]

### Testing Plan
1. Test target functionality
2. Regression test all 13 XMLs

### Success Criteria
- [Specific measurable outcomes]

### Approval
- [ ] User approved plan
```

---

## Planning Checklist

Before starting implementation:

- [ ] Problem/goal clearly defined
- [ ] Impact analysis completed
- [ ] Risk level determined
- [ ] Files to modify identified
- [ ] Strategy selected
- [ ] Success criteria defined
- [ ] User approval obtained (for HIGH risk)

---

## Anti-Patterns in Planning

| Anti-Pattern | Problem | Correct Approach |
|--------------|---------|------------------|
| "I'll figure it out as I go" | Leads to scope creep | Plan before coding |
| "It's a small change" | Underestimates impact | Always assess risk |
| "I don't need to test that" | Causes regressions | Plan regression tests |
| "I'll refactor while fixing" | Breaks working code | Separate concerns |

---

## Related Documents

- `docs/CONVERSION_FLOW_MAP.md` - Pipeline architecture (for impact analysis)
- `.claude/CLAUDE.md` Rules 13, 14, 17 - Planning constraints
- `GOLDEN_COMMIT.yaml` - Baseline for regression planning
- `2_DEVELOPMENT_PROCEDURE.md` - Implementation after planning

---

**Last Updated**: 2025-12-10
