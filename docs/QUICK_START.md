# Quick Start Guide - xsodus_converter Monorepo

## 5-Minute Setup

### Step 1: Navigate to Project
```powershell
cd "C:\Users\iliya\OneDrive\Desktop\X2S\xsodus_converter"
```

### Step 2: Install Dependencies
```powershell
# Install core package
cd core
pip install -e .

# Install xml-to-sql pipeline
cd ..\pipelines\xml-to-sql
pip install -e .
```

### Step 3: Create Config (if needed)
```powershell
cd pipelines\xml-to-sql
copy config.example.yaml config.yaml
```

### Step 4: Start Web Server
```powershell
# Option 1: Use utility script (recommended)
cd "C:\Users\iliya\OneDrive\Desktop\X2S\xsodus_converter"
utilities\restart_server.bat

# Option 2: Manual start
cd pipelines\xml-to-sql
python -m uvicorn xml_to_sql.web.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 5: Access Web UI
Open browser: http://localhost:8000

1. Select XML file from dropdown or upload
2. Configure HANA options (package path, schemas)
3. Click "Convert"
4. Copy generated SQL from output

**Done!** The converted SQL is also auto-saved to:
```
C:\Users\iliya\OneDrive\Desktop\X2S\xsodus_converter\LATEST_SQL_FROM_DB.txt
```

## Common Operations

### Using the Web UI
- **Upload XML**: Drag & drop or browse
- **Select Instance**: Choose BW_ON_HANA, ECC_ON_HANA, etc.
- **Configure HANA Package**: For CV-to-CV references
- **View/Copy Output**: Generated SQL appears in output panel

### Using the CLI
```powershell
cd pipelines\xml-to-sql

# Convert single XML (HANA mode)
python -m xml_to_sql.cli.app convert \
  --config config.yaml \
  --mode hana \
  --file "Source (XML Files)/CV_EXAMPLE.xml"

# List available XMLs
python -m xml_to_sql.cli.app list --config config.yaml
```

## Project Structure
```
xsodus_converter/
├── core/                    # Shared parsing/database modules
├── pipelines/
│   └── xml-to-sql/          # Main XML to SQL converter
│       ├── src/xml_to_sql/  # Source code
│       ├── web_frontend/    # React frontend
│       └── config.yaml      # Configuration
├── utilities/               # Helper scripts
│   └── restart_server.bat   # Server restart utility
└── docs/                    # Documentation
```

## Next Steps

- **Testing XML conversions:** See [pipelines/xml-to-sql/docs/procedures/3_TESTING_PROCEDURE.md](../pipelines/xml-to-sql/docs/procedures/3_TESTING_PROCEDURE.md)
- **Bug tracking:** See [pipelines/xml-to-sql/docs/BUG_TRACKER.md](../pipelines/xml-to-sql/docs/BUG_TRACKER.md)
- **LLM handover:** See [docs/llm_handover.md](llm_handover.md)

## Troubleshooting

### Port 8000 in use
```powershell
# Kill existing process
taskkill /F /IM python.exe
# Or use the restart script which handles this automatically
utilities\restart_server.bat
```

### Module not found errors
```powershell
# Reinstall packages
cd core && pip install -e .
cd ..\pipelines\xml-to-sql && pip install -e .
```

### Changes not taking effect
```powershell
# Clear cache and restart
utilities\restart_server.bat
```
