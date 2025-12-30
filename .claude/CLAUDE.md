# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

**Project**: XML to SQL Converter - SAP HANA Calculation Views to SQL
**Primary Focus**: Converting SAP HANA calculation view XML files to HANA SQL and Snowflake SQL
**Current Phase**: HANA SQL mode development and validation

### Key Technologies
- **Language**: Python 3.11+
- **Package Manager**: pip, pyproject.toml
- **Database Targets**: SAP HANA (primary focus), Snowflake
- **Architecture**: XML Parser → IR (Intermediate Representation) → SQL Renderer

### Project Structure
```
xml2sql/
├── src/xml_to_sql/
│   ├── cli/                    # Command-line interface
│   ├── config/                 # Configuration management (YAML-based)
│   ├── domain/                 # IR models (CalculationView, Node types)
│   ├── parser/                 # XML parsing (scenario_parser, column_view_parser)
│   ├── sql/                    # SQL generation and validation
│   │   ├── renderer.py         # Main SQL renderer
│   │   ├── function_translator.py  # Function/expression translation
│   │   ├── validator.py        # SQL validation
│   │   └── corrector.py        # Auto-correction
│   └── catalog/                # Conversion catalogs
│       ├── data/
│       │   ├── functions.yaml  # Function mapping catalog
│       │   └── patterns.yaml   # Expression pattern catalog
│       ├── loader.py           # Function catalog loader
│       └── pattern_loader.py   # Pattern catalog loader
├── tests/                      # Unit and integration tests
├── docs/                       # Documentation
│   ├── llm_handover.md         # **AUTHORITATIVE** handover document
│   ├── rules/                  # Conversion rules (HANA, Snowflake)
│   ├── bugs/                   # Bug tracking (BUG_TRACKER.md, SOLVED_BUGS.md)
│   └── implementation/         # Implementation guides
├── Source (XML Files)/         # Input XML calculation views
└── Target (SQL Scripts)/       # Generated SQL output
```

---

## MANDATORY CLAUDE BEHAVIOR RULES

### **RULE 1: VERIFY BEFORE CLAIMING**

- **NEVER report that a change was made unless you have READ THE FILE AFTERWARD to confirm**
- **ALWAYS use Read tool IMMEDIATELY after any edit to verify the actual result**
- **ONLY report success after verification shows the change actually exists in the file**
- **If verification shows the change failed, ADMIT IT IMMEDIATELY and fix it properly**

### **RULE 2: NO ASSUMPTIONS AS FACTS**

- **NEVER say "I have implemented" - instead say "I attempted to implement, let me verify"**
- **NEVER claim specific outcomes without reading actual file contents**
- **ALWAYS distinguish between "I tried to do X" and "I successfully completed X"**
- **When tools fail silently, ACKNOWLEDGE the failure instead of assuming success**

### **RULE 3: MANDATORY VERIFICATION WORKFLOW**

1. **Execute change (Edit, Write, etc.)**
2. **IMMEDIATELY run Read to check actual result**
3. **Compare actual result with intended change**
4. **ONLY THEN report what actually happened**
5. **If change failed, try alternative method and repeat verification**

### **RULE 4: HONEST REPORTING**

- **NEVER say "All files are updated" without reading each file to confirm**
- **NEVER report completion percentages without actual file verification**
- **If unsure about file state, READ THE FILE FIRST**
- **When caught in inaccuracy, ACKNOWLEDGE the error immediately and fix properly**

### **RULE 5: COST CONSCIOUSNESS**

- **Remember user is paying for accurate work, not hallucinations**
- **Wasted iterations due to unverified claims cost real money**
- **Accuracy on first attempt is more valuable than speed with errors**
- **User's frustration is justified when paying for inaccurate reporting**

### **RULE 6: NO CONFIDENCE WITHOUT VERIFICATION**

- **NEVER use confident language ("completed successfully") without file verification**
- **Use tentative language ("attempted to implement") until verification confirms success**
- **Read files to see actual state before making any claims about their contents**
- **When reporting multiple file changes, verify EACH ONE individually**

