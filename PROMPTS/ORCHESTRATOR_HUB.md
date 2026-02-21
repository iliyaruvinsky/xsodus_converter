# ORCHESTRATOR HUB - BEx-to-CV & CV-to-CDS Pipelines

**Last Updated:** 2026-02-01 15:00
**Updated By:** Orc (Orchestrator)
**Sprint:** Sprint 1 - CV Renderer Fix & Parser Enhancement
**Status:** ACTIVE

---

## SYSTEM SECTION (Static)

### Project Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    xsodus_converter - New Pipelines                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Pipeline 1: BEx-to-CV          Pipeline 2: CV-to-CDS                   │
│  ┌──────────────────────┐       ┌──────────────────────┐                │
│  │ BEx XML (SAP BW)     │       │ CV XML (HANA)        │                │
│  │        ↓             │       │        ↓             │                │
│  │ bex_parser.py        │       │ cv_parser.py         │                │
│  │        ↓             │       │        ↓             │                │
│  │ BExQuery IR          │       │ CDSView IR           │                │
│  │        ↓             │       │        ↓             │                │
│  │ cv_renderer.py       │       │ cds_renderer.py      │                │
│  │        ↓             │       │        ↓             │                │
│  │ CV XML (HANA 2.3)    │       │ ABAP CDS / CAP CDS   │                │
│  └──────────────────────┘       └──────────────────────┘                │
│                                                                          │
│  Frontend: React UI for both pipelines (ui/frontend/)                   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Agent Roster

| Agent | Name | Role | Territory |
|-------|------|------|-----------|
| 🎯 | **Orc** | Orchestrator | System management, coordination, validation |
| 🎨 | **Sally** | Frontend | `ui/frontend/*`, web components, UX |
| ⚙️ | **Winston** | Backend | Parsers, renderers, catalogs, domain models |

### File Ownership Matrix

| Path | Owner | Shared? |
|------|-------|---------|
| `pipelines/bex-to-cv/src/bex_to_cv/parser/` | Winston | No |
| `pipelines/bex-to-cv/src/bex_to_cv/renderer/` | Winston | No |
| `pipelines/bex-to-cv/src/bex_to_cv/domain/` | Winston | No |
| `pipelines/bex-to-cv/src/bex_to_cv/catalog/` | Winston | No |
| `pipelines/cv-to-cds/src/cv_to_cds/*` | Winston | No |
| `pipelines/*/web/api/` | Winston | Coordinate |
| `ui/frontend/*` | Sally | No |
| `pipelines/*/docs/` | Both | Coordinate |
| `PROMPTS/*` | Orc | No |
| `docs/llm_handover.md` | Orc | No |

### Coordination Protocol

