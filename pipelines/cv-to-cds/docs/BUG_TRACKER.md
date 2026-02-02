# Bug Tracker - CV to CDS Conversion Issues

**Purpose**: Structured tracking of all bugs discovered during CV to CDS conversion testing
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
**Discovered**: [Date], [CV name]
**CV**: [filename]
**CDS Syntax**: ABAP | CAP

**Error**:
[Compilation error message]

**Problem**:
[Description of the issue]

**Root Cause**:
[Analysis of why this happens]

**Related Rules**:
- [Link to ABAP_CDS_CONVERSION_RULES.md or CAP_CDS_CONVERSION_RULES.md]

**Impact**:
[Which CVs/scenarios affected]

**Affected CVs**:
- List of CVs with this bug

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
- CV XML namespace handling (View:ColumnView)
- Node graph traversal
- Element extraction
- Aggregation behavior mapping

### ABAP CDS Renderer Issues
- @Analytics annotation generation
- Type mapping (HANA → ABAP types)
- Association generation
- Parameter declaration syntax

### CAP CDS Renderer Issues
- Entity definition syntax
- Type mapping (HANA → CAP types)
- Aspect/projection generation

### Catalog Issues
- Type mapping failures
- Missing annotation rules
- Semantic type resolution

---

**Process**: Every compilation error -> Create bug ticket -> Map to rules -> Implement fix -> Document solution
