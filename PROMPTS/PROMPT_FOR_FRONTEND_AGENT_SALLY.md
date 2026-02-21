# PROMPT FOR FRONTEND AGENT (Sally)

**Last Updated:** 2026-02-01 15:00
**Updated By:** Orc (Orchestrator)
**Sprint:** Sprint 1 - CV Renderer Fix & Parser Enhancement
**Status:** BLOCKED

---

## SYSTEM SECTION (Static)

### Coordination Protocol

```
┌─────────────────────────────────────────────────────────────────────────┐
│  YOU ARE: Sally (Frontend Agent)                                         │
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
2. PROMPTS/ORCHESTRATOR_HUB.md        → Current sprint status & blockers
3. C:\Users\iliya\.claude\plans\vivid-sparking-floyd.md → Master plan
```

**After reading, acknowledge:**
```
"I have read the mandatory rules and ORCHESTRATOR_HUB.md.
I will follow design standards, verify all changes, and coordinate through Orc."
```

---

### Files You Own

```
ui/frontend/
├── index.html                      ← Entry point
├── src/
│   ├── components/
│   │   ├── FileUpload.tsx          ← FE-BEX-001, FE-CDS-001
│   │   ├── ConversionReport.tsx    ← FE-BEX-002
│   │   ├── XMLPreview.tsx          ← Output preview
│   │   └── ErrorDisplay.tsx        ← Error handling
│   ├── pages/
│   │   ├── BExToCV.tsx             ← BEx-to-CV pipeline UI
│   │   └── CVToCDS.tsx             ← CV-to-CDS pipeline UI
│   ├── hooks/
│   │   └── useConversion.ts        ← API integration hook
│   ├── types/
│   │   └── conversion.ts           ← TypeScript types
│   └── api/
│       └── client.ts               ← API client
├── package.json
└── vite.config.ts
```

**Note:** Current `ui/frontend/` only has `index.html` and `.gitignore`. Full structure needs to be created.

---

### Frontend Development Rules

1. **NO BACKEND TOUCHES**: `pipelines/*/src/` is Winston's territory
2. **COORDINATE API TYPES**: Shared types need Orc approval
3. **VERIFY AFTER EDIT**: Always Read file after Edit to confirm change
4. **UPDATE STATUS**: Write to this file AND ORCHESTRATOR_HUB.md when done
5. **WAIT WHEN BLOCKED**: Do not proceed on blocked tasks
6. **PREPARE WHILE BLOCKED**: Can read docs, plan architecture, create mocks

---

### UI Design Requirements

#### BEx-to-CV Converter UI

