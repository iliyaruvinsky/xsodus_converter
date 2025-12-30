# SQL to ABAP Pipeline

Converts SQL (with CTE structure) to Pure ABAP code, portable across any SAP database.

## Quick Start

1. **Generate SQL** using the xml-to-sql pipeline
2. **Generate ABAP** via the UI "ABAP" tab → "Generate ABAP" button
3. **Download** the `.abap` file
4. **Upload** to SAP via SE38 or ADT
5. **Run** syntax check (Ctrl+F2)

## Pipeline Flow

```
XML (Calculation View) → SQL (with CTEs) → Pure ABAP
```

## Generation Mode: Pure ABAP

This pipeline generates **Pure ABAP** (not EXEC SQL):
- Uses native SELECT statements
- Uses FOR ALL ENTRIES for JOINs
- Works on ANY SAP database (HANA, Oracle, SQL Server, MaxDB, etc.)

## Documentation

| Document | Description |
|----------|-------------|
| [PURE_ABAP_CONVERSION_RULES.md](rules/pure/PURE_ABAP_CONVERSION_RULES.md) | SQL→ABAP transformation rules |
| [BUG_TRACKER.md](docs/BUG_TRACKER.md) | Active bug tracking |
| [SOLVED_BUGS.md](docs/SOLVED_BUGS.md) | Solved bugs archive |
| [GOLDEN_COMMIT.yaml](GOLDEN_COMMIT.yaml) | Validated baseline tracking |

## Code Location

The Pure ABAP generator code resides in the xml-to-sql pipeline:

```
pipelines/xml-to-sql/src/xml_to_sql/abap/
├── __init__.py          # Exports both modes
├── sql_to_abap.py       # Main converter (SQL CTEs → ABAP)
├── pure_generator.py    # Pure ABAP code generation
└── generator.py         # EXEC SQL mode (HANA-only, not used)
```

## API Endpoints

- `POST /api/generate-abap/{conversion_id}` - Generate ABAP on demand
- `GET /api/download/{conversion_id}/abap` - Download .abap file

## Folder Structure

```
sql-to-abap/
├── README.md              # This file
├── GOLDEN_COMMIT.yaml     # Baseline tracking (SE38 validated)
├── docs/
│   ├── BUG_TRACKER.md     # Active bugs
│   └── SOLVED_BUGS.md     # Solved bugs
├── rules/
│   ├── native/            # Reserved for EXEC SQL rules
│   └── pure/
│       └── PURE_ABAP_CONVERSION_RULES.md
├── src/                   # Reserved for future ABAP-specific code
├── tests/                 # Reserved for tests
├── ui/                    # Reserved for UI components
└── VALIDATED/             # SE38-validated ABAP programs
```

## Validation Workflow

1. Generate ABAP from validated SQL
2. Upload to SAP (SE38 or ADT)
3. Syntax check (Ctrl+F2)
4. Execute if passes (F8)
5. Document in GOLDEN_COMMIT.yaml

---

**Last Updated**: 2025-12-10
