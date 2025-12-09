# Pipeline Isolation Rules for LLM Development

**Purpose**: Ensure LLM reads ONLY relevant context when working on specific pipeline  
**Critical**: Prevents context overload and "can't find my shit" problem

---

## MANDATORY RULE: Pipeline-Scoped Context

**When working on a specific pipeline, LLM MUST:**

### ✅ READ ONLY:
```
pipelines/{target-pipeline}/**     # Target pipeline folder
core/**                             # Shared foundation  
.claude/**                          # AI rules and procedures
docs/ARCHITECTURE.md                # Structure reference only
README.md                           # Project overview only
```

### ❌ IGNORE:
```
pipelines/{other-pipelines}/**      # All other pipeline folders
docs/pipes/                         # Other pipeline docs
```

---

## Pipeline Identification

**Before starting ANY task, identify target pipeline:**

### XML to SQL Work
- **Pipeline**: `pipelines/xml-to-sql/`
- **Read**: xml-to-sql/rules/, xml-to-sql/docs/BUG_TRACKER.md
- **Ignore**: sql-to-abap/, csv-to-json/

### SQL to ABAP Work  
- **Pipeline**: `pipelines/sql-to-abap/`
- **Read**: sql-to-abap/rules/, sql-to-abap/docs/
- **Ignore**: xml-to-sql/, csv-to-json/

### CSV to JSON Work
- **Pipeline**: `pipelines/csv-to-json/`
- **Read**: csv-to-json/schemas/, csv-to-json/docs/
- **Ignore**: xml-to-sql/, sql-to-abap/

---

## Verification Questions

**Before answering ANY question, verify:**

1. ✅ Am I reading the correct pipeline folder?
2. ✅ Am I referencing the correct BUG_TRACKER.md?
3. ✅ Am I using the correct GOLDEN_COMMIT.yaml?
4. ✅ Am I looking at the correct rules file?
5. ✅ Am I checking the correct VALIDATED folder?

**Example Verification:**
```
User asks: "What's in BUG_TRACKER?"
LLM checks: Which pipeline are we working on?
- If xml-to-sql → Read pipelines/xml-to-sql/docs/BUG_TRACKER.md
- If sql-to-abap → Read pipelines/sql-to-abap/docs/BUG_TRACKER.md
NOT: Read both or root-level BUG_TRACKER
```

---

## File Location Rules

### Per-Pipeline Files (Read from target pipeline ONLY)

**Each pipeline has its own:**
- `rules/` - Conversion rules (e.g., hana/, snowflake/ subdirs)
- `catalog/` - Function/pattern catalogs per target
- `docs/BUG_TRACKER.md` - ONLY bugs for this pipeline
- `docs/SOLVED_BUGS.md` - ONLY solutions for this pipeline
- `VALIDATED/` - Golden SQL/output files for this pipeline
- `GOLDEN_COMMIT.yaml` - This pipeline's baseline tracking
- `tests/` - Tests for this pipeline only
- `config.yaml` - Pipeline-specific configuration

### Shared Files (Always accessible)
- `core/` - Parser, IR models, database utilities
- `.claude/CLAUDE.md` - Behavior rules
- `.claude/MANDATORY_PROCEDURES.md` - Investigation procedures
- `.claude/PIPELINE_ISOLATION_RULES.md` - This document

### Project Files (Reference only)
- `docs/ARCHITECTURE.md` - Structure explanation
- `README.md` - Project overview
- `docs/README.md` - Documentation index

---

## Code Import Rules

**Pipeline code MUST NOT import from other pipelines:**

**✅ ALLOWED:**
```python
# In pipelines/xml-to-sql/src/renderer.py
from x2s_core.models import Scenario, Node      # Core imports ✅
from x2s_core.parser import parse_scenario      # Core imports ✅
from .translator import translate_function      # Same pipeline ✅
```

**❌ FORBIDDEN:**
```python
# In pipelines/xml-to-sql/src/renderer.py
from pipelines.sql_to_abap import generate_abap  # Cross-pipeline ❌
```

