# BW Metadata Extraction Rules

## Overview

This document defines standard patterns for extracting metadata from SAP BW systems using Pure ABAP. These patterns are designed to work on any SAP system with BW components.

**Purpose**: Extract BW metadata to CSV for migration to target data warehouses (Snowflake, SQL Server, SAP Datasphere).

---

## Core Principles

### 1. Always Filter Active Versions
BW metadata tables contain multiple versions of objects:
- `objvers = 'A'` - Active version (production)
- `objvers = 'M'` - Modified version (development)
- `objvers = 'D'` - Delivered version (SAP standard)

**ALWAYS** filter by `objvers = 'A'` for production extractions.

### 2. Language Filtering
Text tables contain descriptions in multiple languages:
- Filter by `langu = 'E'` or `ddlanguage = 'E'` for English
- Or use `sy-langu` for current user language

### 3. Use FOR ALL ENTRIES Pattern
To prevent TIME_OUT on large tables:
1. Extract primary keys first (driving table)
2. Use FOR ALL ENTRIES for dependent tables
3. Always check `IF lt_keys IS NOT INITIAL` before FAE

---

## InfoObject Extraction

### Tables
| Table | Purpose | Key Fields |
|-------|---------|------------|
| RSDIOBJ | InfoObject definitions | IOBJNM, IOBJTP, DATATP, LNGLTH |
| RSDIOBJT | InfoObject texts | IOBJNM, LANGU, TXTLG, TXTSH |
| RSDBCHATR | Characteristic attributes | CHABASNM, ATTRINM |
| RSDATRNAV | Navigation attributes | CHABASNM, ATTRINM |
| RSDCHABAS | Master data tables | CHABASNM |

### Filters
```abap
" Active InfoObjects only
WHERE objvers = 'A'

" English texts
WHERE objvers = 'A' AND langu = 'E'

" Exclude SAP standard (optional)
WHERE objvers = 'A' AND iobjnm NOT LIKE '0%'
```

### SQL Pattern (CTE)
```sql
WITH infoobjects AS (
  SELECT
    r.iobjnm,
    r.iobjtp,
    r.datatp,
    r.lnglth,
    r.decimals,
    r.lowercase,
    r.masterdata,
    r.authrelevant
  FROM SAPABAP1.rsdiobj AS r
  WHERE r.objvers = 'A'
),
infoobject_texts AS (
  SELECT
    t.iobjnm,
    t.txtlg,
    t.txtsh
  FROM SAPABAP1.rsdiobjt AS t
  WHERE t.objvers = 'A' AND t.langu = 'E'
),
result AS (
  SELECT
    i.iobjnm AS INFOOBJECT,
    t.txtlg AS DESCRIPTION,
    i.iobjtp AS TYPE,
    i.datatp AS DATA_TYPE,
    i.lnglth AS LENGTH,
    i.decimals AS DECIMALS
  FROM infoobjects AS i
  LEFT JOIN infoobject_texts AS t ON i.iobjnm = t.iobjnm
)
SELECT * FROM result
```

### Output Fields
| Field | Description | Example |
|-------|-------------|---------|
| IOBJNM | Technical name | 0MATERIAL, ZBWCUST |
| TXTLG | Long description | Material Number |
| IOBJTP | Type | CHA=Characteristic, KYF=Key Figure, TIM=Time, UNI=Unit |
| DATATP | Data type | CHAR, NUMC, DEC, DATS |
| LNGLTH | Length | 18 |
| DECIMALS | Decimal places | 2 |

---

## DataSource Extraction

### Tables
| Table | Purpose | Key Fields |
|-------|---------|------------|
| ROOSOURCE | DataSource definitions | OLTPSOURCE, TYPE, EXTRACTOR |
| ROOSOURCET | DataSource texts | OLTPSOURCE, LANGU, TXTLG |
| ROOSFIELD | DataSource fields | OLTPSOURCE, FIELDNM, EXSTRUCT |
| DD03L | Dictionary table fields | TABNAME, FIELDNAME, DATATYPE |
| DD03T | Field texts | TABNAME, FIELDNAME, DDTEXT |

### Filters
```abap
" Active DataSources, exclude hierarchy
WHERE objvers = 'A' AND type <> 'HIER'

" Field definitions - exclude includes
WHERE fieldname NOT LIKE '.INCLUDE%'
  AND fieldname NOT LIKE 'INCLU-%'
```

