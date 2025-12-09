# Error Investigation Procedure - When NO VALIDATED SQL Exists

**When**: XML fails HANA validation and NO working SQL exists for comparison  
**Status**: New XML being tested or known problematic XML

---

## SYSTEMATIC PROCEDURE

### STEP 1: Read Generated SQL

**Command**:
```powershell
python -c "lines = open('LATEST_SQL_FROM_DB.txt', encoding='utf-8').readlines(); print(f'Total lines: {len(lines)}'); print(f'Line 1: {lines[0][:80]}'); print(f'Scenario: {lines[1] if len(lines) > 1 else \"N/A\"}')"
```

**Record**:
- [ ] Total lines: _________
- [ ] Scenario ID: _________
- [ ] CREATE VIEW line exists: Yes/No

---

### STEP 2: Locate Exact Error Line

**From HANA error message, extract:**
- Line number (e.g., "line 28")
- Column number (e.g., "col 3")
- Error type (e.g., "incorrect syntax near )")

**Command** (replace LINE_NUM with actual line from error):
```powershell
python -c "lines = open('LATEST_SQL_FROM_DB.txt', encoding='utf-8').readlines(); line_num = [LINE_NUM]; print(f'Line {line_num-1}: {lines[line_num-2] if line_num > 1 else \"N/A\"}'); print(f'Line {line_num}: {lines[line_num-1]}'); print(f'Line {line_num+1}: {lines[line_num] if line_num < len(lines) else \"N/A\"}')"
```

**Record**:
- [ ] Error line number: _________
- [ ] Line before error: _________
- [ ] Error line content: _________
- [ ] Line after error: _________

---

### STEP 3: Identify SQL Pattern at Error

**Analyze the error line for common issues:**