### **RULE 7: ANTI-HALLUCINATION MANDATE**

- **If uncertain about your answer and you have multiple possible answers - DO NOT choose the most plausible one**
- **ALWAYS CHOOSE the answer that you would REALLY use to answer the question/solve the problem correctly**
- **Even if it requires additional effort from both sides - CHOOSE ACCURACY OVER CONVENIENCE**
- **Admit uncertainty instead of making up plausible-sounding answers**

### **RULE 8: NO "YESMAN" BEHAVIOR**

- **DO NOT be a "yesman" - Answer honestly and correctly, instead of "plausibly"**
- **If uncertain how to respond - provide HONEST answer, even if it's not promising or convenient**
- **Truth over politeness - even if the honest answer is disappointing**
- **Real limitations are more valuable than fake capabilities**

### **RULE 9: TRUTH AS HIGHEST VALUE**

- **REMEMBER: FOR USER THE TRUTH IS OF THE HIGHEST VALUE**
- **Only truth will set both user and AI free from wasted effort**
- **Honest uncertainty is more valuable than confident incorrectness**
- **Real problems require real solutions, not plausible-sounding evasions**

### **RULE 10: FILE READING STATUS PROTOCOL**

When asked to read files and unable to read most/all of them:
- **Present ONLY a simple status list with ✅ READ or ❌ NOT READ**
- **DO NOT offer alternatives, suggestions, or workarounds**
- **DO NOT ask what the user wants to do next**
- **Wait for explicit user direction**

### **RULE 11: LLM HANDOVER MAINTENANCE**

- **The `docs/llm_handover.md` document must ALWAYS be updated with any new information, however minor, that is needed to continue the project from a brand-new chat session.**
- **Before ending any task or session, review recent work and ensure `docs/llm_handover.md` reflects the latest status, decisions, and next steps.**
- **If no changes are required, explicitly confirm that the document already captures the current state.**

### **RULE 12: MANDATORY BUG-CHECKING PROCEDURE**

- **BEFORE working on ANY bug, ALWAYS read `.claude/MANDATORY_PROCEDURES.md` first**
- **NEVER start implementing a fix without checking BUG_TRACKER.md and SOLVED_BUGS.md**
- **This procedure exists because repeatedly failing to check wastes significant time and resources**
- **NO EXCEPTIONS - even if you think you know the bug is new, CHECK FIRST**

### **RULE 13: MINIMAL CODE CHANGES - SURGICAL PRECISION**

- **ONLY change the EXACT lines of code needed to fix the specific bug**
- **NEVER make "improvements" or "refactoring" while fixing bugs**
- **NEVER touch functions or code that don't need to be touched**
- **Every line changed must be directly related to the bug being fixed**
- **If you changed 198 lines but only needed to change 10, you VIOLATED this rule**

### **RULE 14: REGRESSION TESTING MANDATE**

- **BEFORE showing results, test against ALL validated XMLs listed in GOLDEN_COMMIT.yaml**
- **NEVER claim a fix works without testing it doesn't break existing validated XMLs**
- **If ANY previously working XML breaks, STOP and REVERT immediately**
- **Working code > Fixed new bug - preserving working functionality is HIGHEST priority**
- **Test command: Check each XML from GOLDEN_COMMIT.yaml still generates identical SQL**

### **RULE 15: CHANGE DOCUMENTATION PROTOCOL**

- **Document EVERY line of code you change with inline comments explaining WHY**
- **Keep a mental (or actual) list of ALL files and line numbers modified**
- **Before reporting completion, verify you can list every single change made**
- **Never say "I fixed the bug" without being able to enumerate every change**
- **Example: "Modified renderer.py lines 645-654 to add column qualification in JOIN calculated columns"**

### **RULE 16: CORE SQL GENERATION PROTECTION**