### SQL Pattern (CTE)
```sql
WITH datasources AS (
  SELECT
    r.oltpsource,
    r.type,
    r.extractor,
    r.extracttyp,
    r.deltaflag
  FROM SAPABAP1.roosource AS r
  WHERE r.objvers = 'A' AND r.type <> 'HIER'
),
datasource_texts AS (
  SELECT
    t.oltpsource,
    t.txtlg
  FROM SAPABAP1.roosourcet AS t
  WHERE t.langu = 'E'
),
datasource_fields AS (
  SELECT
    f.oltpsource,
    f.fieldnm,
    f.keyflag,
    f.exstruct,
    f.selection
  FROM SAPABAP1.roosfield AS f
  WHERE f.objvers = 'A'
),
result AS (
  SELECT
    d.oltpsource AS DATASOURCE,
    t.txtlg AS DESCRIPTION,
    d.type AS TYPE,
    d.extractor AS EXTRACTOR_FM,
    f.fieldnm AS FIELD_NAME,
    f.keyflag AS IS_KEY
  FROM datasources AS d
  LEFT JOIN datasource_texts AS t ON d.oltpsource = t.oltpsource
  INNER JOIN datasource_fields AS f ON d.oltpsource = f.oltpsource
)
SELECT * FROM result
```

### Output Fields
| Field | Description | Example |
|-------|-------------|---------|
| OLTPSOURCE | DataSource technical name | 0CO_OM_OPA_1 |
| TXTLG | Description | Overhead Orders |
| TYPE | Type | TRAN=Transaction, MAST=Master |
| EXTRACTOR | Extractor function module | RSA1_... |
| FIELDNM | Field name | AUFNR, KOSTL |

---

## Transformation Extraction

### Tables
| Table | Purpose | Key Fields |
|-------|---------|------------|
| RSTRAN | Transformation definitions | TRANID, SOURCENAME, TARGETNAME |
| RSTRANDT | Transformation texts | TRANID, LANGU, TXTLG |
| RSTRANFIELD | Field mappings | TRANID, FIELDNM, RULEID |
| RSTRANRULE | Transformation rules | TRANID, RULEID, FORMULA |

### Filters
```abap
" Active transformations only
WHERE objvers = 'A' AND objstat = 'ACT'
```

### SQL Pattern (CTE)
```sql
WITH transformations AS (
  SELECT
    t.tranid,
    t.sourcetype,
    t.sourcename,
    t.targettype,
    t.targetname,
    t.objstat
  FROM SAPABAP1.rstran AS t
  WHERE t.objvers = 'A' AND t.objstat = 'ACT'
),
transformation_texts AS (
  SELECT
    tt.tranid,
    tt.txtlg
  FROM SAPABAP1.rstrandt AS tt
  WHERE tt.langu = 'E'
),
field_mappings AS (
  SELECT
    f.tranid,
    f.fieldnm AS target_field,
    f.ruleid
  FROM SAPABAP1.rstranfield AS f
),
result AS (
  SELECT
    t.tranid AS TRANSFORMATION_ID,
    tx.txtlg AS DESCRIPTION,
    t.sourcetype AS SOURCE_TYPE,
    t.sourcename AS SOURCE_NAME,
    t.targettype AS TARGET_TYPE,
    t.targetname AS TARGET_NAME,
    f.target_field AS TARGET_FIELD
  FROM transformations AS t
  LEFT JOIN transformation_texts AS tx ON t.tranid = tx.tranid
  LEFT JOIN field_mappings AS f ON t.tranid = f.tranid
)
SELECT * FROM result
```

---

## Process Chain Extraction

### Tables
| Table | Purpose | Key Fields |
|-------|---------|------------|
| RSPCCHAIN | Process chain definitions | CHAIN_ID, TYPE |
| RSPCCHAINATTR | Chain attributes | CHAIN_ID, ATTRIBUTE |
| RSPCCHAINT | Chain texts | CHAIN_ID, LANGU, TXTLG |
| RSPCPROCESSLOG | Execution history | LOG_ID, CHAIN_ID, DATUM |

### Filters
```abap
" Active process chains only
WHERE objvers = 'A'

" Recent execution history (last 30 days)
WHERE datum >= sy-datum - 30
```

