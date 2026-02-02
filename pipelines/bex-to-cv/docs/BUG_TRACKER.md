# Bug Tracker - BEx to CV Conversion Issues

**Purpose**: Structured tracking of all bugs discovered during BEx to CV conversion testing
**Version**: 1.0.0
**Last Updated**: 2026-02-01

---

## Active Bugs

*No bugs discovered yet - pipeline in development*

---

## Bug Statistics

**Total Bugs Tracked**: 0
**Open**: 0
**Fixed - Awaiting Validation**: 0
**Solved**: 0

---

## Future Bug Template

```markdown
### BUG-XXX: [Short Description]

**Status**: OPEN | IN PROGRESS | FIXED
**Severity**: Critical | High | Medium | Low
**Discovered**: [Date], [XML name]
**XML**: [filename]

**Error**:
[Error message]

**Problem**:
[Description of the issue]

**Root Cause**:
[Analysis of why this happens]

**Related Rules**:
- [Link to BEX_TO_CV_CONVERSION_RULES.md rules that relate]

**Impact**:
[Which XMLs/scenarios affected]

**Affected XMLs**:
- List of XMLs with this bug

**Proposed Solution**:
[How to fix]

**Files Modified** (if fixed):
- List of files changed

**Next Steps**:
1. Action items
```

---

## Common Issue Categories

### Parser Issues
- BEx XML namespace handling (asx:abap)
- G_T_ELTDIR element parsing
- G_T_GLOBV variable extraction
- G_T_SELECT/G_T_RANGE filter mapping

### Renderer Issues
- CV XML namespace generation
- Node graph construction
- Input parameter generation
- Filter expression conversion

### Catalog Issues
- InfoObject resolution failures
- Missing table mappings
- Data type mismatches

---

**Process**: Every HANA error -> Create bug ticket -> Map to rules -> Implement fix -> Document solution