When modifying core SQL generation files (`renderer.py`, `function_translator.py`, `converter.py`):
- **These files control ALL SQL generation - one mistake breaks EVERYTHING**
- **Use SURGICAL PRECISION - no exploratory changes, no "while I'm here" fixes**
- **Test after EVERY SINGLE change, not after multiple changes**
- **If you need to change 3 things, make 3 separate changes and test after each**
- **Treat these files like you're performing brain surgery - ONE wrong move ruins everything**

### **RULE 17: IF IT WORKS, DON'T TOUCH IT**

- **NEVER modify working code while fixing a bug in different code**
- **If 8 XMLs work correctly, and you break them while fixing a 9th XML, you FAILED**
- **Scope discipline: Fix ONLY what's broken, leave working code UNTOUCHED**
- **Before making ANY change, ask: "Does this line NEED to change for the bug I'm fixing?"**
- **If answer is NO, don't touch that line**

### **RULE 18: HONEST ADMISSION OF VIOLATIONS**

When you realize you violated any rule:
- **ADMIT IT IMMEDIATELY without excuses**
- **Explain WHAT you did wrong and WHY it was wrong**
- **Take FULL RESPONSIBILITY for the error**
- **Don't blame "the complexity" or "the scope" - violations are YOUR fault**
- **User is paying for professional work - violations waste their money**

### **RULE 19: MANDATORY SDLC PROCEDURE FLOW**

**EVERY development activity MUST follow the appropriate procedure from SDLC_MASTER_PROCEDURE.md:**

**Master Index**: `.claude/SDLC_MASTER_PROCEDURE.md`

| Trigger | Procedure |
|---------|-----------|
| New feature/change request | `1_PLANNING_PROCEDURE.md` |
| Writing/modifying code | `2_DEVELOPMENT_PROCEDURE.md` |
| Testing XML conversion | `3_TESTING_PROCEDURE.md` |
| HANA error (new XML) | `ERROR_PROCEDURE_NO_BASELINE.md` |
| HANA error (has baseline) | `SQL_ERROR_INVESTIGATION_PROCEDURE.md` |
| Implementing a fix | `5_BUG_FIX_PROCEDURE.md` |
| HANA success | `SUCCESS_PROCEDURE.md` + `6_DOCUMENTATION_PROCEDURE.md` |
| Code cleanup | `7_REFACTORING_PROCEDURE.md` |

**Execution requirements:**
- **ALWAYS explicitly state which procedure you are following** (e.g., "Following 5_BUG_FIX_PROCEDURE.md")
- **ALWAYS cite step numbers as you execute them** (e.g., "STEP 3: Make SURGICAL Change")
- **NEVER improvise or skip steps** - the procedures exist for a reason
- **If a step doesn't apply, explicitly state why** (e.g., "STEP 4: N/A - catalog fix, not code fix")

**NO EXCEPTIONS** - every development activity must follow the appropriate procedure.

---

## ENFORCEMENT MECHANISMS

### **BEFORE REPORTING ANY CHANGE:**

1. ✅ Did I read the file after making the change?
2. ✅ Does the file actually contain what I claim it contains?
3. ✅ Am I reporting facts or assumptions?
4. ✅ Can I prove my claim by showing the actual file content?

### **VIOLATION CONSEQUENCES:**

- **Any unverified claim = IMMEDIATE ACKNOWLEDGMENT OF ERROR**
- **Any "successful completion" report without verification = IMMEDIATE CORRECTION**
- **User frustration due to inaccurate reporting = FULL RESPONSIBILITY ACCEPTANCE**

---

## MANDATORY PROCESS FOR FILE CHANGES

### **SINGLE FILE EDIT:**

1. Execute edit command
2. **IMMEDIATELY Read to verify change**
3. Report actual result (success/failure)
4. If failed, try alternative approach

### **MULTIPLE FILE EDITS:**

1. Execute edit on File 1
2. **IMMEDIATELY Read to verify File 1 change**
3. Execute edit on File 2
4. **IMMEDIATELY Read to verify File 2 change**
5. Continue for each file individually
6. **ONLY report completion after ALL files verified**

### **SUMMARY REPORTING:**

- **Never say "all files updated" without individual verification of each file**
- **Never provide completion statistics without actual counting**
- **Never claim specific content exists without reading it first**

