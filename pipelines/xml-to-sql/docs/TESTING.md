# Testing Instructions

> **For Developers:** This guide covers testing procedures for the XML to SQL converter tool.

## Prerequisites

1. **Python 3.11+** installed
2. **Virtual environment** activated (if using one)
3. **Project dependencies** installed

> **Note:** For systematic error investigation when HANA SQL fails, see [SQL_ERROR_INVESTIGATION_PROCEDURE.md](../SQL_ERROR_INVESTIGATION_PROCEDURE.md) in the project root.

## Step 1: Verify Installation

```powershell
# Navigate to project directory
cd "C:\Users\USER\Google Drive\SW_PLATFORM\15. AI\MY_LATEST_FILES\EXODUS\XML to SQL"

# Activate virtual environment (if using one)
.\venv\Scripts\Activate.ps1

# Verify installation
venv\Scripts\python -m pytest --version
```

## Step 2: Run Unit Tests

```powershell
# Run all tests
venv\Scripts\python -m pytest -v

# Run specific test file
venv\Scripts\python -m pytest tests/test_sql_renderer.py -v

# Run with coverage (if pytest-cov installed)
venv\Scripts\python -m pytest --cov=src/xml_to_sql --cov-report=html
```

**Expected Result:** All 23 tests should pass.

## Step 3: Create Configuration File

1. Copy the example config:
   ```powershell
   Copy-Item config.example.yaml config.yaml
   ```

2. Edit `config.yaml` to match your environment:
   ```yaml
   defaults:
     client: "PROD"
     language: "EN"

   paths:
     source: "Source (XML Files)"
     target: "Target (SQL Scripts)"

   schema_overrides:
     # Override schema names if needed
     # SAPK5D: "PRODUCTION_SCHEMA"

   currency:
     udf_name: "CONVERT_CURRENCY"
     rates_table: "EXCHANGE_RATES"
     schema: "UTILITY"

   scenarios:
     - id: "Sold_Materials"
       output: "V_C_SOLD_MATERIALS"
       enabled: true
       overrides:
         client: "100"
   ```

## Step 4: Test CLI - List Scenarios

```powershell
# List all scenarios in config
venv\Scripts\python -m xml_to_sql.cli.app list --config config.yaml

# Or using the entry point (if installed)
xml-to-sql list --config config.yaml
```

**Expected Result:** List of scenarios with their status and source paths.

## Step 5: Test CLI - Dry Run (List Only)

```powershell
# See what would be processed without generating SQL
venv\Scripts\python -m xml_to_sql.cli.app convert --config config.yaml --list-only
```

**Expected Result:** Shows planned conversions without executing them.

## Step 6: Test CLI - Convert Single Scenario

```powershell
# Convert a specific scenario
venv\Scripts\python -m xml_to_sql.cli.app convert --config config.yaml --scenario Sold_Materials

# Or convert multiple scenarios
venv\Scripts\python -m xml_to_sql.cli.app convert --config config.yaml --scenario Sold_Materials --scenario SALES_BOM
```

**Expected Result:**
- SQL file generated in `Target (SQL Scripts)/`
- Console output showing parsing statistics
- Success message with file path

## Step 7: Test CLI - Convert All Enabled Scenarios

```powershell
# Convert all enabled scenarios in config
venv\Scripts\python -m xml_to_sql.cli.app convert --config config.yaml
```

**Expected Result:** SQL files generated for all enabled scenarios.

## Step 8: Verify Generated SQL Files

1. **Check output directory:**
   ```powershell
   Get-ChildItem "Target (SQL Scripts)" -Filter *.sql
   ```

2. **Inspect a generated SQL file:**
   ```powershell
   Get-Content "Target (SQL Scripts)\V_C_SOLD_MATERIALS.sql" | Select-Object -First 50
   ```

3. **Verify SQL structure:**
   - Should start with `WITH` clause (if CTEs present)
   - Should contain `SELECT` statements
   - Should reference source tables/schemas
   - Should have proper CTE aliases

## Step 9: Test with Different XML Files

Test each sample XML file individually:

```powershell
# Test Sold_Materials
venv\Scripts\python -m xml_to_sql.cli.app convert --config config.yaml --scenario Sold_Materials

# Test SALES_BOM
venv\Scripts\python -m xml_to_sql.cli.app convert --config config.yaml --scenario SALES_BOM

# Test KMDM_Materials (contains UNION)
venv\Scripts\python -m xml_to_sql.cli.app convert --config config.yaml --scenario KMDM_Materials

# Test Recently_created_products (contains multiple unions)
venv\Scripts\python -m xml_to_sql.cli.app convert --config config.yaml --scenario Recently_created_products
```

## Step 10: Validate SQL Syntax (Optional)

If you have Snowflake access or SQL validator:

```powershell
# Check SQL files for basic syntax issues
# (This requires a SQL validator tool or Snowflake connection)
```