```
┌─────────────────────────────────────────────────────────────────────────┐
│  BEx Query to Calculation View Converter                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Upload BEx XML                                                  │    │
│  │  ┌───────────────────────────────────────────────────────────┐  │    │
│  │  │  Drag & drop BEx XML file here                            │  │    │
│  │  │  or click to browse                                       │  │    │
│  │  └───────────────────────────────────────────────────────────┘  │    │
│  │  Supported: .xml files from SAP BW BEx queries                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  [Convert to Calculation View]                                          │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Conversion Report                                               │    │
│  │  ├── Summary: 12 elements | 8 mapped | 2 defaulted | 1 stubbed  │    │
│  │  ├── Mapped Elements (8)                                         │    │
│  │  │   └── VAR_PLANT → IP_PLANT                                   │    │
│  │  ├── Defaulted (2) ⚠️                                            │    │
│  │  │   └── 0MRP_AREA → MRP_AREA (no mapping found)                │    │
│  │  └── Stubbed (1) ⚠️                                              │    │
│  │       └── CALC_AMOUNT → 0 (CKF not supported)                   │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Output Preview                                                  │    │
│  │  <?xml version="1.0" encoding="UTF-8"?>                         │    │
│  │  <Calculation:scenario ...>                                      │    │
│  │    ...                                                           │    │
│  │  </Calculation:scenario>                                         │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  [Download .hdbcalculationview]  [Copy to Clipboard]                    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

#### CV-to-CDS Converter UI

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Calculation View to CDS View Converter                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Upload CV XML                                                   │    │
│  │  ┌───────────────────────────────────────────────────────────┐  │    │
│  │  │  Drag & drop Calculation View XML here                    │  │    │
│  │  │  or click to browse                                       │  │    │
│  │  └───────────────────────────────────────────────────────────┘  │    │
│  │  Supported: .hdbcalculationview, .calculationview               │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  Output Format: [ABAP CDS ▼] / [CAP CDS ▼]                              │
│                                                                          │
│  [Convert to CDS View]                                                  │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Output Preview                                                  │    │
│  │  @AbapCatalog.sqlViewName: 'ZI_EXAMPLE'                         │    │
│  │  define view ZI_EXAMPLE                                          │    │
│  │    with parameters ...                                           │    │
│  │  as select from "CV_EXAMPLE"                                     │    │
│  │  { ... }                                                         │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  [Download .cds]  [Copy to Clipboard]                                   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## SPECIFIC SECTION (Dynamic - Per Sprint)

### Current Status

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ⏸️  YOU ARE BLOCKED                                                     │
│                                                                          │
│  Waiting for: Winston to complete BE-CV-001, BE-CV-002                  │
│  Then: Orc validates G2 (CV structure) and G3 (HANA activation)         │
│  After G3 passes: You can start FE-BEX-001                              │
│                                                                          │
│  DO NOT:                                                                 │
│  - Build API integration (backend not ready)                            │
│  - Test with real conversions (wrong format being generated)            │
│                                                                          │
│  CAN DO:                                                                 │
│  - Read master plan and design docs                                     │
│  - Plan component architecture                                           │
│  - Set up React/Vite project structure                                  │
│  - Create type definitions (conversion.ts)                              │
│  - Build static mockups (no API calls)                                  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### Your Task Queue

#### Priority 0 (Blocked - Wait)

| Task ID | Description | Status | Blocked By |
|---------|-------------|--------|------------|
| FE-BEX-001 | Build BEx-to-CV upload UI | ⏸️ BLOCKED | G3 (CV Activation) |
| FE-BEX-002 | Build conversion report display | ⏸️ BLOCKED | BE-REPORT-001 |

#### Priority 1 (Can Prepare Now)

| Task ID | Description | Status | Notes |
|---------|-------------|--------|-------|
| FE-SETUP-001 | Initialize React/Vite project in ui/frontend/ | 📋 CAN START | No backend dependency |
| FE-SETUP-002 | Create TypeScript types for conversion report | 📋 CAN START | Use plan Section 10 |
| FE-MOCK-001 | Create static mockups with fake data | 📋 CAN START | For UI review |

#### Priority 2 (After G3 Passes)

| Task ID | Description | Status | Depends On |
|---------|-------------|--------|------------|
| FE-BEX-003 | XML output preview with syntax highlighting | 📋 PLANNED | FE-BEX-001 |
| FE-BEX-004 | Download/copy functionality | 📋 PLANNED | FE-BEX-001 |
| FE-CDS-001 | Build CV-to-CDS upload UI | 📋 PLANNED | G5 |
| FE-CDS-002 | ABAP/CAP CDS output selector | 📋 PLANNED | FE-CDS-001 |

---

### Preparation Tasks (While Blocked)

#### FE-SETUP-001: Initialize React Project

**Can Do Now** - No backend dependency

```bash
cd ui/frontend
npm create vite@latest . -- --template react-ts
npm install
npm install @tanstack/react-query axios
npm install -D tailwindcss postcss autoprefixer
```

**Folder Structure to Create:**
```
ui/frontend/
├── src/
│   ├── components/
│   │   ├── FileUpload.tsx
│   │   ├── ConversionReport.tsx
│   │   └── XMLPreview.tsx
│   ├── pages/
│   │   ├── BExToCV.tsx
│   │   └── CVToCDS.tsx
│   ├── hooks/
│   ├── types/
│   │   └── conversion.ts
│   └── api/
├── package.json
└── vite.config.ts
```

---

#### FE-SETUP-002: TypeScript Types

**Can Do Now** - Based on plan Section 10

```typescript
// types/conversion.ts