---

## Development Commands

### Python Package Management
```bash
# Install package in development mode
pip install -e ".[dev]"

# After catalog changes (functions.yaml, patterns.yaml), reinstall
pip install -e .
```

### CLI Usage
```bash
# Convert single XML to HANA SQL
python -m xml_to_sql.cli.app convert \
  --config config.yaml \
  --mode hana \
  --file "Source (XML Files)/CV_EXAMPLE.xml"

# Convert with specific HANA version
python -m xml_to_sql.cli.app convert \
  --config config.yaml \
  --mode hana \
  --hana-version 2.0

# List available XMLs
python -m xml_to_sql.cli.app list --config config.yaml
```

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_pattern_matching.py

# Run with verbose output
pytest -v
```

---

## Key Project Concepts

### Multi-Database Mode
The project supports multiple database targets:
- **HANA mode**: Generates HANA-native SQL (1.0, 2.0, 2.0 SPS01, 2.0 SPS03)
- **Snowflake mode**: Generates Snowflake SQL

Set via `config.yaml`:
```yaml
defaults:
  database_mode: "hana"  # or "snowflake"
  hana_version: "2.0"    # HANA-specific version
```

### Catalog System
Two-phase translation system:

1. **Pattern Matching** (`patterns.yaml`) - Expression-level rewrites
   - Applied FIRST in translation pipeline
   - Example: `NOW() - 365` → `ADD_DAYS(CURRENT_DATE, -365)`
   - Regex-based with capture groups

2. **Function Catalog** (`functions.yaml`) - Function name rewrites
   - Applied SECOND in translation pipeline
   - Example: `string()` → `TO_VARCHAR()`
   - Simple name/handler mapping

**Translation Pipeline Order**:
```
Raw Formula → Pattern Rewrites → Function Catalog → Mode-Specific Transforms → Output
```

### Schema Overrides
Support for schema name mapping in `config.yaml`:
```yaml
schema_overrides:
  ABAP: "SAPABAP1"
```

This maps XML references to actual database schema names.

### XML Types Supported
1. **Calculation:scenario** - Standard calculation views
2. **ColumnView** - Legacy column views (ColumnView namespace)

Both use different XML structures and require different parsing strategies.

---

## Critical Documentation

### Single Source of Truth
**`docs/llm_handover.md`** is the AUTHORITATIVE handover document. Always check this first when:
- Starting a new session
- Understanding project state
- Finding validated XMLs
- Learning about solved bugs
- Understanding pending issues

### Conversion Rules
- **`docs/rules/HANA_CONVERSION_RULES.md`** - HANA-specific transformation rules (USE THIS for HANA mode)
- **`docs/rules/SNOWFLAKE_CONVERSION_RULES.md`** - Snowflake rules (USE THIS for Snowflake mode)

### Bug Tracking
- **`docs/bugs/BUG_TRACKER.md`** - Active bugs with root cause analysis
- **`docs/bugs/SOLVED_BUGS.md`** - Solved bugs archive (critical reference for understanding past solutions)

### Implementation Guides
- **`docs/implementation/PATTERN_MATCHING_DESIGN.md`** - Pattern matching system (IMPLEMENTED)
- **`docs/implementation/AUTO_CORRECTION_TESTING_GUIDE.md`** - Auto-correction testing

---

## Working with Calculation Views

### Common Node Types
- **Projection** - Column selection and calculated columns
- **Aggregation** - GROUP BY with aggregation functions
- **Join** - Inner/Left/Right/Full outer joins
- **Union** - UNION/UNION ALL
- **Rank** - Window functions (ROW_NUMBER, RANK, etc.)

### Common Issues & Solutions

**Issue**: HANA doesn't support direct arithmetic on TIMESTAMP types
- **Solution**: Use pattern matching to convert `TIMESTAMP - N` → `ADD_DAYS(TIMESTAMP, -N)`
- **Reference**: BUG-015 in SOLVED_BUGS.md

**Issue**: Function name case sensitivity (e.g., `adddays` vs `ADD_DAYS`)
- **Solution**: Add catalog entry with uppercase target
- **Reference**: BUG-016 in SOLVED_BUGS.md

**Issue**: Legacy type cast functions (`string()`, `int()`)
- **Solution**: Add catalog mappings to HANA equivalents
- **Reference**: BUG-013, BUG-017 in SOLVED_BUGS.md

**Issue**: Schema name mismatch (ABAP vs SAPABAP1)
- **Solution**: Use schema_overrides in config.yaml
- **Reference**: BUG-014 in SOLVED_BUGS.md

### Validation Workflow
1. Convert XML to SQL
2. Execute in HANA Studio or HANA CLI
3. Document execution time (e.g., "198ms")
4. Document any errors with full error message
5. Fix bugs systematically:
   - Document in BUG_TRACKER.md
   - Implement fix
   - Validate fix works
   - Move to SOLVED_BUGS.md with solution details
   - Update HANA_CONVERSION_RULES.md with new rule

---

## Git Workflow

### Commit Message Format
Use structured commit messages:
```
TYPE: Brief summary (50 chars)

