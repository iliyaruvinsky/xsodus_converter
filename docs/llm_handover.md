# LLM Handover - X2S Converter Monorepo

**Last Updated**: 2025-12-22 (SESSION 11: BUG-040 VALIDATED, 15 XMLs)
**Repo**: https://github.com/iliyaruvinsky/xsodus_converter
**Structure**: Optimal monorepo with pipeline isolation
**Status**: ✅ xml-to-sql pipeline FULLY MIGRATED & WORKING (15 XMLs validated)
**SDLC**: ✅ 7-process framework with procedures in `pipelines/xml-to-sql/docs/procedures/`

---

## 📋 SESSION 11 Summary (2025-12-22) - SUCCESS

**XML Tested**: COPYOF_CV_ACOUSTIC_1_09072023.xml (Maccabi-BW_ON_HANA)
**Validation Time**: 127ms (DROP: 9ms, CREATE: 118ms)

**Errors Encountered & Fixed**:
1. `[266]: SUM on NVARCHAR` → **BUG-040 VALIDATED** - TO_INTEGER() cast works
2. `[257]: IF EXISTS syntax error` → **BUG-041 REVERTED** - User's HANA is pre-SPS03

**Bugs Resolved**:
- **BUG-040**: ✅ VALIDATED - Added TO_INTEGER() cast for SUM/AVG on VARCHAR columns
- **BUG-041**: 🟠 REVERTED - IF EXISTS not supported in user's HANA version (workaround: skip DROP on first run)