export interface ConversionReport {
  conversion: {
    input_file: string;
    output_file: string;
    timestamp: string;
    status: 'SUCCESS' | 'SUCCESS_WITH_WARNINGS' | 'FAILED';
  };
  summary: {
    total_elements: number;
    mapped: number;
    defaulted: number;
    stubbed: number;
    skipped: number;
    unsupported_fatal: number;
  };
  elements: {
    mapped: ConversionElement[];
    defaulted: ConversionElement[];
    stubbed: ConversionElement[];
    skipped: ConversionElement[];
  };
  warnings: string[];
  errors: string[];
}

export interface ConversionElement {
  element: string;
  type: string;
  source: string;
  target: string;
  category: 'MAPPED' | 'MAPPING_DEFAULT' | 'UNSUPPORTED_STUB' | 'SKIPPED';
  warning?: string;
  note?: string;
}

export type Pipeline = 'bex-to-cv' | 'cv-to-cds';
export type CDSFormat = 'abap' | 'cap';
```

---

### Messages from Orchestrator

```
[2026-02-01 15:00] ORC:
STATUS: You are BLOCKED on all API-dependent tasks
REASON: Winston needs to fix cv_renderer.py first (BE-CV-001, BE-CV-002)
        Then I validate G2/G3 before you can integrate

CAN DO NOW:
1. FE-SETUP-001: Initialize React project (npm create vite)
2. FE-SETUP-002: Create TypeScript types from plan Section 10
3. FE-MOCK-001: Build static mockups with hardcoded data

DO NOT:
- Call any backend APIs
- Test real conversions
- Mark API-dependent tasks as done

I WILL NOTIFY YOU when G3 passes and you can start FE-BEX-001.
```

---

### Your Status Updates (Write Here)

#### [DATE] Sally:

```
(Write your status updates here when you complete tasks or encounter issues)
Example:
[2026-02-01 16:00] Sally:
- Completed FE-SETUP-001: Initialized Vite React project
- Completed FE-SETUP-002: Created conversion.ts types
- Waiting for G3 to start FE-BEX-001
```

---

### Design Decisions (FROZEN - Do Not Re-Decide)

| Decision | Answer | Plan Reference |
|----------|--------|----------------|
| Frontend Framework | React + TypeScript | - |
| Build Tool | Vite | - |
| Styling | Tailwind CSS | - |
| API Client | Axios + React Query | - |
| Conversion Report Format | YAML (parsed to JSON) | Plan Section 10 |
| CDS Output Options | ABAP CDS, CAP CDS | Plan Decision 7-9 |

---

### Conversion Report Display Spec

When displaying conversion reports, use this hierarchy:

```
Summary Bar:
[12 total] [8 mapped ✓] [2 defaulted ⚠️] [1 stubbed ⚠️] [1 skipped]

Expandable Sections:
├── ✓ Mapped (8) - Green
│   └── List of successfully mapped elements
├── ⚠️ Defaulted (2) - Yellow
│   └── Elements using fallback values (show warning)
├── ⚠️ Stubbed (1) - Orange
│   └── Unsupported features replaced with stubs
└── ○ Skipped (1) - Gray
    └── Elements ignored (documented)
```

**Color Coding:**
- SUCCESS: Green badge
- SUCCESS_WITH_WARNINGS: Yellow badge
- FAILED: Red badge

---

### When Unblocked (After G3 Passes)

1. Orc will update this file with "UNBLOCKED" status
2. Read ORCHESTRATOR_HUB.md for any new decisions
3. Start FE-BEX-001: Build BEx-to-CV upload UI
4. Integrate with backend API (Winston will provide endpoint spec)
5. Update status after each task completion

---

*Maintained by Orc (Orchestrator). Check ORCHESTRATOR_HUB.md for full project status.*
