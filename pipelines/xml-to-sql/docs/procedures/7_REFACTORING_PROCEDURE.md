# 7. Refactoring Procedure

**Version**: 1.0
**Created**: 2025-12-10
**Purpose**: Guidelines for safe code cleanup and optimization after debugging cycles

---

## When to Use This Procedure

- After multiple bugs fixed in same area
- When code duplication is excessive
- When technical debt accumulation is clear
- When explicitly requested by user
- **NEVER during active bug fixing**

---

## Core Principle

### CLAUDE.md Rule 17: IF IT WORKS, DON'T TOUCH IT

**Translation for Refactoring:**
- Refactor ONLY when explicitly justified
- Refactor ONLY after all bugs in area are fixed
- Refactor with SAME surgical precision as bug fixes
- Test EVERYTHING after refactoring

---

## Refactoring Triggers

### Safe to Refactor

| Trigger | Example | Proceed If |
|---------|---------|------------|
| Explicit request | "Clean up this code" | User asked |
| Completed bug cycle | 5 bugs fixed in renderer.py | All tests pass |
| Clear duplication | Same code in 3 places | Can consolidate safely |
| Performance issue | Slow SQL generation | Profiled and identified |

### DO NOT Refactor

| Condition | Why Not |
|-----------|---------|
| During bug fix | Mixing concerns causes regressions |
| "While I'm here" | Rule 13 violation |
| Working code that looks ugly | Rule 17 - if it works, leave it |
| Complex code you don't understand | Risk of breaking logic |

---

## PROCEDURE: Safe Refactoring

### STEP 1: Justify the Refactoring

**Document:**
```markdown
REFACTORING JUSTIFICATION:

1. What: [What code to refactor]
2. Why: [Specific reason - user request/duplication/tech debt]
3. Benefit: [What improves]
4. Risk: [What could break]
5. Approval: [User approved: YES/NO]
```

**If cannot justify, DO NOT REFACTOR**

### STEP 2: Establish Baseline

**Before ANY refactoring:**

1. **Run full regression test:**
   ```powershell
   utilities\validate_all_xmls.bat
   ```

2. **Document baseline:**
   - [ ] All 13 XMLs pass
   - [ ] Record baseline state

3. **Create safe restore point:**
   ```powershell
   git stash  # or
   git commit -m "WIP: Pre-refactoring baseline"
   ```

### STEP 3: Define Scope

**List EXACTLY what will change:**

```markdown
REFACTORING SCOPE:

Files affected:
1. [file1.py] - [what changes]
2. [file2.py] - [what changes]

Functions affected:
1. [function_name()] - [change type]
2. [function_name()] - [change type]

WILL NOT TOUCH:
- [list code staying unchanged]
```

### STEP 4: Execute Incrementally

**Golden Rule**: One refactoring change at a time

```
Change 1 → Test → Pass? → Change 2 → Test → Pass? → ...
              ↓                            ↓
           REVERT                       REVERT
```

**For each change:**
1. Make SINGLE refactoring change
2. Save file
3. Run target XML test
4. Run regression test (all 13 XMLs)
5. Only proceed if ALL pass

### STEP 5: Verify Behavior Preservation

**After ALL refactoring:**

1. **Full regression test:**
   ```powershell
   utilities\validate_all_xmls.bat
   ```

2. **Verify identical output:**
   - SQL output should be IDENTICAL to before
   - HANA execution times should be similar

3. **If ANY difference:**
   - STOP
   - REVERT to pre-refactoring state
   - Analyze what changed behavior

### STEP 6: Document Changes

**Update documentation:**
- [ ] Code comments explain new structure
- [ ] No BUG-XXX references removed
- [ ] llm_handover.md updated

---

## Types of Safe Refactoring

### Type 1: Extract Function

**When**: Same code block appears in multiple places

**Pattern:**
```python
# BEFORE (duplicated in 3 places)
result = complex_operation(a)
result = transform(result, b)
return format_output(result)

# AFTER (extracted)
def _process_and_format(a, b):
    """Extracted helper for [purpose]. See refactoring [date]."""
    result = complex_operation(a)
    result = transform(result, b)
    return format_output(result)
```

### Type 2: Simplify Conditional

**When**: Nested if/else becomes unreadable

**Pattern:**
```python
# BEFORE
if a:
    if b:
        if c:
            do_thing()

# AFTER
if a and b and c:
    do_thing()
```

### Type 3: Rename for Clarity

**When**: Variable/function names are unclear

**Pattern:**
```python
# BEFORE
x = get_data()

# AFTER
column_expressions = get_data()
```

### Type 4: Remove Dead Code

**When**: Code is unreachable or unused

**WARNING**: Verify code is truly dead:
- Search for all references
- Check if called via reflection/dynamic calls
- Only remove if 100% sure unused

---

## Refactoring Anti-Patterns

| Anti-Pattern | Risk | Instead |
|--------------|------|---------|
| "Clean up as I fix bugs" | Scope creep | Separate commits |
| Large-scale restructuring | Regressions | Small incremental changes |
| Changing working code | Breaking functionality | Leave alone |
| Removing "unused" BUG comments | Losing history | Keep all BUG-XXX refs |
| Changing function signatures | Breaking callers | Preserve interfaces |

---

## Refactoring Checklist

**Before Starting:**
- [ ] User explicitly requested or approved
- [ ] All current bugs fixed
- [ ] Full regression test passes
- [ ] Scope clearly defined
- [ ] Restore point created

**During Refactoring:**
- [ ] One change at a time
- [ ] Test after each change
- [ ] Behavior preserved
- [ ] No "while I'm here" additions

**After Refactoring:**
- [ ] Full regression test passes
- [ ] SQL output identical
- [ ] Documentation updated
- [ ] No functionality lost

---

## Emergency Revert

**If refactoring causes ANY regression:**

```powershell
# Option 1: Full revert
git checkout -- <files>

# Option 2: Restore stash
git stash pop

# Option 3: Reset to commit
git reset --hard <commit_before_refactoring>
```

**Then:**
1. Document what went wrong
2. Analyze why behavior changed
3. Either abandon refactoring or find safer approach

---

## Post-Refactoring Cleanup

### Technical Debt Tracking

**If refactoring identified more debt to address later:**

```markdown
## Technical Debt Log

### TD-001: [Description]
- Location: [file:lines]
- Impact: LOW/MEDIUM/HIGH
- Effort: LOW/MEDIUM/HIGH
- Discovered: [date]
- Status: DEFERRED

### TD-002: [Description]
...
```

---

## Related Documents

- `.claude/CLAUDE.md` Rule 17 - "If it works, don't touch it"
- `2_DEVELOPMENT_PROCEDURE.md` - Code change rules
- `3_TESTING_PROCEDURE.md` - Regression testing
- `GOLDEN_COMMIT.yaml` - Baseline for verification

---

**Last Updated**: 2025-12-10
