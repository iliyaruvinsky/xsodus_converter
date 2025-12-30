# SDLC Master Procedure Index

**Version**: 1.0
**Created**: 2025-12-10
**Purpose**: Single entry point for all development lifecycle processes

---

## Quick Reference - Which Procedure to Follow

| Trigger | Procedure | Location |
|---------|-----------|----------|
| New feature/change request | **1. PLANNING** | `pipelines/xml-to-sql/docs/procedures/1_PLANNING_PROCEDURE.md` |
| Writing code | **2. DEVELOPMENT** | `pipelines/xml-to-sql/docs/procedures/2_DEVELOPMENT_PROCEDURE.md` |
| Testing XML conversion | **3. TESTING** | `pipelines/xml-to-sql/docs/procedures/3_TESTING_PROCEDURE.md` |
| HANA error (new XML) | **4. DEBUGGING** | `pipelines/xml-to-sql/docs/ERROR_PROCEDURE_NO_BASELINE.md` |
| HANA error (has baseline) | **4. DEBUGGING** | `pipelines/xml-to-sql/docs/SQL_ERROR_INVESTIGATION_PROCEDURE.md` |
| Implementing a fix | **5. BUG FIX** | `pipelines/xml-to-sql/docs/procedures/5_BUG_FIX_PROCEDURE.md` |
| HANA success | **6. DOCUMENTATION** | `pipelines/xml-to-sql/docs/SUCCESS_PROCEDURE.md` |
| Cleanup/optimization | **7. REFACTORING** | `pipelines/xml-to-sql/docs/procedures/7_REFACTORING_PROCEDURE.md` |

---

## The 7 SDLC Processes

### 1. PLANNING
**When**: Before starting any new feature, significant change, or bug fix
**Procedure**: `pipelines/xml-to-sql/docs/procedures/1_PLANNING_PROCEDURE.md`

**Key steps**:
1. Define the change scope
2. Impact analysis using CONVERSION_FLOW_MAP.md
3. Risk assessment
4. Identify affected files
5. Get user approval before implementation

**Related documents**:
- `pipelines/xml-to-sql/docs/CONVERSION_FLOW_MAP.md` - Architecture reference
- `.claude/CLAUDE.md` Rule 13 - Minimal changes principle

---

### 2. DEVELOPMENT
**When**: Writing or modifying code
**Procedure**: `pipelines/xml-to-sql/docs/procedures/2_DEVELOPMENT_PROCEDURE.md`

**Key rules** (from CLAUDE.md):
- Rule 13: MINIMAL CODE CHANGES - Surgical precision
- Rule 14: REGRESSION TESTING MANDATE
- Rule 15: CHANGE DOCUMENTATION PROTOCOL
- Rule 16: CORE SQL GENERATION PROTECTION
- Rule 17: IF IT WORKS, DON'T TOUCH IT

**Related documents**:
- `.claude/MANDATORY_PROCEDURES.md` - Code change procedure
- `.claude/PIPELINE_ISOLATION_RULES.md` - Code import rules
- `pipelines/xml-to-sql/rules/hana/HANA_CONVERSION_RULES.md` - Implementation rules

**Key files for changes**:
- Catalog fixes: `catalog/hana/data/functions.yaml`, `patterns.yaml`
- Code fixes: `src/xml_to_sql/sql/renderer.py`, `function_translator.py`

---

### 3. TESTING
**When**: After any code change, before claiming success
**Procedure**: `pipelines/xml-to-sql/docs/procedures/3_TESTING_PROCEDURE.md`

**Key steps**:
1. Run `utilities/restart_server.bat`
2. Test the target XML via web UI
3. Run in HANA
4. If ALL 13 validated XMLs affected, run regression test

**Related documents**:
- `pipelines/xml-to-sql/GOLDEN_COMMIT.yaml` - Baseline (13 validated XMLs)
- `.claude/MANDATORY_PROCEDURES.md` - SQL validation checks

**Automation scripts**:
- `utilities/restart_server.bat` - Restart server after changes
- `utilities/validate_all_xmls.bat` - Run all regression tests

---

### 4. DEBUGGING
**When**: HANA returns an error
**Procedure**: Depends on whether VALIDATED baseline exists

#### 4a. NEW XML (no baseline)
**Procedure**: `pipelines/xml-to-sql/docs/ERROR_PROCEDURE_NO_BASELINE.md` (12 steps)

Steps:
1. Read generated SQL
2. Locate exact error line
3. Identify SQL pattern at error
4. Search known bug patterns
5. Check conversion rules
6. Analyze XML source
7. Check catalog completeness
8. Root cause determination
9. Determine fix strategy
10. Document as new bug
11. Implement fix
12. Request regeneration

#### 4b. HAS VALIDATED BASELINE
**Procedure**: `pipelines/xml-to-sql/docs/SQL_ERROR_INVESTIGATION_PROCEDURE.md` (10 steps)

Steps:
1. Capture generated SQL
2. Identify error location
3. Compare with VALIDATED SQL
4. Check catalogs exist
5. Verify configuration
6. Map errors to rules
7. Check rule implementation
8. Root cause analysis
9. Check commit timeline
10. Determine fix strategy

**Related documents**:
- `pipelines/xml-to-sql/docs/BUG_TRACKER.md` - Known active bugs
- `pipelines/xml-to-sql/docs/SOLVED_BUGS.md` - Past solutions
- `pipelines/xml-to-sql/rules/hana/HANA_CONVERSION_RULES.md` - Error-to-rule mapping

---