**Validation**: `scripts/validate_structure.py` enforces this

---

## Git Workflow Rules

### Branch Naming
```
pipelines/{pipeline-name}/feature-{name}
pipelines/{pipeline-name}/bugfix-{number}
pipelines/{pipeline-name}/dev
```

**Examples:**
- `pipelines/xml-to-sql/feature-add-oracle`
- `pipelines/sql-to-abap/bugfix-046`
- `pipelines/csv-to-json/dev`

### Commit Scope
**Commits SHOULD change files in ONE pipeline only**

**Example - Good:**
```bash
git commit -m "xml-to-sql: Add DATE function mapping"
# Changes only in pipelines/xml-to-sql/
```

**Example - Bad:**
```bash
git commit -m "Fix bugs in multiple pipelines"
# Changes in xml-to-sql/, sql-to-abap/, csv-to-json/ ❌
```

### Git Tags
```
{pipeline-name}/v{version}
```

**Examples:**
- `xml-to-sql/v3.0.0`
- `sql-to-abap/v1.0.0`
- `csv-to-json/v2.0.0`

---

## Documentation Rules

### Per-Pipeline Documentation

**Each pipeline maintains:**
- Own BUG_TRACKER.md (ONLY bugs for that pipeline)
- Own GOLDEN_COMMIT.yaml (baseline for that pipeline)
- Own rules documentation
- Own testing guides

**DO NOT:**
- Mix bugs from different pipelines in one tracker
- Reference other pipeline bugs
- Assume rules apply across pipelines

### Shared Documentation

**Project-wide docs (in root docs/):**
- Architecture overview
- Contributing guidelines
- Getting started
- NOT: Pipeline-specific rules or bugs

---

## Testing Rules

**Test ONLY target pipeline:**

```bash
# Test xml-to-sql
pytest pipelines/xml-to-sql/tests/

# Test sql-to-abap
pytest pipelines/sql-to-abap/tests/

# NOT: pytest (runs all pipelines)
```

**Regression testing:**
- Each pipeline has own VALIDATED folder
- Compare ONLY within that pipeline
- Don't cross-check with other pipelines

---

## LLM Memory Rules

**When creating memories about bugs/fixes:**

**✅ CORRECT:**
- "xml-to-sql: BUG-046 in pipelines/xml-to-sql/docs/BUG_TRACKER.md"
- "sql-to-abap: ABAP syntax rules in pipelines/sql-to-abap/rules/"

**❌ WRONG:**
- "BUG-046 in BUG_TRACKER.md" (which one?)
- "Check the rules" (which pipeline's rules?)

---

## ENFORCEMENT

**Automated validation** (`scripts/validate_structure.py`):
- Checks no cross-pipeline imports (except core)
- Verifies folder structure integrity
- Validates each pipeline is self-contained

**Pre-commit hook**:
- Runs validation before allowing commit
- Blocks commits violating isolation

**Manual verification**:
- Can delete any pipeline folder without breaking others
- LLM working on one pipeline never mentions other pipelines

---

## VIOLATION CONSEQUENCES

**If pipeline isolation is broken:**
- ❌ Context overload returns
- ❌ "Can't find my shit" problem returns
- ❌ Bugs mix between pipelines
- ❌ Git history becomes confusing
- ❌ Independent development impossible

**THESE RULES EXIST because:**
- User paid for 2 weeks to build working system
- Context mixing destroyed it multiple times
- This structure prevents repeating that mistake

---

## SUCCESS CRITERIA

**Structure is correct if:**
- ✅ Can work on xml-to-sql without seeing ABAP docs
- ✅ Can delete sql-to-abap/ without breaking xml-to-sql
- ✅ Each pipeline has own baseline, bugs, rules
- ✅ LLM answers using ONLY target pipeline context
- ✅ Git log per pipeline is clean and focused

---

**Last Updated**: 2025-12-08  
**Status**: MANDATORY - Must be read before every LLM task  
**Enforcement**: Automated + manual verification