### SQL Pattern (CTE)
```sql
WITH process_chains AS (
  SELECT
    c.chain_id,
    c.type,
    c.is_plan_allowed
  FROM SAPABAP1.rspcchain AS c
  WHERE c.objvers = 'A'
),
chain_texts AS (
  SELECT
    t.chain_id,
    t.txtlg
  FROM SAPABAP1.rspcchaint AS t
  WHERE t.langu = 'E'
),
recent_logs AS (
  SELECT
    l.chain_id,
    l.log_id,
    l.datum,
    l.state
  FROM SAPABAP1.rspcprocesslog AS l
  WHERE l.datum >= ADD_DAYS(CURRENT_DATE, -30)
),
result AS (
  SELECT
    c.chain_id AS CHAIN_ID,
    t.txtlg AS DESCRIPTION,
    c.type AS TYPE,
    COUNT(l.log_id) AS EXECUTION_COUNT,
    MAX(l.datum) AS LAST_EXECUTION
  FROM process_chains AS c
  LEFT JOIN chain_texts AS t ON c.chain_id = t.chain_id
  LEFT JOIN recent_logs AS l ON c.chain_id = l.chain_id
  GROUP BY c.chain_id, t.txtlg, c.type
)
SELECT * FROM result
```

---

## InfoProvider Extraction

### Tables
| Table | Purpose | Key Fields |
|-------|---------|------------|
| RSDIOBJ | InfoCubes/DSOs (IOBJTP='IOBJ') | IOBJNM, INFOCUBE |
| RSDCUBE | InfoCube definitions | INFOCUBE, CUBETP |
| RSDCUBET | InfoCube texts | INFOCUBE, LANGU, TXTLG |
| RSDODSO | DSO definitions | ODSOBJECT, ODOTP |
| RSDODSOT | DSO texts | ODSOBJECT, LANGU, TXTLG |

### Filters
```abap
" InfoCubes
WHERE cubetp = 'IC' AND objvers = 'A'

" DSOs/ADSOs
WHERE objvers = 'A'
```

---

## Business Filters Reference

These filters are auto-applied by the sql_to_abap.py generator:

```python
BUSINESS_FILTERS = {
    'ROOSOURCE': ["objvers = 'A'", "type <> 'HIER'"],
    'ROOSFIELD': ["objvers = 'A'"],
    'RSDIOBJ': ["objvers = 'A'"],
    'RSDIOBJT': ["objvers = 'A'"],
    'ROOSOURCET': ["langu = 'E'"],
    'DD03T': ["ddlanguage = 'E'"],
    'DD04T': ["ddlanguage = 'E'"],
    'DD03L': ["fieldname NOT LIKE '.INCLUDE%'", "fieldname NOT LIKE 'INCLU-%'"],
}
```

---

## CSV Output Standards

### File Naming
```
{SYSTEM_ID}_{OBJECT_TYPE}_{YYYYMMDD}_{HHMMSS}.csv

Examples:
- BWP_INFOOBJECTS_20251230_143022.csv
- BWP_DATASOURCES_20251230_143055.csv
- BWP_TRANSFORMATIONS_20251230_143112.csv
```

### Format
- Encoding: UTF-8
- Delimiter: Semicolon (;)
- Header: First row = technical field names
- Quote character: Double-quote (") for values containing delimiter

### Example Output
```csv
INFOOBJECT;DESCRIPTION;TYPE;DATA_TYPE;LENGTH;DECIMALS
0MATERIAL;Material Number;CHA;CHAR;18;0
0CUSTOMER;Customer;CHA;NUMC;10;0
0AMOUNT;Amount in Document Currency;KYF;CURR;17;2
```

---

## Extraction Checklist

Before running extraction:
- [ ] Verify SAP system connection
- [ ] Check authorization for target tables (S_TABU_DIS)
- [ ] Estimate data volume (count before extract)
- [ ] Configure output path (GUI or app server)
- [ ] Set appropriate date range for history tables

After extraction:
- [ ] Verify row counts match expectations
- [ ] Check CSV encoding (open in Excel/text editor)
- [ ] Validate data types in output
- [ ] Document extraction in GOLDEN_COMMIT.yaml

---

## Error Handling

### Common Issues

| Error | Cause | Solution |
|-------|-------|----------|
| TIME_OUT dump | Full table scan | Add business filters, use FAE |
| "Table not found" | Missing schema | Check table exists in system |
| No data returned | Incorrect filters | Verify objvers='A' records exist |
| Encoding issues | Wrong codepage | Use UTF-8 (codepage 4103) |

### Authorization Requirements
- S_TABU_DIS: Display authorization for tables
- S_DATASET: File system access (for app server)
- S_GUI: SAP GUI download permission

---

**Last Updated**: 2025-12-30
**Version**: 1.0