**Checklist**:
- [ ] Unbalanced parentheses? (count ( vs ))
- [ ] Orphaned operator? (AND/OR with no following condition)
- [ ] Missing operand? (= without left or right side)
- [ ] Invalid function? (function that doesn't exist in HANA)
- [ ] Wrong syntax? (function used as operator or vice versa)
- [ ] Empty clause? (WHERE (), IN (), etc.)
- [ ] Parameter cleanup artifact? (leftover from $$PARAM$$ substitution)

**Pattern identified**: _________

---

### STEP 4: Search Known Bug Patterns

**Check BUG_TRACKER.md for similar errors:**

**Command**:
```powershell
findstr /C:"[ERROR_CODE]" docs\bugs\BUG_TRACKER.md
findstr /C:"[ERROR_FRAGMENT]" docs\bugs\BUG_TRACKER.md
```

**Examples**:
- `[321] invalid view name` → BUG-029 (view name quoting)
- `[328] invalid name of function` → Missing catalog entry
- `[257] syntax error near ")"` → Parameter cleanup, empty clauses
- `[260] invalid column name` → Column qualification issues

**Check SOLVED_BUGS.md for solutions:**

**Command**:
```powershell
findstr /C:"[ERROR_PATTERN]" docs\bugs\SOLVED_BUGS.md
```

**Record**:
- [ ] Similar bug found: BUG-XXX
- [ ] Solution documented: Yes/No
- [ ] Applies to this case: Yes/No

---

### STEP 5: Check Conversion Rules

**Map error to rules in HANA_CONVERSION_RULES.md:**

**Common Mappings**:
| Error Type | Check Rule | Location |
|------------|-----------|----------|
| Invalid function name | Rule #14 (Legacy casts), Rule #15 (Function case) | Lines 910-977 |
| Invalid operator | Rule #2 (IN → OR) | Lines 582-607 |
| View name not quoted | PRINCIPLE #5 | Lines 358-452 |
| Column ambiguity | PRINCIPLE #4 | Lines 282-355 |
| CTE not found | PRINCIPLE #3 | Lines 202-279 |
| Parameter artifacts | PRINCIPLE #2 | Lines 118-199 |

**Check**:
```powershell
findstr /i "[RULE_KEYWORD]" docs\rules\HANA_CONVERSION_RULES.md
```

**Record**:
- [ ] Rule violated: _________
- [ ] Rule documented: Yes/No
- [ ] Implementation location: _________

---

### STEP 6: Analyze XML Source

**When no working SQL exists, check XML to understand intent:**

**Command**:
```powershell
findstr /C:"[ELEMENT_NAME]" "Source (XML Files)\[PATH]\[XML_FILE]"
```

**Check**:
- [ ] What function is used in XML?
- [ ] What is the intended transformation?
- [ ] Are there parameters in WHERE clause?
- [ ] Are there calculated columns referenced in filters?

**Record XML intent**: _________

---

### STEP 7: Check Catalog Completeness

**Verify function/pattern exists:**

**For function errors**:
```powershell
findstr /i "[FUNCTION_NAME]" src\xml_to_sql\catalog\data\functions.yaml
```

**For pattern errors**:
```powershell
findstr /i "[PATTERN]" src\xml_to_sql\catalog\data\patterns.yaml
```

**Check if mapping is**:
- [ ] Missing entirely
- [ ] Incorrect target
- [ ] Wrong handler type

**Record**: _________

---

### STEP 8: Root Cause Determination

**Based on Steps 1-7, determine root cause:**

**Categories**:
1. **Missing Catalog Entry** → Add to functions.yaml or patterns.yaml
2. **Wrong Catalog Mapping** → Fix target or handler
3. **Parameter Cleanup Issue** → Check renderer.py cleanup patterns
4. **Column Qualification Issue** → Check renderer.py qualification logic
5. **Subquery Wrapping Missing** → Check needs_subquery logic
6. **Rule Not Implemented** → Code change required (DANGEROUS)

**Root Cause**: _________

---

### STEP 9: Determine Fix Strategy

**Based on root cause:**

**STRATEGY A: Add Catalog Entry** (SAFE)
- Missing function? Add to functions.yaml
- Missing pattern? Add to patterns.yaml
- Run: `pip install -e .`
- Test

**STRATEGY B: Fix Catalog Entry** (SAFE)
- Wrong target? Update functions.yaml
- Wrong handler? Change rename ↔ template
- Run: `pip install -e .`
- Test

**STRATEGY C: Parameter Cleanup** (MEDIUM RISK)
- Add cleanup pattern to renderer.py
- Test against other XMLs for regression
- Document in BUG_TRACKER

**STRATEGY D: Code Fix** (HIGH RISK)
- Requires changing renderer.py logic
- MUST test all VALIDATED XMLs after
- Document as new bug
- Surgical precision required

**STRATEGY E: Known Limitation** (DEFER)
- Bug is documented as Active
- No safe fix exists yet
- Document in GOLDEN_COMMIT as limitation
- Move to next XML

**Selected Strategy**: _________

---

### STEP 10: Document as New Bug (If Needed)

**If this is a NEW bug pattern:**

**Create ticket in BUG_TRACKER.md**:
```markdown
### 🔴 BUG-XXX: [Short Description]

**Priority**: [Critical/High/Medium/Low]
**Status**: Active
**Discovered**: [XML name], [Date]
**Affects**: [Which XMLs]

**Error**:
```
[HANA error message]
```

**Problem**:
```sql
[SQL fragment showing issue]
```

**Root Cause**:
[Analysis]

**Proposed Solution**:
[How to fix]

**Next Steps**:
1. [Action items]
```

---

### STEP 11: Implement Fix

**Execute selected strategy from Step 9**

**For Catalog Changes**:
1. Edit functions.yaml or patterns.yaml
2. Run: `pip install -e .`
3. Restart server
4. Test

**For Code Changes**:
1. Make SURGICAL change
2. Document with BUG-XXX comment
3. Test THIS XML
4. Test ALL VALIDATED XMLs (regression check)
5. If any regression → REVERT

---

### STEP 12: Request Regeneration

**Commands for user**:
```powershell
pip install -e .  # If catalog changed
# Restart server
# Test XML in web UI
```

**Expected**:
- [ ] If SUCCESS → Follow SUCCESS_PROCEDURE.md
- [ ] If ERROR → Repeat Steps 1-11

---

## CURRENT CASE: CV_CT02_CT03

**Error**: Line 28 "syntax error near )"

**Following procedure:**

**STEP 1**: ✅ Read SQL - 270 lines
**STEP 2**: Need to check line 28
**STEP 3**: Checking pattern...
**STEP 4**: BUG-019 documented (REGEXP_LIKE + calc columns)
**STEP 5**: Rule - (checking)
**STEP 6**: XML source - (need to check)
**STEP 7**: ✅ Found MATCH → LIKE (wrong!)
**STEP 8**: Root cause: MATCH mapped to LIKE() which doesn't exist as function
**STEP 9**: Strategy A - Fix catalog (changed MATCH → REGEXP_LIKE)
**STEP 10**: Not new bug - catalog error
**STEP 11**: ✅ Fixed functions.yaml
**STEP 12**: Requesting regeneration...

---

**This procedure works for ANY XML without validated baseline.**