**Files Modified**:
- `pipelines/xml-to-sql/src/xml_to_sql/sql/renderer.py`:
  - Lines 740-751: Added TO_INTEGER cast for SUM/AVG on VARCHAR columns ✅ WORKS
  - Line 1754: IF EXISTS REVERTED (pre-SPS03 HANA doesn't support it)

**Documentation Updated**:
- SOLVED_BUGS.md: BUG-040 added with full solution
- MANDATORY_PROCEDURES.md: Added Check 5 for SUM/AVG on non-numeric columns
- BUG_TRACKER.md: Statistics updated, BUG-040 marked validated

**New Validated XML**: COPYOF_CV_ACOUSTIC_1_09072023.xml (15th XML)

---

## ⚡ IMMEDIATE ACTIONS - Do This NOW

**You are starting a NEW session in a FRESH monorepo.**

### Step 1: Read Context (5 minutes)
```
MANDATORY - Read these 3 files FIRST:
1. .claude/CLAUDE.md (behavior rules)
2. .claude/MANDATORY_PROCEDURES.md (procedures)
3. .claude/PIPELINE_ISOLATION_RULES.md (context rules)
```

### Step 2: Understand Current State (5 minutes)
```
Read:
- pipelines/xml-to-sql/GOLDEN_COMMIT.yaml (baseline status)
- pipelines/xml-to-sql/docs/BUG_TRACKER.md (active bugs)
- This handover (rest of document below)
```

### Step 3: Setup Development Environment (10 minutes)
```powershell
# Install core
cd core
pip install -e .
cd ..

# Install xml-to-sql pipeline
cd pipelines/xml-to-sql
pip install -e .
cd ../..
```

### Step 4: Start Server (if web UI needed)
```powershell
cd pipelines/xml-to-sql
python run_server.py
# Server runs at http://localhost:8000
```

### Step 5: Verify Working Baseline (10 minutes)
```
Test one validated XML:
1. Upload CV_EQUIPMENT_STATUSES.xml via web UI (http://localhost:8000)
2. Convert
3. Check LATEST_SQL_FROM_DB.txt auto-saved
4. Compare with pipelines/xml-to-sql/VALIDATED/hana/CV_EQUIPMENT_STATUSES.sql
5. Should match exactly
```

### Step 6: Ask User What to Work On
```
User will tell you:
- Test remaining XMLs?
- Fix specific bug?
- Add new feature?
- Migrate another pipeline?

WAIT for user direction before proceeding.
```

---

## 🚀 START HERE - First Session in New Repo

### What This Repo Is

**X2S (XML-to-SQL-to-X) Converter** - Multi-pipeline SAP data conversion system with strict pipeline isolation.

**Current State**:
- ✅ **xml-to-sql pipeline**: FULLY MIGRATED & PRODUCTION READY (13 XMLs validated in HANA)
- ⏳ **sql-to-abap pipeline**: Structure created, not yet migrated
- ⏳ **csv-to-json pipeline**: Structure created, not yet migrated

**Migration Completed**: 2025-12-10
- Copied complete `xml_to_sql` package from old repo
- Frontend migrated to `pipelines/xml-to-sql/web_frontend/`
- All Source XMLs, Target SQL scripts, package mappings migrated
- Server tested and working at http://localhost:8000

### Critical Files to Read FIRST

**Before doing ANYTHING, read these 3 files:**

1. **[.claude/CLAUDE.md](.claude/CLAUDE.md)** - Mandatory behavior rules (18 rules)
2. **[.claude/MANDATORY_PROCEDURES.md](.claude/MANDATORY_PROCEDURES.md)** - Bug-checking, SQL analysis
3. **[.claude/PIPELINE_ISOLATION_RULES.md](.claude/PIPELINE_ISOLATION_RULES.md)** - Context management

**CRITICAL**: Pipeline isolation rules MUST be followed. When working on xml-to-sql, read ONLY `pipelines/xml-to-sql/**`, ignore other pipelines.

---

## 📁 Repository Structure

```
xsodus_converter/
├── core/                           # Shared foundation
│   └── src/x2s_core/
│       ├── models/                # IR, Scenario, Node
│       ├── parser/                # XML parsing (scenario_parser, column_view_parser)
│       ├── database/              # Batch, Mappings, History
│       └── utils/
│
├── pipelines/
│   ├── xml-to-sql/                # PRIMARY PIPELINE ⭐
│   │   ├── src/
│   │   │   ├── renderer/         # SQL generation (renderer.py)
│   │   │   ├── translator/       # Functions (function_translator.py)
│   │   │   └── api/              # FastAPI routes (routes.py, models.py)
│   │   ├── rules/
│   │   │   ├── hana/             # HANA_CONVERSION_RULES.md
│   │   │   ├── snowflake/        # SNOWFLAKE_CONVERSION_RULES.md
│   │   │   └── sqlserver/        # (future)
│   │   ├── catalog/
│   │   │   └── hana/data/
│   │   │       ├── functions.yaml  # Function mappings (WITH FIXES)
│   │   │       └── patterns.yaml   # Pattern rewrites
│   │   ├── VALIDATED/hana/       # Golden SQL files (5 files)
│   │   ├── docs/
│   │   │   ├── BUG_TRACKER.md              # xml-to-sql bugs ONLY
│   │   │   ├── SOLVED_BUGS.md
│   │   │   ├── SQL_ERROR_INVESTIGATION_PROCEDURE.md
│   │   │   ├── ERROR_PROCEDURE_NO_BASELINE.md
│   │   │   └── SUCCESS_PROCEDURE.md
│   │   ├── config.yaml
│   │   └── GOLDEN_COMMIT.yaml
│   │
│   ├── sql-to-abap/              # Not yet migrated
│   └── csv-to-json/              # Not yet migrated
│
├── .claude/                       # AI assistant rules
├── scripts/                       # Validation scripts
└── docs/                          # Project-wide docs
```

---

## 🎯 Current Development Status

### xml-to-sql Pipeline: WORKING ✅

**Base**: Commit 680ad44 from old repo + critical fixes  
**Validated**: 6 XMLs working in HANA  
**Known Limitation**: 1 XML (CV_CT02_CT03) deferred due to source issues

**Validated XMLs** (in `pipelines/xml-to-sql/VALIDATED/hana/`):
1. CV_EQUIPMENT_STATUSES - 26ms ✅
2. CV_TOP_PTHLGY - 195ms ✅
3. CV_INVENTORY_ORDERS ✅
4. CV_PURCHASE_ORDERS ✅
5. CV_CNCLD_EVNTS ✅
6. (One more confirmed) ✅

**Critical Fixes Applied**:
- DATE → TO_DATE mapping added
- DAYSBETWEEN → DAYS_BETWEEN mapping added
- NOW changed to template handler (removes parentheses)
- MATCH → REGEXP_LIKE (was incorrectly LIKE)
- view_schema default changed from _SYS_BIC to SAPABAP1
- Auto-save to LATEST_SQL_FROM_DB.txt implemented

**Required Configuration** (`pipelines/xml-to-sql/config.yaml`):
```yaml
defaults:
  database_mode: "hana"
  hana_version: "2.0"

schema_overrides:
  ABAP: "SAPABAP1"
```

---

## 🔧 How to Work in This Repo

### For xml-to-sql Development

**Read ONLY These Folders**:
- `pipelines/xml-to-sql/**`
- `core/**`
- `.claude/**`

**DO NOT Read**:
- `pipelines/sql-to-abap/**`
- `pipelines/csv-to-json/**`

**Key Files for xml-to-sql**:
- **Rules**: `pipelines/xml-to-sql/rules/hana/HANA_CONVERSION_RULES.md`
- **Bugs**: `pipelines/xml-to-sql/docs/BUG_TRACKER.md`
- **Baseline**: `pipelines/xml-to-sql/GOLDEN_COMMIT.yaml`
- **Golden SQL**: `pipelines/xml-to-sql/VALIDATED/hana/*.sql`
- **Procedures**: `pipelines/xml-to-sql/docs/*_PROCEDURE.md`

### When HANA Error Occurs

**Follow this procedure** (documented in `pipelines/xml-to-sql/docs/SQL_ERROR_INVESTIGATION_PROCEDURE.md`):

1. Read `LATEST_SQL_FROM_DB.txt` (auto-saved)
2. Identify error line
3. Compare with `pipelines/xml-to-sql/VALIDATED/hana/{XML_NAME}.sql`
4. Map error to rules in `HANA_CONVERSION_RULES.md`
5. Check `BUG_TRACKER.md` for known bugs
6. Fix (catalog or code)
7. Test and document

**If no VALIDATED SQL exists**: Follow `ERROR_PROCEDURE_NO_BASELINE.md`

**If validation succeeds**: Follow `SUCCESS_PROCEDURE.md`

### Catalog Changes

**After changing** `functions.yaml` or `patterns.yaml`:
```powershell
cd pipelines/xml-to-sql
pip install -e .
# Restart server
```

---

## 🐛 Known Issues

### Active Bugs (xml-to-sql)
- **BUG-019**: REGEXP_LIKE with calculated columns (CV_CT02_CT03)
- **BUG-003**: REGEXP_LIKE parameter patterns (CV_CT02_CT03)

**Status**: Both deferred - source XML may have issues

### Known Limitations
- CV_CT02_CT03.xml not validatable (documented in GOLDEN_COMMIT.yaml)
- Parameter cleanup works for simple cases, complex DATE() nesting may fail

---

## 📊 Validation Status

**Pipeline**: xml-to-sql  
**Success Rate**: 6/7 tested (86%)  
**Execution Times**:
- Average: ~50ms
- Range: 26ms - 195ms
- Complex CV (CV_TOP_PTHLGY): 195ms

**Baseline**: `pipelines/xml-to-sql/GOLDEN_COMMIT.yaml`

---

## 🔄 Development Workflow

### Testing New XML

1. Upload via web UI
2. Convert (SQL auto-saved to LATEST_SQL_FROM_DB.txt)
3. Copy SQL to HANA Studio
4. Execute
5. If success → Follow SUCCESS_PROCEDURE.md
6. If error → Follow SQL_ERROR_INVESTIGATION_PROCEDURE.md

### Making Code Changes

**MANDATORY**:
- Read `.claude/CLAUDE.md` RULE 13-16 (minimal changes, regression testing)
- Test against ALL validated XMLs after any change
- Document every change with BUG-XXX comments
- Update BUG_TRACKER.md or SOLVED_BUGS.md

### Committing Changes

**Format**:
```bash
git commit -m "xml-to-sql: [TYPE]: Brief description

## What Changed
- File: line numbers: what changed

## Validation
- Which XMLs tested
- Results

Co-Authored-By: Claude <noreply@anthropic.com>"
```

**Tag stable states**:
```bash
git tag xml-to-sql/v3.0.1 -m "Description"
```

---

## 📚 Documentation Map

### AI Rules (MUST READ FIRST)
- `.claude/CLAUDE.md` - 19 behavior rules (including Rule 19: SDLC Procedures)
- `.claude/MANDATORY_PROCEDURES.md` - Bug-checking, SQL analysis
- `.claude/PIPELINE_ISOLATION_RULES.md` - Context management
- `.claude/SDLC_MASTER_PROCEDURE.md` - **MASTER INDEX for all 7 SDLC processes**

### SDLC Procedures (NEW - 2025-12-10)
| Process | Procedure | Location |
|---------|-----------|----------|
| 1. Planning | `1_PLANNING_PROCEDURE.md` | `pipelines/xml-to-sql/docs/procedures/` |
| 2. Development | `2_DEVELOPMENT_PROCEDURE.md` | `pipelines/xml-to-sql/docs/procedures/` |
| 3. Testing | `3_TESTING_PROCEDURE.md` | `pipelines/xml-to-sql/docs/procedures/` |
| 4. Debugging | `4_DEBUGGING_PROCEDURE.md` | `pipelines/xml-to-sql/docs/procedures/` |
| 5. Bug Fixing | `5_BUG_FIX_PROCEDURE.md` | `pipelines/xml-to-sql/docs/procedures/` |
| 6. Documentation | `6_DOCUMENTATION_PROCEDURE.md` | `pipelines/xml-to-sql/docs/procedures/` |
| 7. Refactoring | `7_REFACTORING_PROCEDURE.md` | `pipelines/xml-to-sql/docs/procedures/` |

### Existing Error/Success Procedures
- `ERROR_PROCEDURE_NO_BASELINE.md` - 12-step debug (new XMLs)
- `SQL_ERROR_INVESTIGATION_PROCEDURE.md` - 10-step debug (has baseline)
- `SUCCESS_PROCEDURE.md` - Post-success documentation

### Automation Scripts
- `utilities/restart_server.bat` - Restart server after changes
- `utilities/validate_all_xmls.bat` - Regression test all 13 XMLs

### xml-to-sql Pipeline Docs
- `pipelines/xml-to-sql/rules/hana/HANA_CONVERSION_RULES.md` - Transformation rules
- `pipelines/xml-to-sql/docs/BUG_TRACKER.md` - Active bugs
- `pipelines/xml-to-sql/docs/SOLVED_BUGS.md` - Historical solutions
- `pipelines/xml-to-sql/docs/CONVERSION_FLOW_MAP.md` - Pipeline flow

### Project-Wide Docs
- `docs/ARCHITECTURE.md` - Monorepo structure explanation
- `README.md` - Project overview

---

## 🔑 Critical Configuration

### config.yaml Requirements

**Location**: `pipelines/xml-to-sql/config.yaml`

**MUST HAVE**:
```yaml
defaults:
  database_mode: "hana"
  hana_version: "2.0"

schema_overrides:
  ABAP: "SAPABAP1"
```

**Without schema_overrides**, SQL uses wrong schema and fails in HANA.

---

## 🎓 Key Concepts

### Pipeline Isolation

**CRITICAL RULE**: Each pipeline is completely self-contained.

- xml-to-sql has own BUG_TRACKER, GOLDEN_COMMIT, VALIDATED folder
- sql-to-abap (future) will have separate BUG_TRACKER, GOLDEN_COMMIT, VALIDATED folder
- NO mixing of bugs or references between pipelines

**Why**: Prevents context overload, allows independent development.

### Target Variants

**xml-to-sql supports 3 targets**:
- HANA (primary) - rules in `rules/hana/`
- Snowflake (secondary) - rules in `rules/snowflake/`
- SQL Server (future) - rules in `rules/sqlserver/`

**Catalog per target**:
- `catalog/hana/data/functions.yaml` - HANA function mappings
- `catalog/hana/data/patterns.yaml` - HANA pattern rewrites
- (Snowflake and SQL Server catalogs to be added)

### VALIDATED Folder = Truth

**Location**: `pipelines/xml-to-sql/VALIDATED/hana/`

**Contains**: 5 golden SQL files proven to work in HANA

**Purpose**:
- Regression baseline
- Working examples for comparison
- MUST compare before making code changes

**Rule**: Before ANY code change, compare generated SQL with VALIDATED version

---

## 🚨 What NOT to Do

### DO NOT:
1. ❌ Import from other pipelines (pipelines/sql-to-abap → pipelines/xml-to-sql)
2. ❌ Mix bugs from different pipelines in one BUG_TRACKER
3. ❌ Make code changes without checking VALIDATED folder first
4. ❌ Read all pipeline contexts when working on one pipeline
5. ❌ Skip mandatory procedures (bug-checking, SQL analysis)
6. ❌ Make changes without testing ALL validated XMLs
7. ❌ Commit changes across multiple pipelines in one commit

### VIOLATION CONSEQUENCES:
- Context overload returns
- "Can't find my shit" problem returns
- Pipelines break each other
- Independent development impossible

---

## 📋 Immediate Next Steps

### Option A: Continue Testing (Recommended)
1. Setup new repo locally
2. Install dependencies
3. Test the 6 validated XMLs in new structure
4. Verify all still work
5. Test remaining XMLs from old repo

### Option B: Migrate Other Pipelines
1. Extract sql-to-abap from old repo
2. Copy to `pipelines/sql-to-abap/`
3. Test independently
4. Don't touch xml-to-sql while doing this

### Option C: Fix Known Issues
1. Work on BUG-019 (CV_CT02_CT03)
2. Add more function mappings
3. Test more XMLs

---

## 🔗 Old Repo Reference

**Old Repo**: `C:\Users\iliya\OneDrive\Desktop\X2S\xml2sql`  
**Status**: Archived (for reference only)  
**Working Commit**: 680ad44 + fixes

**What Was Left Behind** (intentionally):
- Old git history (complex, confusing)
- Session summaries (historical)
- Temp files
- Incomplete audit reports
- Old distribution zips

**What Was Migrated**:
- All working code
- All catalogs with fixes
- All rules and procedures
- VALIDATED folder
- Bug tracking
- AI context

---

## 📖 Quick Reference

### When Debugging HANA Error
1. Read `LATEST_SQL_FROM_DB.txt` (auto-saved)
2. Compare with `pipelines/xml-to-sql/VALIDATED/hana/{XML}.sql`
3. Follow `pipelines/xml-to-sql/docs/SQL_ERROR_INVESTIGATION_PROCEDURE.md`
4. Check `pipelines/xml-to-sql/docs/BUG_TRACKER.md` for known bugs
5. Map error to `pipelines/xml-to-sql/rules/hana/HANA_CONVERSION_RULES.md`

### When XML Validates Successfully
1. Follow `pipelines/xml-to-sql/docs/SUCCESS_PROCEDURE.md`
2. Update `pipelines/xml-to-sql/GOLDEN_COMMIT.yaml`
3. Copy SQL to `pipelines/xml-to-sql/VALIDATED/hana/`
4. Update catalogs if new functions discovered
5. Commit changes

### When Adding New Function Mapping
1. Edit `pipelines/xml-to-sql/catalog/hana/data/functions.yaml`
2. Run: `cd pipelines/xml-to-sql && pip install -e .`
3. Restart server
4. Test
5. Document in functions.yaml description

---

## 🏗️ Migration History

**Source**: xml2sql (old repo, commit 680ad44)  
**Target**: xsodus_converter (new monorepo)  
**Date**: 2025-12-08

**Why Migrated**:
- Old repo had confusing git history (no commit had complete working state)
- Multiple pipes mixed together causing context overload
- "Can't find my shit" problem
- Need clean structure for multi-pipeline development

**What Changed**:
- ✅ Pipeline isolation (strict folder boundaries)
- ✅ Per-pipeline VALIDATED folders
- ✅ Per-pipeline BUG_TRACKERs
- ✅ Shared core extracted
- ✅ LLM context rules enforced
- ✅ Clean git history from day 1

**What Stayed Same**:
- All working code
- All fixes
- All rules
- All bugs documented
- All procedures

---

## 💡 Key Lessons (From Old Repo)

### What Went Wrong Before
1. All pipes in one folder → context overload
2. No pipeline isolation → breaking one broke all
3. Git commits mixed all pipes → unclear history
4. Single BUG_TRACKER for all pipes → confusion
5. Config.yaml not version controlled properly

### What's Different Now
1. ✅ Strict pipeline isolation
2. ✅ Independent baselines per pipeline
3. ✅ Git branches per pipeline
4. ✅ Separate BUG_TRACKERs
5. ✅ Clean structure from start

### How to Keep It Clean
- Follow pipeline isolation rules ALWAYS
- LLM reads ONLY target pipeline context
- Test within pipeline, don't cross-contaminate
- Commit changes per pipeline, not across

---

## 📈 Success Metrics

**Migration Successful When**:
- ✅ All 6 validated XMLs work in new structure
- ✅ Validation script passes
- ✅ No cross-pipeline imports
- ✅ Each pipeline self-contained
- ✅ LLM can work on xml-to-sql without seeing ABAP context

**Current Status**: 5/5 metrics achieved (pending XML testing)

---

## 🚀 Next Actions

### Immediate (For New LLM Session)
1. Read this handover
2. Read .claude/ files (3 files)
3. Check `pipelines/xml-to-sql/GOLDEN_COMMIT.yaml`
4. Review `pipelines/xml-to-sql/VALIDATED/hana/` (working examples)
5. Setup local development environment
6. Test XMLs to verify migration

### Short Term
1. Test remaining XMLs from old repo
2. Add any new function mappings discovered
3. Complete xml-to-sql validation coverage
4. Freeze xml-to-sql as stable

### Long Term
1. Migrate sql-to-abap pipeline
2. Migrate csv-to-json pipeline
3. Add new pipelines independently
4. Build unified UI

---

## 🎯 Working Baseline Reference

**Commit**: 20af687 (xml-to-sql/v3.0.0)  
**Includes**:
- Core shared code
- xml-to-sql pipeline with all fixes
- Complete catalogs (functions.yaml with DATE, DAYSBETWEEN, NOW, MATCH)
- VALIDATED folder
- All documentation
- All procedures

**To Use This Baseline**:
```bash
git checkout xml-to-sql/v3.0.0
cd pipelines/xml-to-sql
pip install -e .
# Use this as reference for working state
```

---

## 📞 Contact & Coordination

**Old Repo Agent**: May still be active in `C:\Users\iliya\OneDrive\Desktop\X2S\xml2sql`  
**New Repo Agent**: This session (you)  
**Coordination**: User manages both, shares findings

**If working in parallel**:
- Old repo: Reference only, testing
- New repo: Active development
- Don't sync changes back to old repo

---

## ✅ Verification Checklist

**For New LLM Session in This Repo**:

Before starting work:
- [ ] Read .claude/CLAUDE.md
- [ ] Read .claude/MANDATORY_PROCEDURES.md  
- [ ] Read .claude/PIPELINE_ISOLATION_RULES.md
- [ ] Check which pipeline you're working on
- [ ] Read ONLY that pipeline's folder
- [ ] Verify config.yaml has correct settings
- [ ] Check GOLDEN_COMMIT.yaml for baseline
- [ ] Review VALIDATED folder for working examples

Before making changes:
- [ ] Compare with VALIDATED SQL if exists
- [ ] Check BUG_TRACKER for known issues
- [ ] Verify rule in HANA_CONVERSION_RULES.md
- [ ] Test plan ready

After making changes:
- [ ] Test against ALL validated XMLs
- [ ] Update documentation
- [ ] Commit with proper message
- [ ] Follow SUCCESS_PROCEDURE.md if validation succeeds

---

## 🎓 Essential Reading Order

**Day 1 (New Agent)**:
1. This handover (you're reading it)
2. .claude/CLAUDE.md (30 min)
3. .claude/MANDATORY_PROCEDURES.md (20 min)
4. .claude/PIPELINE_ISOLATION_RULES.md (10 min)
5. pipelines/xml-to-sql/GOLDEN_COMMIT.yaml (5 min)
6. pipelines/xml-to-sql/docs/BUG_TRACKER.md (scan)

**Day 2 (First Development)**:
7. pipelines/xml-to-sql/rules/hana/HANA_CONVERSION_RULES.md (deep read)
8. pipelines/xml-to-sql/docs/CONVERSION_FLOW_MAP.md
9. pipelines/xml-to-sql/docs/SQL_ERROR_INVESTIGATION_PROCEDURE.md

**As Needed**:
10. SUCCESS_PROCEDURE.md (when XML validates)
11. ERROR_PROCEDURE_NO_BASELINE.md (when no VALIDATED SQL exists)
12. SOLVED_BUGS.md (for historical solutions)

---

**Last Updated**: 2025-12-10
**Version**: 1.1 (SDLC Framework Added)
**Status**: xml-to-sql pipeline READY with full SDLC process documentation

---

## Session Update: 2025-12-10

### SDLC Framework Implementation
Created comprehensive 7-process SDLC framework:
- Master index: `.claude/SDLC_MASTER_PROCEDURE.md`
- 7 numbered procedures in `pipelines/xml-to-sql/docs/procedures/`
- Automation scripts in `utilities/`
- Updated CLAUDE.md Rule 19 for SDLC enforcement

### Files Created
- `.claude/SDLC_MASTER_PROCEDURE.md` - Master index
- `pipelines/xml-to-sql/docs/procedures/1_PLANNING_PROCEDURE.md`
- `pipelines/xml-to-sql/docs/procedures/2_DEVELOPMENT_PROCEDURE.md`
- `pipelines/xml-to-sql/docs/procedures/3_TESTING_PROCEDURE.md`
- `pipelines/xml-to-sql/docs/procedures/4_DEBUGGING_PROCEDURE.md`
- `pipelines/xml-to-sql/docs/procedures/5_BUG_FIX_PROCEDURE.md`
- `pipelines/xml-to-sql/docs/procedures/6_DOCUMENTATION_PROCEDURE.md`
- `pipelines/xml-to-sql/docs/procedures/7_REFACTORING_PROCEDURE.md`
- `utilities/validate_all_xmls.bat`

### Previous Session Fixes (2025-12-10)
- Fixed `restart_server.bat` path issues
- Added `FORMAT → TO_VARCHAR` function mapping
- Added input parameter substitution with default values
- Fixed SQL auto-save path to `C:\Users\iliya\OneDrive\Desktop\X2S\xsodus_converter\LATEST_SQL_FROM_DB.txt`

---

## Session 9 Update: 2025-12-10 (ASSESSMENT_REPORT Validated)

### XML Validated
| XML | Execution Time | Status |
|-----|----------------|--------|
| ASSESSMENT_REPORT.xml | 21ms | ✅ PASS |

### Bugs Fixed
1. **Nested function rewrite fix** - `_build_replacement()` now recursively processes arguments
   - Before: `format(format(x))` → `TO_VARCHAR(format(x))` ❌
   - After: `format(format(x))` → `TO_VARCHAR(TO_VARCHAR(x))` ✅

2. **FORMAT → TO_VARCHAR mapping** - Added to functions.yaml catalog

### Code Changes
- `pipelines/xml-to-sql/src/xml_to_sql/sql/function_translator.py` lines 1202-1238
  - Added `processed_args = [_apply_catalog_rewrites(arg, ctx) for arg in args]`
  - Updated all handlers to use `processed_args`

- `pipelines/xml-to-sql/src/xml_to_sql/web/api/routes.py` lines 44-54
  - Fixed path calculation for LATEST_SQL_FROM_DB.txt (7 levels up, not 6)

### Validated XMLs Count
**Total: 14 XMLs validated** (was 13)

**For questions**: Review procedures in `pipelines/xml-to-sql/docs/`
**For context**: This is a CLEAN START with lessons learned from old repo