### 5. BUG FIX
**When**: After debugging identifies root cause, ready to implement fix
**Procedure**: `pipelines/xml-to-sql/docs/procedures/5_BUG_FIX_PROCEDURE.md`

**Fix types** (in order of safety):
1. **CATALOG FIX** (SAFE) - Add to functions.yaml or patterns.yaml
2. **CONFIG FIX** (SAFE) - Update config.yaml
3. **CODE FIX** (DANGEROUS) - Modify renderer.py or function_translator.py

**Key rules**:
- Surgical precision - only change what's needed
- Test after EVERY change
- Document with BUG-XXX comments

**Related documents**:
- `.claude/MANDATORY_PROCEDURES.md` - Code change procedure
- `.claude/CLAUDE.md` Rules 13-17

---

### 6. DOCUMENTATION
**When**: After HANA validation succeeds
**Procedure**: `pipelines/xml-to-sql/docs/SUCCESS_PROCEDURE.md` (4 steps)

**Key steps**:
1. Update productive scripts (functions.yaml, patterns.yaml)
2. Update documentation:
   - GOLDEN_COMMIT.yaml
   - BUG_TRACKER.md → SOLVED_BUGS.md
   - HANA_CONVERSION_RULES.md (if new rule)
   - Copy SQL to VALIDATED/ folder
   - Update llm_handover.md
3. Commit changes
4. Move to next XML

**Related documents**:
- `.claude/CLAUDE.md` Rule 11 - llm_handover.md maintenance
- `.claude/CLAUDE.md` Rule 15 - Change documentation protocol

---

### 7. REFACTORING
**When**: After debugging cycle complete, code cleanup needed
**Procedure**: `pipelines/xml-to-sql/docs/procedures/7_REFACTORING_PROCEDURE.md`

**When to refactor**:
- Multiple bugs fixed in same area
- Code duplication identified
- Technical debt accumulation
- NEVER during active bug fixing

**Key rule** (CLAUDE.md Rule 17):
- IF IT WORKS, DON'T TOUCH IT
- Refactor only when explicitly requested or clearly necessary

---

## Typical Workflow Sequences

### New Feature Development
```
1. PLANNING → 2. DEVELOPMENT → 3. TESTING → [4. DEBUGGING → 5. BUG FIX → 3. TESTING]* → 6. DOCUMENTATION
```

### Bug Fix from User Report
```
4. DEBUGGING → 5. BUG FIX → 3. TESTING → 6. DOCUMENTATION
```

### New XML Validation
```
3. TESTING → [4. DEBUGGING → 5. BUG FIX → 3. TESTING]* → 6. DOCUMENTATION
```

### Post-Sprint Cleanup
```
1. PLANNING (scope) → 7. REFACTORING → 3. TESTING → 6. DOCUMENTATION
```

---

## Mandatory Rule (CLAUDE.md Rule 19)

**EVERY development activity MUST follow the appropriate procedure from this index.**

Execution requirements:
- ALWAYS explicitly state which procedure you are following
- ALWAYS cite step numbers as you execute them
- NEVER improvise or skip steps
- If a step doesn't apply, explicitly state why

**NO EXCEPTIONS**

---

## Document Locations Summary

### AI Behavior Rules (.claude/)
| Document | Purpose |
|----------|---------|
| `CLAUDE.md` | 19 mandatory behavior rules |
| `MANDATORY_PROCEDURES.md` | Bug-checking, SQL analysis, validation |
| `PIPELINE_ISOLATION_RULES.md` | Context isolation rules |
| `SDLC_MASTER_PROCEDURE.md` | This index |

### Pipeline Procedures (pipelines/xml-to-sql/docs/)
| Document | Purpose |
|----------|---------|
| `ERROR_PROCEDURE_NO_BASELINE.md` | Debug new XMLs (12 steps) |
| `SQL_ERROR_INVESTIGATION_PROCEDURE.md` | Debug with baseline (10 steps) |
| `SUCCESS_PROCEDURE.md` | Post-success documentation (4 steps) |
| `BUG_TRACKER.md` | Active bugs |
| `SOLVED_BUGS.md` | Solved bugs archive |
| `CONVERSION_FLOW_MAP.md` | Pipeline architecture |

### Pipeline Procedures (pipelines/xml-to-sql/docs/procedures/)
| Document | Purpose |
|----------|---------|
| `1_PLANNING_PROCEDURE.md` | Feature/change planning |
| `2_DEVELOPMENT_PROCEDURE.md` | Code writing rules |
| `3_TESTING_PROCEDURE.md` | Testing process |
| `5_BUG_FIX_PROCEDURE.md` | Fix implementation |
| `6_DOCUMENTATION_PROCEDURE.md` | Documentation updates |
| `7_REFACTORING_PROCEDURE.md` | Code cleanup |

### Rules (pipelines/xml-to-sql/rules/)
| Document | Purpose |
|----------|---------|
| `hana/HANA_CONVERSION_RULES.md` | 26 HANA transformation rules |
| `snowflake/SNOWFLAKE_CONVERSION_RULES.md` | 5 Snowflake rules |

### Baselines (pipelines/xml-to-sql/)
| Document | Purpose |
|----------|---------|
| `GOLDEN_COMMIT.yaml` | 13 validated XMLs baseline |
| `VALIDATED/hana/*.sql` | Golden SQL files |

### Utilities (utilities/)
| Script | Purpose |
|--------|---------|
| `restart_server.bat` | Restart development server |
| `validate_all_xmls.bat` | Run regression tests |

---

**Last Updated**: 2025-12-10
**Version**: 1.0
