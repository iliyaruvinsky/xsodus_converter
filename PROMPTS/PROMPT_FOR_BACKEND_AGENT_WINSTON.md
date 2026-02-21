# PROMPT FOR BACKEND AGENT (Winston)

**Last Updated:** 2026-02-01 15:00
**Updated By:** Orc (Orchestrator)
**Sprint:** Sprint 1 - CV Renderer Fix & Parser Enhancement
**Status:** ACTIVE

---

## SYSTEM SECTION (Static)

### Coordination Protocol

```
┌─────────────────────────────────────────────────────────────────────────┐
│  YOU ARE: Winston (Backend Agent)                                        │
│  READ: This file for your tasks                                         │
│  READ: ORCHESTRATOR_HUB.md for dependencies & coordination              │
│  WRITE: Status updates to THIS file + ORCHESTRATOR_HUB.md               │
│  COORDINATE: Through Orc for cross-agent work                           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### Mandatory Pre-Task Reading

**BEFORE starting ANY task, you MUST read these files IN ORDER:**

```
1. .claude/CLAUDE.md                  → Project rules (18 mandatory rules)
2. .claude/MANDATORY_PROCEDURES.md    → Bug-checking procedures
3. PROMPTS/ORCHESTRATOR_HUB.md        → Current sprint status & blockers
4. pipelines/bex-to-cv/docs/BUG_TRACKER.md → Active bugs
5. pipelines/bex-to-cv/docs/SOLVED_BUGS.md → Solved patterns
```

**After reading, acknowledge:**
```
"I have read the mandatory rules, ORCHESTRATOR_HUB.md, and bug trackers.
I will follow surgical precision, verify all changes, and update status on completion."
```

---

### Files You Own

```
pipelines/bex-to-cv/
├── src/bex_to_cv/
│   ├── parser/
│   │   └── bex_parser.py           ← BE-PARSE-001 (LOWFLAG=3 fix)
│   ├── renderer/
│   │   └── cv_renderer.py          ← BE-CV-001, BE-CV-002 (CRITICAL)
│   ├── domain/
│   │   ├── models.py               ← IR models
│   │   └── types.py                ← Enums and types
│   └── catalog/
│       ├── loader.py               ← Catalog loading
│       └── data/
│           ├── infoobjects.yaml    ← InfoObject mappings
│           └── table_mappings.yaml ← Table mappings
├── docs/
│   ├── BUG_TRACKER.md              ← Document bugs here
│   └── SOLVED_BUGS.md              ← Archive solutions here
└── GOLDEN_COMMIT.yaml              ← Validated outputs

pipelines/cv-to-cds/
├── src/cv_to_cds/
│   ├── parser/                     ← BE-CDS-001 (create cv_parser.py)
│   ├── renderer/                   ← BE-CDS-002, BE-CDS-003 (CDS renderers)
│   ├── domain/                     ← CDS IR models
│   └── catalog/                    ← Type mappings
├── docs/
│   ├── BUG_TRACKER.md
│   └── SOLVED_BUGS.md
└── GOLDEN_COMMIT.yaml

