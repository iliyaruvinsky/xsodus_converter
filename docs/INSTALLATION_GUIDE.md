# Installation Guide for xsodus_converter (XML to SQL Monorepo)

This guide will help you install and run the xsodus_converter application on your local machine.

## Prerequisites

Before installing, ensure you have:

- **Python 3.11 or higher** - [Download Python](https://www.python.org/downloads/)
- **Node.js 18 or higher** (for frontend) - [Download Node.js](https://nodejs.org/)
- **Git** (for pulling from repository) - [Download Git](https://git-scm.com/downloads)

## Installation Steps

### Step 1: Clone the Repository

```powershell
cd "C:\Users\iliya\OneDrive\Desktop\X2S"
git clone https://github.com/your-repo/xsodus_converter.git
cd xsodus_converter
```

### Step 2: Install Core Package

```powershell
cd core
pip install -e .
cd ..
```

### Step 3: Install XML-to-SQL Pipeline

```powershell
cd pipelines\xml-to-sql
pip install -e .
```

### Step 4: Set Up Frontend (Optional, if building from source)

```powershell
cd web_frontend
npm install
npm run build
cd ..
```

### Step 5: Create Configuration File

```powershell
copy config.example.yaml config.yaml
# Edit config.yaml with your settings
```

### Step 6: Start the Server

```powershell
# Option 1: Use utility script (recommended)
cd "C:\Users\iliya\OneDrive\Desktop\X2S\xsodus_converter"
utilities\restart_server.bat

# Option 2: Manual start
cd pipelines\xml-to-sql
python -m uvicorn xml_to_sql.web.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 7: Access the Web Interface

Open your browser: `http://localhost:8000`

## Configuration

### Basic Configuration (config.yaml)

```yaml
defaults:
  client: "PROD"
  language: "EN"
  database_mode: "hana"    # "hana" or "snowflake"
  hana_version: "2.0"      # HANA version
  view_schema: "_SYS_BIC"  # Default schema for views

paths:
  source: "Source (XML Files)"
  target: "Target (SQL Scripts)"

schema_overrides:
  ABAP: "SAPABAP1"         # Map XML schema to actual database schema
```

### Web Interface Configuration

The web interface allows you to configure per-conversion settings:
- **Database Mode**: HANA or Snowflake
- **HANA Package Path**: For CV-to-CV references
- **View Schema**: Where views are created (default: _SYS_BIC)
- **Target Schema**: Where tables are located (default: SAPABAP1)

## Running the Application

### Start the Web Server

```powershell
# From project root
utilities\restart_server.bat
```

The server starts on `http://localhost:8000`.

### Using the Web Interface

1. Open `http://localhost:8000` in your browser
2. Upload a SAP HANA calculation view XML file
3. Configure HANA settings (package path, schemas)
4. Click "Convert"
5. Review the generated SQL
6. Copy SQL or view auto-saved file: `LATEST_SQL_FROM_DB.txt`

### Using the CLI

```powershell
cd pipelines\xml-to-sql

# Convert a single XML file (HANA mode)
python -m xml_to_sql.cli.app convert --config config.yaml --mode hana --file "path/to/file.xml"

# List available XMLs
python -m xml_to_sql.cli.app list --config config.yaml
```

## Project Structure

```
xsodus_converter/
├── core/                           # Shared core modules
│   └── src/x2s_core/               # Parser, database, models
├── pipelines/
│   └── xml-to-sql/                 # Main XML-to-SQL converter
│       ├── src/xml_to_sql/         # Source code
│       │   ├── sql/                # Renderer, function translator
│       │   ├── web/                # FastAPI backend
│       │   └── catalog/            # Function/pattern catalogs
│       ├── web_frontend/           # React frontend
│       ├── catalog/hana/           # HANA-specific catalogs
│       └── docs/                   # Pipeline-specific docs
├── utilities/                      # Helper scripts
│   └── restart_server.bat          # Server restart utility
├── docs/                           # General documentation
└── Source (XML Files)/             # Input XML files
```

## Troubleshooting

### Port 8000 in Use

```powershell
# Kill existing Python processes
taskkill /F /IM python.exe

# Or use restart script which handles this
utilities\restart_server.bat
```

### Module Not Found Errors

```powershell
# Reinstall both packages
cd core && pip install -e .
cd ..\pipelines\xml-to-sql && pip install -e .
```

### Changes Not Taking Effect

```powershell
# Clear cache and reinstall
utilities\restart_server.bat
```

This script:
1. Kills all Python processes
2. Clears `__pycache__` directories
3. Reinstalls packages
4. Starts fresh server

### SQLite Database Errors

```powershell
# Delete databases to reset
del pipelines\xml-to-sql\conversions.db
del pipelines\xml-to-sql\package_mappings.db
```

## Next Steps

- **Quick Start**: See [QUICK_START.md](QUICK_START.md)
- **Testing Procedure**: See [pipelines/xml-to-sql/docs/procedures/3_TESTING_PROCEDURE.md](../pipelines/xml-to-sql/docs/procedures/3_TESTING_PROCEDURE.md)
- **Bug Tracking**: See [pipelines/xml-to-sql/docs/BUG_TRACKER.md](../pipelines/xml-to-sql/docs/BUG_TRACKER.md)
- **LLM Handover**: See [llm_handover.md](llm_handover.md)

## Support

For issues or questions:
- Check documentation in `docs/` and `pipelines/xml-to-sql/docs/`
- Review BUG_TRACKER.md for known issues
- Check SOLVED_BUGS.md for past solutions