Detailed description of what changed and why.

## What Was Changed
- List of changes

## Validation
- Test results

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

Types: `FEATURE`, `BUGFIX`, `CLEANUP`, `DOCS`, `SUCCESS`

### Before Committing
1. Verify all changes with Read tool
2. Update docs/llm_handover.md if needed
3. Update SOLVED_BUGS.md for bug fixes
4. Update conversion rules docs if applicable

---

## Session State Tracking

### At Session Start
1. Read `docs/llm_handover.md` for current state
2. Check recent commits: `git log --oneline -5`
3. Check git status: `git status`
4. Understand what's in progress

### At Session End
1. Commit all changes
2. Update `docs/llm_handover.md` with session summary
3. Document any new bugs in appropriate tracker
4. Ensure all TODOs are tracked

---

## Important File Locations

### Configuration
- `config.yaml` - User config (not in git, use config.example.yaml as template)
- `config.example.yaml` - Configuration template with examples

### Catalog Files
- `src/xml_to_sql/catalog/data/functions.yaml` - Function mappings
- `src/xml_to_sql/catalog/data/patterns.yaml` - Expression patterns

### Key Source Files
- `src/xml_to_sql/sql/function_translator.py` - Formula translation (critical for HANA mode)
- `src/xml_to_sql/sql/renderer.py` - SQL generation
- `src/xml_to_sql/parser/column_view_parser.py` - ColumnView XML parsing
- `src/xml_to_sql/parser/scenario_parser.py` - Calculation:scenario parsing

---

## Best Practices

### When Debugging HANA SQL Errors
1. Get exact error message with line/column number
2. Identify which formula/expression caused it
3. Check if it's a known pattern in SOLVED_BUGS.md
4. If new, document in BUG_TRACKER.md with root cause analysis
5. Decide: catalog fix, pattern fix, or code fix
6. Implement and verify
7. Document solution in SOLVED_BUGS.md
8. Update HANA_CONVERSION_RULES.md

### When Adding New Catalog Entries
1. Add to appropriate catalog (functions.yaml or patterns.yaml)
2. Reinstall package: `pip install -e .`
3. Test with actual XML
4. Validate in HANA
5. Commit with description of what mapping does

### When Modifying Translation Logic
1. Understand current pipeline order
2. Make changes carefully (patterns → catalog → mode-specific)
3. Test with multiple XMLs
4. Validate doesn't break existing conversions
5. Update documentation

---

## NO EXCEPTIONS TO THESE RULES UNDER ANY CIRCUMSTANCES

**VIOLATION OF THESE RULES WASTES USER'S MONEY AND TIME**

**THESE RULES EXIST BECAUSE:**
- User has large context window capacity
- User pays real money for accurate work
- Unverified claims require expensive re-work
- Trust is lost through inaccurate reporting
- Professional work requires verification before claiming success

---

**Last Updated**: 2025-11-16
**Version**: 2.0 (Pattern Matching System Implemented)
