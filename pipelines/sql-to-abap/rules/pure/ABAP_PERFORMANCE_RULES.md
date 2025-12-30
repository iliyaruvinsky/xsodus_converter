# ABAP Performance Rules

## Overview

This document defines performance optimization patterns for Pure ABAP extraction programs. Following these rules prevents TIME_OUT dumps and ensures efficient memory usage.

**Critical**: BW metadata tables can contain millions of records. Without proper filtering and optimization, extractions will TIME_OUT or crash.

---

## Rule 1: FOR ALL ENTRIES Pattern

### Problem
Direct SELECT with subquery causes full table scans:
```abap
" BAD - Full table scan on dd03l
SELECT * FROM dd03l
  WHERE tabname IN (SELECT exstruct FROM roosfield WHERE ...).
```

### Solution
Use FOR ALL ENTRIES with guard check:
```abap
" GOOD - Index-friendly lookup
DATA: lt_keys TYPE TABLE OF ty_keys.

" Step 1: Get keys
SELECT DISTINCT exstruct AS tabname
  INTO TABLE lt_keys
  FROM roosfield
  WHERE objvers = 'A'.

" Step 2: Use FAE with guard
IF lt_keys IS NOT INITIAL.
  SELECT tabname fieldname datatype leng
    INTO TABLE lt_dd03l
    FROM dd03l
    FOR ALL ENTRIES IN lt_keys
    WHERE tabname = lt_keys-tabname
      AND fieldname NOT LIKE '.INCLUDE%'.
ENDIF.
```

### Key Points
- **ALWAYS** check `IS NOT INITIAL` before FOR ALL ENTRIES
- FAE with empty table returns ALL records (dangerous!)
- Use DISTINCT when extracting keys to avoid duplicates
- FAE columns must match key types exactly

---

## Rule 2: Business Filters

### Problem
BW tables contain all versions (Active, Modified, Delivered):
```abap
" BAD - Gets all versions (3x+ data volume)
SELECT * FROM rsdiobj.
```

### Solution
Always filter to active version only:
```abap
" GOOD - Active version only
SELECT * FROM rsdiobj
  WHERE objvers = 'A'.
```

### Standard Business Filters
| Table | Filter | Reason |
|-------|--------|--------|
| ROOSOURCE | `objvers = 'A' AND type <> 'HIER'` | Active, non-hierarchy |
| ROOSFIELD | `objvers = 'A'` | Active version |
| RSDIOBJ | `objvers = 'A'` | Active InfoObjects |
| RSDIOBJT | `objvers = 'A' AND langu = 'E'` | Active + English |
| DD03L | `fieldname NOT LIKE '.INCLUDE%'` | Exclude includes |
| DD03T | `ddlanguage = 'E'` | English texts only |

---

## Rule 3: Package Processing

### Problem
Large result sets cause memory overflow:
```abap
" BAD - Loads entire table into memory
SELECT * FROM large_table INTO TABLE lt_data.
" If lt_data has 10M rows = memory crash
```

### Solution
Process in packages:
```abap
" GOOD - Process in 10,000 row chunks
CONSTANTS: c_package_size TYPE i VALUE 10000.

DATA: lt_chunk TYPE TABLE OF ty_data.

SELECT * FROM large_table
  INTO TABLE lt_chunk
  PACKAGE SIZE c_package_size.

  " Process chunk
  LOOP AT lt_chunk INTO ls_item.
    " Process single record
    APPEND ls_item TO lt_result.
  ENDLOOP.

  " Release memory
  FREE lt_chunk.

ENDSELECT.
```

### Alternative: UP TO N ROWS
For sampling or testing:
```abap
" Limit results for testing
SELECT * FROM large_table
  INTO TABLE lt_data
  UP TO 1000 ROWS.
```

---

## Rule 4: Memory Management

### Problem
Internal tables accumulate memory during processing:
```abap
" BAD - Memory leak
LOOP AT lt_source INTO ls_source.
  APPEND ls_source TO lt_result.
ENDLOOP.
" lt_source still holds all data
```

### Solution
Free tables after use:
```abap
" GOOD - Release source memory
LOOP AT lt_source INTO ls_source.
  APPEND ls_source TO lt_result.
ENDLOOP.

FREE lt_source. " Release memory

" Or use DELETE during processing
LOOP AT lt_source INTO ls_source.
  APPEND ls_source TO lt_result.
  DELETE lt_source INDEX sy-tabix.
ENDLOOP.
```

### Bulk Free
```abap
" Free multiple tables at once
FREE: lt_temp1, lt_temp2, lt_temp3, lt_keys.
```

---

## Rule 5: Index-Friendly WHERE Clauses

### Problem
WHERE clause columns not in index order:
```abap
" BAD - May not use index efficiently
SELECT * FROM rsdiobj
  WHERE datatp = 'CHAR'
    AND objvers = 'A'.
```

### Solution
Order WHERE conditions to match index (primary key first):
```abap
" GOOD - Index-friendly (primary key columns first)
SELECT * FROM rsdiobj
  WHERE objvers = 'A'
    AND iobjnm LIKE 'Z%'
    AND datatp = 'CHAR'.
```

### Index Tips
- Put primary key columns first in WHERE
- Use equality (=) before ranges (BETWEEN, LIKE)
- Avoid NOT LIKE on leading columns
- Check table indexes with SE11/SE14

---

## Rule 6: Avoid SELECT *

### Problem
SELECT * retrieves all columns including BLOBs:
```abap
" BAD - Gets all columns including large ones
SELECT * FROM rsdiobj INTO TABLE lt_data.
```