## Step 11: Test Error Handling

1. **Test with missing XML file:**
   ```yaml
   # In config.yaml, add a scenario pointing to non-existent file
   scenarios:
     - id: "NonExistent"
       source: "Missing_File.XML"
       enabled: true
   ```
   ```powershell
   venv\Scripts\python -m xml_to_sql.cli.app convert --config config.yaml --scenario NonExistent
   ```
   **Expected:** Error message indicating file not found.

2. **Test with invalid config:**
   ```powershell
   # Create invalid config.yaml with syntax errors
   venv\Scripts\python -m xml_to_sql.cli.app convert --config config.yaml
   ```
   **Expected:** Clear error message about config issues.

## Step 12: Test Function Translation

Verify HANA function translation works:

1. **Check for IF → IFF translation:**
   ```powershell
   # Look for IFF in generated SQL
   Select-String -Path "Target (SQL Scripts)\*.sql" -Pattern "IFF"
   ```

2. **Check for string concatenation:**
   ```powershell
   # Look for || operator (Snowflake concatenation)
   Select-String -Path "Target (SQL Scripts)\*.sql" -Pattern "\|\|"
   ```

## Step 13: Test Union Support

Verify UNION nodes are rendered correctly:

```powershell
# KMDM_Materials contains UNION nodes
venv\Scripts\python -m xml_to_sql.cli.app convert --config config.yaml --scenario KMDM_Materials

# Check generated SQL for UNION ALL
Get-Content "Target (SQL Scripts)\V_C_KMDM_MATERIALS.sql" | Select-String -Pattern "UNION"
```

**Expected:** SQL should contain `UNION ALL` statements.

## Step 14: Test Currency Configuration

1. **With currency UDF configured:**
   ```yaml
   currency:
     udf_name: "CONVERT_CURRENCY"
     schema: "UTILITY"
   ```
   Generated SQL should reference the UDF when currency conversion is needed.

2. **Without currency config:**
   ```yaml
   currency: {}
   ```
   Should generate warnings but still produce SQL.

## Step 15: Regression Test - All XML Samples

Run comprehensive regression test:

```powershell
# Run pytest with all XML sample tests
venv\Scripts\python -m pytest tests/test_sql_renderer.py::test_render_all_xml_samples -v
```

**Expected:** All 7 XML samples should generate valid SQL.

## Step 16: Performance Test (Optional)

Test with larger files:

```powershell
# Time the conversion
Measure-Command {
    venv\Scripts\python -m xml_to_sql.cli.app convert --config config.yaml
}
```

## Troubleshooting

### Issue: Import errors
**Solution:** Ensure virtual environment is activated and dependencies are installed:
```powershell
.\venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

### Issue: XML file not found
**Solution:** Verify file paths in config.yaml match actual file locations.

### Issue: SQL generation fails
**Solution:** Check console output for warnings. Review parser logs for unsupported constructs.

### Issue: Tests fail
**Solution:** 
```powershell
# Run with verbose output
venv\Scripts\python -m pytest -vv

# Run specific failing test
venv\Scripts\python -m pytest tests/test_sql_renderer.py::test_name -vv
```

## Expected Test Results

When all tests pass, you should see:
```
============================= test session starts =============================
collected 23 items

tests/test_config_loader.py::test_load_config_with_defaults PASSED
tests/test_config_loader.py::test_select_scenarios_filters_disabled PASSED
tests/test_parser.py::test_parse_scenario_smoke[Sold_Materials.XML] PASSED
tests/test_parser.py::test_parse_scenario_smoke[SALES_BOM.XML] PASSED
tests/test_parser.py::test_parse_scenario_smoke[Recently_created_products.XML] PASSED
tests/test_parser.py::test_parse_scenario_variables_and_logical_model PASSED
tests/test_skeleton.py::test_import_package PASSED
tests/test_sql_renderer.py::test_render_simple_projection PASSED
tests/test_sql_renderer.py::test_render_projection_with_filter PASSED
tests/test_sql_renderer.py::test_render_join PASSED
tests/test_sql_renderer.py::test_render_aggregation PASSED
tests/test_sql_renderer.py::test_render_integration_sold_materials PASSED
tests/test_sql_renderer.py::test_render_all_xml_samples[...] PASSED (7 tests)
tests/test_sql_renderer.py::test_render_union_node PASSED
tests/test_sql_renderer.py::test_render_with_currency_config PASSED
tests/test_sql_renderer.py::test_function_translation_if_statement PASSED
tests/test_sql_renderer.py::test_function_translation_string_concatenation PASSED

============================= 23 passed in 0.15s ==============================
```

## Next Steps

After successful testing:
1. Review generated SQL files for correctness
2. Test SQL execution in Snowflake (if available)
3. Adjust config.yaml for production settings
4. Document any issues or edge cases found

