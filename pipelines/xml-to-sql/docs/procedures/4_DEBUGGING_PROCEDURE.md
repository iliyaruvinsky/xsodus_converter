# 4. Debugging Procedure

**Version**: 1.0
**Created**: 2025-12-10
**Purpose**: Index for debugging procedures based on context

---

## When to Use This Procedure

- When HANA returns an error
- When generated SQL is incorrect
- When conversion fails
- When regression is detected

---

## Procedure Selection

| Condition | Procedure | Location |
|-----------|-----------|----------|
| New XML (no baseline) | 12-Step Investigation | `ERROR_PROCEDURE_NO_BASELINE.md` |
| Has VALIDATED baseline | 10-Step Investigation | `SQL_ERROR_INVESTIGATION_PROCEDURE.md` |

---

## Quick Decision Tree

```
HANA Error Received
        │
        ▼
Does this XML have a VALIDATED/*.sql baseline?
        │
        ├── YES → SQL_ERROR_INVESTIGATION_PROCEDURE.md (10 steps)
        │         Compare with baseline, identify what changed
        │
        └── NO  → ERROR_PROCEDURE_NO_BASELINE.md (12 steps)
                  Full investigation from scratch
```

---

## Procedure A: New XML (No Baseline)

**File**: `pipelines/xml-to-sql/docs/ERROR_PROCEDURE_NO_BASELINE.md`

**Steps Overview:**
1. Read Generated SQL
2. Locate Exact Error Line
3. Identify SQL Pattern at Error
4. Search Known Bug Patterns
5. Check Conversion Rules
6. Analyze XML Source
7. Check Catalog Completeness
8. Root Cause Determination
9. Determine Fix Strategy
10. Document as New Bug
11. Implement Fix
12. Request Regeneration

**Use When:**
- Testing a new XML for the first time
- No reference SQL exists in `VALIDATED/` folder
- Need full investigation from scratch

---

## Procedure B: Has VALIDATED Baseline

**File**: `pipelines/xml-to-sql/docs/SQL_ERROR_INVESTIGATION_PROCEDURE.md`

**Steps Overview:**
1. Capture Generated SQL
2. Identify Error Location
3. Compare with VALIDATED SQL
4. Check Catalogs Exist
5. Verify Configuration
6. Map Errors to Rules
7. Check Rule Implementation
8. Root Cause Analysis
9. Check Commit Timeline
10. Determine Fix Strategy

**Use When:**
- XML previously validated successfully
- VALIDATED/*.sql file exists for comparison
- Regression occurred (worked before, fails now)

---

## Supporting Documents

During debugging, you may need to reference:

| Document | Purpose | When to Use |
|----------|---------|-------------|
| `BUG_TRACKER.md` | Known active bugs | Check if error is known |
| `SOLVED_BUGS.md` | Past solutions | Check for similar patterns |
| `HANA_CONVERSION_RULES.md` | Rule definitions | Map error to rule violation |
| `GOLDEN_COMMIT.yaml` | Baseline reference | Check validated state |
| `CONVERSION_FLOW_MAP.md` | Architecture | Understand pipeline flow |

---

## Common Error Patterns

### Quick Reference

| HANA Error | Likely Cause | Check First |
|------------|--------------|-------------|
| `[321] invalid view name` | View name quoting | BUG-029 |
| `[328] invalid name of function` | Missing catalog entry | functions.yaml |
| `[257] syntax error near )` | Parameter cleanup | BUG-021, BUG-022 |
| `[260] invalid column name` | Column qualification | BUG-027 |
| `[259] invalid table name` | CTE ordering | BUG-028 |
| `[362] invalid schema` | Schema mapping | config.yaml |

---

## After Debugging

Once root cause is identified:

```
Root Cause Identified
        │
        ▼
Go to 5_BUG_FIX_PROCEDURE.md
        │
        ▼
After fix implemented
        │
        ├── SUCCESS → 6_DOCUMENTATION_PROCEDURE.md
        │
        └── FAIL    → Return to debugging
```

---

## Debugging Checklist

- [ ] Error message captured completely
- [ ] Line number and column noted
- [ ] SQL fragment at error identified
- [ ] BUG_TRACKER.md checked
- [ ] SOLVED_BUGS.md checked
- [ ] Root cause determined
- [ ] Fix strategy identified
- [ ] Ready for 5_BUG_FIX_PROCEDURE.md

---

## Related Documents

- `ERROR_PROCEDURE_NO_BASELINE.md` - Full 12-step procedure
- `SQL_ERROR_INVESTIGATION_PROCEDURE.md` - 10-step procedure with baseline
- `5_BUG_FIX_PROCEDURE.md` - After debugging, implement fix
- `.claude/MANDATORY_PROCEDURES.md` - Bug checking requirements
- `docs/BUG_TRACKER.md` - Active bugs
- `docs/SOLVED_BUGS.md` - Solved bugs archive

---

**Last Updated**: 2025-12-10