```
┌─────────────────────────────────────────────────────────────────────────┐
│  COMMUNICATION FLOW                                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│     ┌─────────┐                                                          │
│     │   Orc   │  ← Updates all 3 prompt files                           │
│     │ (Hub)   │  ← Manages stage gates                                  │
│     └────┬────┘  ← Coordinates blockers                                 │
│          │                                                               │
│     ┌────┴────┐                                                          │
│     ▼         ▼                                                          │
│ ┌───────┐ ┌───────┐                                                      │
│ │Winston│ │ Sally │                                                      │
│ │(Back) │ │(Front)│                                                      │
│ └───┬───┘ └───┬───┘                                                      │
│     │         │                                                          │
│     └────┬────┘                                                          │
│          ▼                                                               │
│   ORCHESTRATOR_HUB.md  ← Both agents write status here                  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Stage Gates Reference

| Gate | Name | Owner | Entry Criteria |
|------|------|-------|----------------|
| G0 | Prerequisites | Orc | Sample BEx XML available, reference CV format verified |
| G1 | Parser Complete | Winston | BEx parser handles all G_T_* sections |
| G2 | CV Renderer Complete | Winston | CV XML matches schemaVersion 2.3 |
| G3 | CV Activation | Orc | CV activates in HANA Studio |
| G4 | CV-to-CDS Parser | Winston | CV parser reads schemaVersion 2.3 |
| G5 | CDS Renderer Complete | Winston | ABAP/CAP CDS syntax correct |
| G6 | End-to-End | Orc | Full chain BEx → CV → CDS works |
| G7 | UI Integration | Sally | Web UI operational |

---

## SPECIFIC SECTION (Dynamic - Per Sprint)

### Current Sprint: Sprint 1 - Foundation Fixes

**Sprint Goal:** Fix CV renderer to output correct schemaVersion 2.3 format

**Duration:** 2026-02-01 to 2026-02-07

---

### Phase Status

| Phase | Description | Status | Owner |
|-------|-------------|--------|-------|
| Phase 1 | Foundation (folders, pyproject.toml) | ✅ COMPLETE | - |
| Phase 2 | BEx Parser & Renderer | 🔄 NEEDS UPDATES | Winston |
| Phase 3 | CV Validation & Enhancement | 📋 PENDING | Winston + Orc |
| Phase 4 | CV-to-CDS Parser | 📋 PENDING | Winston |
| Phase 5 | CDS Renderers | 📋 PENDING | Winston |
| Phase 6 | Web API & CLI | 📋 PENDING | Winston + Sally |
| Phase 7 | Documentation & Golden Commit | 📋 PENDING | Orc |

---

### Current Blockers

| Blocker ID | Description | Blocks | Owner | Status |
|------------|-------------|--------|-------|--------|
| BLOCK-001 | cv_renderer.py uses wrong XML format | G2, G3, all frontend | Winston | 🔴 ACTIVE |
| BLOCK-002 | LOWFLAG=3 variable resolution missing | G1 completion | Winston | 🔴 ACTIVE |

---

### Cross-Agent Dependencies

```
┌─────────────────────────────────────────────────────────────────────────┐
│  DEPENDENCY CHAIN - Sprint 1                                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  BE-CV-001 (Winston)                                                     │
│      │                                                                   │
│      ├──► BE-CV-002 (Winston) ──► G2 (Orc validates)                    │
│      │                                   │                               │
│      │                                   ▼                               │
│      │                            G3 (HANA activation)                   │
│      │                                   │                               │
│      │                                   ▼                               │
│      └────────────────────────► FE-BEX-001 (Sally) - BLOCKED            │
│                                                                          │
│  Legend:                                                                 │
│  BE-* = Backend tasks                                                    │
│  FE-* = Frontend tasks                                                   │
│  G* = Stage Gates                                                        │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### Task Summary (All Agents)

#### Priority 0 - Critical Path (This Sprint)

| Task ID | Description | Owner | Status | Blocks |
|---------|-------------|-------|--------|--------|
| BE-CV-001 | Fix cv_renderer.py schemaVersion 2.3 format | Winston | 🔴 TODO | BE-CV-002, G2 |
| BE-CV-002 | Add AccessControl namespace for filters | Winston | 🔴 TODO | G2 |
| BE-PARSE-001 | Add LOWFLAG=3 variable reference resolution | Winston | 🔴 TODO | G1 |
| BE-REPORT-001 | Add conversion report generation | Winston | 🔴 TODO | G2 |

#### Priority 1 - After P0

| Task ID | Description | Owner | Status | Depends On |
|---------|-------------|-------|--------|------------|
| G2-VALIDATE | Validate CV XML structure | Orc | 📋 PLANNED | BE-CV-001, BE-CV-002 |
| G3-ACTIVATE | Test CV activation in HANA Studio | Orc | 📋 PLANNED | G2-VALIDATE |
| FE-BEX-001 | Build BEx-to-CV upload UI | Sally | ⏸️ BLOCKED | G3-ACTIVATE |
| FE-BEX-002 | Build conversion report display | Sally | ⏸️ BLOCKED | BE-REPORT-001 |

#### Priority 2 - Phase 4+

| Task ID | Description | Owner | Status | Depends On |
|---------|-------------|-------|--------|------------|
| BE-CDS-001 | Create cv_parser.py for CV → CDS | Winston | 📋 PLANNED | G3 |
| BE-CDS-002 | Create ABAP CDS renderer | Winston | 📋 PLANNED | BE-CDS-001 |
| BE-CDS-003 | Create CAP CDS renderer | Winston | 📋 PLANNED | BE-CDS-001 |
| FE-CDS-001 | Build CV-to-CDS upload UI | Sally | 📋 PLANNED | BE-CDS-002 |

