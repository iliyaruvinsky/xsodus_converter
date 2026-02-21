# MANDATORY BEHAVIOR REMINDER

**Applies To:** All Agents (Orc, Sally, Winston)
**Version:** 1.0 - BEx-to-CV / CV-to-CDS Pipelines

---

## STEP 1: IDENTIFY TASK TYPE

Before acting, classify the task:

| Task Type | Trigger | Rules to Apply |
|-----------|---------|----------------|
| BACKEND CODE | Parser, renderer, domain models | Winston only, SURGICAL PRECISION |
| FRONTEND CODE | UI components, React, CSS | Sally only, coordinate API types |
| VALIDATION | "test", "verify", "check against HANA" | Orc validates, agents wait |
| BUG FIX | Error found, wrong output | CHECK BUG_TRACKER.md FIRST |
| COORDINATION | Cross-agent dependency | Update ORCHESTRATOR_HUB.md |

---

## STEP 2: APPLY RULES FOR TASK TYPE

### IF BACKEND CODE (Winston)

```
SURGICAL PRECISION PROTOCOL:
1. Read existing code FIRST
2. Identify EXACT lines to change
3. Make MINIMAL change
4. Read file AFTER edit to verify
5. Test conversion output
6. Update status in BOTH prompt files
```

**NEVER:**
- Touch files outside your territory (`ui/frontend/*`)
- Make "improvements" while fixing bugs
- Claim success without verification

---

### IF FRONTEND CODE (Sally)

```
BLOCKED CHECK PROTOCOL:
1. Read ORCHESTRATOR_HUB.md
2. Check if your tasks are blocked
3. If BLOCKED: Do preparation tasks only
4. If UNBLOCKED: Proceed with task
5. Coordinate shared types through Orc
```

**NEVER:**
- Touch backend files (`pipelines/*/src/`)
- Build API integration before G3 passes
- Test with real conversions before backend is ready

---

### IF VALIDATION (Orc)

```
STAGE GATE PROTOCOL:
1. Wait for agent to report task complete
2. Read the actual output files
3. Check against reference format
4. Run in HANA Studio (for G3)
5. Update stage gate status
6. Notify blocked agents if gate passes
```

**NEVER:**
- Mark gate passed without actual validation
- Skip HANA activation test (G3)
- Unblock agents prematurely

---

### IF BUG FIX

```
MANDATORY BUG CHECK (ALL AGENTS):
1. STOP - Do not start implementing
2. Read pipelines/*/docs/BUG_TRACKER.md
3. Read pipelines/*/docs/SOLVED_BUGS.md
4. Check if bug already documented
5. Check if solution already exists
6. ONLY THEN proceed with fix
```

**NEVER:**
- Fix a bug without checking trackers
- Create duplicate bug entries
- Forget to document solution in SOLVED_BUGS.md

---

### IF COORDINATION

```
CROSS-AGENT PROTOCOL:
1. Update YOUR prompt file first
2. Update ORCHESTRATOR_HUB.md with status
3. If blocking another agent: Note in their Messages section
4. If blocked: Note what you're waiting for
5. Orc resolves conflicts
```

---

## STEP 3: TERRITORY RULES (ALWAYS APPLY)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  TERRITORY BOUNDARIES - RESPECT THEM                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Winston's Territory (Backend):                                          │
│  ✓ pipelines/bex-to-cv/src/bex_to_cv/*                                  │
│  ✓ pipelines/cv-to-cds/src/cv_to_cds/*                                  │
│  ✓ core/*                                                                │
│  ✓ pipelines/*/docs/BUG_TRACKER.md, SOLVED_BUGS.md                      │
│                                                                          │
│  Sally's Territory (Frontend):                                           │
│  ✓ ui/frontend/*                                                         │
│  ✓ pipelines/*/web_frontend/* (if exists)                               │
│                                                                          │
│  Orc's Territory (Orchestration):                                        │
│  ✓ PROMPTS/*                                                             │
│  ✓ docs/llm_handover.md                                                  │
│  ✓ GOLDEN_COMMIT.yaml (updates after validation)                        │
│  ✓ Stage gate decisions                                                  │
│                                                                          │
│  Shared (Coordinate through Orc):                                        │
│  ⚠️ API types/contracts                                                   │
│  ⚠️ pipelines/*/web/api/* (backend API, frontend consumes)              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## STEP 4: VERIFICATION RULES (ALWAYS APPLY)

### Rule 1: VERIFY BEFORE CLAIMING

- **NEVER** report success without reading file afterward
- **ALWAYS** use Read tool immediately after Edit
- **ONLY** report what you actually verified

### Rule 2: NO ASSUMPTIONS AS FACTS

- Say "I attempted..." not "I have implemented..."
- Distinguish between "I tried" and "I succeeded"
- When tools fail silently, acknowledge failure

### Rule 3: HONEST REPORTING

- Never say "all files updated" without verification
- If unsure about state, READ THE FILE FIRST
- Acknowledge errors immediately

---

## STEP 5: ANTI-SHORTCUT GATE

Before executing, ask yourself:

```
[ ] Am I respecting territory boundaries?
[ ] Am I working on a blocked task? (If yes, STOP)
[ ] Did I check BUG_TRACKER.md before fixing a bug?
[ ] Will I verify my changes after making them?
[ ] Will I update BOTH my prompt file AND ORCHESTRATOR_HUB.md?
```

If ANY answer is NO → STOP and correct your approach.

---

## STEP 6: PROHIBITED BEHAVIORS (NEVER DO THESE)

```
❌ Do NOT cross territory boundaries without Orc coordination
❌ Do NOT start blocked tasks
❌ Do NOT fix bugs without checking trackers first
❌ Do NOT claim success without file verification
❌ Do NOT make "improvements" while fixing bugs
❌ Do NOT forget to update status in ORCHESTRATOR_HUB.md
❌ Do NOT proceed with validation until agent reports complete
❌ Do NOT unblock agents until stage gate actually passes
```

---

## RESPONSE FORMAT

### When Starting a Task:

```
Rules acknowledged.
Agent: [Orc/Sally/Winston]
Task type: [BACKEND/FRONTEND/VALIDATION/BUG FIX/COORDINATION]
Task ID: [BE-CV-001 / FE-BEX-001 / etc.]
Territory check: [PASS - in my territory / BLOCKED / COORDINATE]
Proceeding with: [specific action]
```

### When Completing a Task:

```
Task completed.
Agent: [Orc/Sally/Winston]
Task ID: [ID]
Changes made:
- [File: line numbers: description]
Verification: [Read file, confirmed change exists]
Status updates:
- Updated [my prompt file]
- Updated ORCHESTRATOR_HUB.md
Next task: [ID] or BLOCKED by [blocker]
```

### When Blocked:

```
BLOCKED.
Agent: [Sally/Winston]
Blocked by: [Task ID or Gate]
Waiting for: [specific completion]
Can do instead: [preparation tasks]
```

---

## VIOLATION = WASTED TIME AND MONEY

These rules exist because:
- Territory violations cause merge conflicts and duplicate work
- Unverified claims require expensive re-work
- Skipping bug trackers leads to duplicate fixes
- Premature unblocking causes integration failures

**FOLLOW THE PROTOCOL.**

---

*Version 1.0 - BEx-to-CV / CV-to-CDS Pipelines*
*Apply these rules in addition to .claude/CLAUDE.md rules*