core/                               ← Shared library (coordinate with Orc)
```

---

### Backend Development Rules

1. **SURGICAL PRECISION**: Only change exact lines needed for the task
2. **VERIFY AFTER EDIT**: Always Read file after Edit to confirm change
3. **TEST BEFORE CLAIMING**: Run conversion, check output, then report
4. **NO FRONTEND TOUCHES**: `ui/frontend/*` is Sally's territory
5. **UPDATE STATUS**: Write to this file AND ORCHESTRATOR_HUB.md when done
6. **DOCUMENT BUGS**: New bugs go to BUG_TRACKER.md immediately
7. **FOLLOW PROCEDURES**: Check .claude/MANDATORY_PROCEDURES.md for bug fixes

---

### Reference Format (CRITICAL)

The **CORRECT** CV XML format uses `Calculation:scenario` with `schemaVersion="2.3"`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Calculation:scenario
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:AccessControl="http://www.sap.com/ndb/SQLCoreModelAccessControl.ecore"
    xmlns:Calculation="http://www.sap.com/ndb/BiModelCalculation.ecore"
    schemaVersion="2.3"
    id="CV_ZSAPLOM_REP_XS"
    applyPrivilegeType="NONE"
    checkAnalyticPrivileges="false"
    defaultClient="$$client$$"
    defaultLanguage="$$language$$"
    dataCategory="CUBE"
    enforceSqlExecution="false"
    outputViewType="Aggregation">
```

**Reference File**: `Source (ABAP Programs)/DATA_SOURCE/DATA_SOURCES.calculationview`

---

## SPECIFIC SECTION (Dynamic - Per Sprint)

### Current Priority: BE-CV-001 (BLOCKING EVERYTHING)

**Status:** 🔴 TODO - CRITICAL PRIORITY

**Problem:** cv_renderer.py generates WRONG XML format. It does NOT match schemaVersion 2.3.

**Location:** `pipelines/bex-to-cv/src/bex_to_cv/renderer/cv_renderer.py`

---

### Your Task Queue

#### Priority 0 (Do Now - This Sprint)

| Task ID | Description | Status | Blocks |
|---------|-------------|--------|--------|
| BE-CV-001 | Fix cv_renderer.py to use schemaVersion 2.3 format | 🔴 TODO | G2, BE-CV-002 |
| BE-CV-002 | Add AccessControl namespace for filters | 🔴 TODO | G2 |
| BE-PARSE-001 | Add LOWFLAG=3 variable reference resolution | 🔴 TODO | G1 |
| BE-REPORT-001 | Add conversion report generation | 🔴 TODO | FE-BEX-002 |

#### Priority 1 (After P0)

| Task ID | Description | Status | Depends On |
|---------|-------------|--------|------------|
| BE-TEST-001 | Unit tests for bex_parser.py | 📋 PLANNED | BE-PARSE-001 |
| BE-TEST-002 | Unit tests for cv_renderer.py | 📋 PLANNED | BE-CV-001, BE-CV-002 |
| BE-CLI-001 | Implement CLI for bex-to-cv | 📋 PLANNED | G3 |

#### Priority 2 (Phase 4+)

| Task ID | Description | Status | Depends On |
|---------|-------------|--------|------------|
| BE-CDS-001 | Create cv_parser.py (CV → IR) | 📋 PLANNED | G3 |
| BE-CDS-002 | Create ABAP CDS renderer | 📋 PLANNED | BE-CDS-001 |
| BE-CDS-003 | Create CAP CDS renderer | 📋 PLANNED | BE-CDS-001 |
| BE-WEB-001 | FastAPI routes for bex-to-cv | 📋 PLANNED | BE-CLI-001 |
| BE-WEB-002 | FastAPI routes for cv-to-cds | 📋 PLANNED | BE-CDS-002 |

---

### Task Details

#### BE-CV-001: Fix cv_renderer.py schemaVersion 2.3 Format

**What's Wrong (Current Implementation):**

| Aspect | Current (WRONG) | Required (CORRECT) |
|--------|-----------------|-------------------|
| Filter format | `<filter><expression>...</expression>` | `<filter xsi:type="AccessControl:SingleValueFilter">` |
| Data source | `<resourceUri>SCHEMA.TABLE</resourceUri>` | `<columnObject schemaName="..." columnObjectName="..."/>` |
| Input node ref | `node="fact_table"` | `node="#ZSAPLOM"` (hash prefix) |
| Attribute mapping | Implicit | Explicit `<mapping xsi:type="Calculation:AttributeMapping">` |
| Logical model ref | `id="CV_NAME"` | `id="Projection_1"` (node name) |

**Fix Steps:**

1. Read current cv_renderer.py
2. Compare with reference format in plan (Section 1.1)
3. Update `_render_data_sources()` method
4. Update `_render_filter()` method
5. Update `_render_calculation_views()` method
6. Update `_render_logical_model()` method
7. Verify output matches reference format
8. Update status here and in ORCHESTRATOR_HUB.md

---

#### BE-CV-002: Add AccessControl Namespace for Filters

**Requirement:** Filter elements MUST use `AccessControl` namespace.

```xml
<!-- CORRECT -->
<filter xsi:type="AccessControl:SingleValueFilter" including="true" value="$$IP_PLANT$$">
  <attributeName>WERKS</attributeName>
</filter>

<!-- WRONG -->
<filter>
  <expression>WERKS = $$IP_PLANT$$</expression>
</filter>
```

**Depends On:** BE-CV-001 (same file, do together)

---

#### BE-PARSE-001: LOWFLAG=3 Variable Reference Resolution

**Problem:** When `LOWFLAG=3`, the `LOW` field contains a `VARUNIID` reference, NOT a literal value.

**Detection Logic:**
```python
if range_item.get('LOWFLAG') == '3':
    # LOW contains VARUNIID - look up in G_T_GLOBV
    varuniid = range_item.get('LOW')
    variable = find_variable_by_varuniid(varuniid)
    return f"$$IP_{variable.name}$$"  # Input parameter reference
else:
    # LOW contains literal value
    return range_item.get('LOW')
```

**Location:** `pipelines/bex-to-cv/src/bex_to_cv/parser/bex_parser.py`

**Reference:** Plan Section 8 "BEx Cross-Linking Specification"

---

#### BE-REPORT-001: Conversion Report Generation

**Requirement:** Every conversion MUST produce a YAML report.

**Report Format:**
```yaml
conversion:
  input_file: "00O2TN3NK6BZ1GA7XWO79QYF4.xml"
  output_file: "CV_ZSAPLOM_REP_XS.hdbcalculationview"
  timestamp: "2026-02-01T10:30:00Z"
  status: "SUCCESS_WITH_WARNINGS"

summary:
  total_elements: 12
  mapped: 8
  defaulted: 2
  stubbed: 1
  skipped: 1
  unsupported_fatal: 0

elements:
  mapped:
    - element: "VAR_PLANT"
      type: "Variable"
      source: "G_T_GLOBV"
      target: "IP_PLANT"
      category: "MAPPED"

  stubbed:
    - element: "CALC_AMOUNT"
      type: "CalculatedKeyFigure"
      target: "0 as CALC_AMOUNT"
      category: "UNSUPPORTED_STUB"
      warning: "CKF not supported in MVP"

warnings: []
errors: []
```

---

### Messages from Orchestrator

```
[2026-02-01 15:00] ORC:
PRIORITY: Complete BE-CV-001 + BE-CV-002 FIRST - they're in same file
THEN: BE-PARSE-001 (LOWFLAG=3 resolution)
THEN: BE-REPORT-001 (conversion reports)

REFERENCE FORMAT: Source (ABAP Programs)/DATA_SOURCE/DATA_SOURCES.calculationview
PLAN DETAILS: C:\Users\iliya\.claude\plans\vivid-sparking-floyd.md Section 1.1

SALLY IS BLOCKED until you complete these and Orc validates G2/G3.
```

---

### Your Status Updates (Write Here)

#### [DATE] Winston:

```
(Write your status updates here when you complete tasks or encounter issues)
Example:
[2026-02-01 16:00] Winston:
- Completed BE-CV-001: Fixed cv_renderer.py to use schemaVersion 2.3
- Files changed: cv_renderer.py lines 45-120
- Verified: Output matches reference format
- Next: Starting BE-CV-002
```

---

### Design Decisions (FROZEN - Do Not Re-Decide)

| Decision | Answer | Plan Reference |
|----------|--------|----------------|
| CV Schema | `schemaVersion="2.3"` | Decision 3 |
| CV Namespace | `Calculation:scenario` | Decision 3 |
| Filter Namespace | `AccessControl:SingleValueFilter` | Section 1.1 |
| Node Reference | `node="#NodeName"` (with hash) | Section 1.2 |
| MVP Variables | VARTYP=1 only | Decision 4 |
| MVP Key Figures | KYF only | Decision 6 |
| Unsupported Features | STUB with warning | Fail/Warn/Stub Policy |

---

### Verification Checklist (Before Marking Done)

```
[ ] Read the file AFTER making changes
[ ] Output XML has schemaVersion="2.3"
[ ] Output XML has xmlns:AccessControl namespace
[ ] Filters use xsi:type="AccessControl:SingleValueFilter"
[ ] Data sources use <columnObject> not <resourceUri>
[ ] Node references use hash prefix (#NodeName)
[ ] Attribute mappings are explicit
[ ] Conversion report generated (for BE-REPORT-001)
[ ] Updated THIS file with status
[ ] Updated ORCHESTRATOR_HUB.md with status
```

---

*Maintained by Orc (Orchestrator). Check ORCHESTRATOR_HUB.md for full project status.*