### Solution
Select only needed columns:
```abap
" GOOD - Only needed columns
SELECT iobjnm iobjtp datatp lnglth
  INTO TABLE lt_data
  FROM rsdiobj
  WHERE objvers = 'A'.
```

### Benefits
- Less data transferred from DB
- Smaller internal table memory
- Faster processing

---

## Rule 7: Aggregation at Database Level

### Problem
Aggregating in ABAP after SELECT:
```abap
" BAD - Gets all records, aggregates in ABAP
SELECT * FROM sales_data INTO TABLE lt_all.
LOOP AT lt_all INTO ls_item.
  COLLECT ls_item INTO lt_aggregated.
ENDLOOP.
```

### Solution
Use SQL aggregation:
```abap
" GOOD - Aggregation at database level
SELECT material SUM( quantity ) AS total_qty
  INTO TABLE lt_aggregated
  FROM sales_data
  GROUP BY material.
```

### When to Use COLLECT
Only use ABAP COLLECT when:
- Data comes from multiple sources
- Complex aggregation logic needed
- Database GROUP BY not possible

---

## Rule 8: Parallel Processing (Advanced)

### For Very Large Extractions
```abap
" Split work by first character of key
DATA: lt_ranges TYPE RANGE OF char1.

" Create ranges: A-D, E-H, I-L, etc.
APPEND VALUE #( sign = 'I' option = 'BT' low = 'A' high = 'D' ) TO lt_ranges.
" ... more ranges

" Submit parallel jobs
LOOP AT lt_ranges INTO ls_range.
  SUBMIT z_extract_parallel
    WITH s_key IN lt_ranges
    VIA JOB lv_jobname NUMBER lv_jobcount
    AND RETURN.
ENDLOOP.
```

### Alternative: Background RFC
```abap
" Use aRFC for parallel execution
CALL FUNCTION 'Z_EXTRACT_CHUNK'
  STARTING NEW TASK lv_task
  DESTINATION 'NONE'
  PERFORMING callback ON END OF TASK
  EXPORTING
    iv_start_key = lv_start
    iv_end_key = lv_end.
```

---

## Rule 9: TIME_OUT Prevention Checklist

Before running extraction:
- [ ] Add `objvers = 'A'` filter
- [ ] Add language filter for text tables
- [ ] Use FOR ALL ENTRIES (not subqueries)
- [ ] Check estimated row count first
- [ ] Consider package processing for > 100K rows

### Quick Row Count Check
```abap
SELECT COUNT(*) INTO lv_count
  FROM target_table
  WHERE objvers = 'A'.

WRITE: / 'Expected rows:', lv_count.
IF lv_count > 100000.
  WRITE: / 'WARNING: Large dataset - use package processing'.
ENDIF.
```

---

## Rule 10: Database Hints (HANA-Specific)

### For HANA Systems
```abap
" Use HANA-specific hints when needed
SELECT * FROM rsdiobj
  INTO TABLE lt_data
  %_HINTS HANA 'NO_CS_JOIN'.
```

### Common HANA Hints
| Hint | Purpose |
|------|---------|
| NO_CS_JOIN | Disable column store join |
| RESULT_LAG | Allow slightly stale data (faster) |
| USE_OLAP_PLAN | Force OLAP engine |

**Note**: Pure ABAP should work without hints. Only add if performance testing shows benefit.

---

## Performance Metrics

### Acceptable Thresholds
| Metric | Acceptable | Warning | Critical |
|--------|------------|---------|----------|
| Row count | < 100K | 100K-1M | > 1M |
| Execution time | < 60s | 60-300s | > 300s |
| Memory usage | < 500MB | 500MB-1GB | > 1GB |

### How to Measure
```abap
DATA: lv_start TYPE timestampl,
      lv_end TYPE timestampl,
      lv_runtime TYPE i.

GET TIME STAMP FIELD lv_start.

" ... extraction logic ...

GET TIME STAMP FIELD lv_end.
lv_runtime = cl_abap_timestamp_diff=>get_difference(
  from = lv_start
  to = lv_end ).

WRITE: / 'Runtime (ms):', lv_runtime.
```

---

## Anti-Patterns Summary

| Anti-Pattern | Problem | Solution |
|--------------|---------|----------|
| SELECT * | Gets unnecessary columns | List specific columns |
| Missing objvers filter | Gets all versions | Add `objvers = 'A'` |
| SELECT...WHERE IN (subquery) | Full table scan | Use FOR ALL ENTRIES |
| No FAE guard check | Returns all data if empty | Check IS NOT INITIAL |
| Loading entire table | Memory overflow | Use PACKAGE SIZE |
| Not freeing tables | Memory leak | Use FREE after processing |
| ABAP aggregation | Slow for large datasets | Use SQL GROUP BY |

---

## Quick Reference

### Minimum Required Filters
```abap
" BW metadata tables
WHERE objvers = 'A'

" Text tables
WHERE langu = 'E' (or ddlanguage = 'E')

" Dictionary tables
WHERE fieldname NOT LIKE '.INCLUDE%'
```

### Standard FAE Template
```abap
" 1. Get keys
SELECT DISTINCT key_field INTO TABLE lt_keys FROM source_table WHERE filters.

" 2. Guard check
IF lt_keys IS NOT INITIAL.
  " 3. FAE select
  SELECT fields INTO TABLE lt_data FROM target_table
    FOR ALL ENTRIES IN lt_keys
    WHERE key_field = lt_keys-key_field.
ENDIF.

" 4. Free keys
FREE lt_keys.
```

---

**Last Updated**: 2025-12-30
**Version**: 1.0