---

### Messages to Agents

#### To Winston (Backend):

```
[2026-02-01 15:00] ORC:
PRIORITY: Complete BE-CV-001, BE-CV-002, BE-PARSE-001 in that order
CRITICAL: cv_renderer.py is generating WRONG XML format
REFERENCE: See vivid-sparking-floyd.md Section 1.1 for correct format
LOCATION: pipelines/bex-to-cv/src/bex_to_cv/renderer/cv_renderer.py
ALSO: Source (ABAP Programs)/DATA_SOURCE/DATA_SOURCES.calculationview has reference format
BLOCKING: Sally cannot start UI until G3 passes
```

#### To Sally (Frontend):

```
[2026-02-01 15:00] ORC:
STATUS: You are BLOCKED until G3 (CV Activation) passes
ACTION: Wait for Winston to complete BE-CV-001, BE-CV-002
PREPARE: Review ui/frontend/ structure, plan component architecture
READ: vivid-sparking-floyd.md for conversion report format (Section 10)
NEXT TASK: FE-BEX-001 (Build BEx-to-CV upload UI) after G3
```

---

### Stage Gate Status

| Gate | Status | Last Checked | Notes |
|------|--------|--------------|-------|
| G0 | ✅ PASS | 2026-02-01 | Sample BEx XML exists, reference CV format documented |
| G1 | 🔄 PARTIAL | 2026-02-01 | Parser works but missing LOWFLAG=3 resolution |
| G2 | 🔴 BLOCKED | - | Waiting on BE-CV-001, BE-CV-002 |
| G3 | 🔴 BLOCKED | - | Waiting on G2 |
| G4 | 🔴 BLOCKED | - | Waiting on G3 |
| G5 | 🔴 BLOCKED | - | Waiting on G4 |
| G6 | 🔴 BLOCKED | - | Waiting on G5 |
| G7 | 🔴 BLOCKED | - | Waiting on G6 |

---

### Key Decisions (FROZEN - Do Not Re-Decide)

| Decision | Answer | Reference |
|----------|--------|-----------|
| CV Schema Version | `schemaVersion="2.3"` | Plan Decision 3 |
| CV Namespace | `Calculation:scenario` | Plan Decision 3 |
| MVP Variable Types | VARTYP=1 only | Plan Decision 4 |
| MVP Key Figures | KYF only (CKF/RKF = STUB) | Plan Decision 6 |
| CDS Strategy | Wrapper (consume CV) | Plan Decision 7 |
| Validation Environment | HANA Studio, ADT, cds compile | Plan Decision 10 |

---

### Agent Status Updates

#### Winston (Backend) Updates:

```
[DATE] Winston:
(Write status updates here)
```

#### Sally (Frontend) Updates:

```
[DATE] Sally:
(Write status updates here)
```

#### Orc (Orchestrator) Updates:

```
[2026-02-01 15:00] Orc:
- Created 3-agent prompt system
- Initialized Sprint 1: Foundation Fixes
- Identified BLOCK-001 and BLOCK-002 as critical path blockers
- Sally is BLOCKED until G3 passes
```

---

### Reference Documents

| Document | Path | Purpose |
|----------|------|---------|
| Implementation Plan | `C:\Users\iliya\.claude\plans\vivid-sparking-floyd.md` | Master plan with all decisions |
| Reference CV | `Source (ABAP Programs)/DATA_SOURCE/DATA_SOURCES.calculationview` | Correct XML format |
| Sample BEx XML | `Source (XML Files)/BW_BEX_XML_VIEWS/00O2TN3NK6BZ1GA7XWO79QYF4.xml` | Input sample |
| BEx Bug Tracker | `pipelines/bex-to-cv/docs/BUG_TRACKER.md` | Pipeline-specific bugs |
| CDS Bug Tracker | `pipelines/cv-to-cds/docs/BUG_TRACKER.md` | Pipeline-specific bugs |
| LLM Handover | `docs/llm_handover.md` | Session continuity |

---

*This file is the central coordination point. All agents MUST read this before starting work.*
*Updated by Orc (Orchestrator). Last sync: 2026-02-01 15:00*
