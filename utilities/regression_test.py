#!/usr/bin/env python
"""
Regression Testing Script - Compare Generated SQL with Golden Copies

CRITICAL: Golden copies are byte-level references from GOLDEN_COMMIT.yaml
- See pipelines/xml-to-sql/GOLDEN_COMMIT.yaml for tracking
- See pipelines/xml-to-sql/Target (SQL Scripts)/VALIDATED/ for golden SQL files

Usage:
    python regression_test.py                    # Normalized comparison (default)
    python regression_test.py --strict           # Byte-level comparison
    python regression_test.py --update-golden    # Update golden copies (requires HANA validation!)
"""
import sys
import argparse
from pathlib import Path

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "pipelines" / "xml-to-sql" / "src"))

from xml_to_sql.web.services.converter import convert_xml_to_sql
import difflib

# Base paths
BASE_DIR = Path(__file__).parent.parent / "pipelines" / "xml-to-sql"
SOURCE_DIR = BASE_DIR / "Source (XML Files)"
TARGET_DIR = BASE_DIR / "Target (SQL Scripts)"

# Test cases from GOLDEN_COMMIT.yaml: (xml_path, validated_sql_path, package_path)
TEST_CASES = [
    (
        "HANA 1.XX XML Views/ECC_ON_HANA/CV_CNCLD_EVNTS.xml",
        "VALIDATED/hana/CV_CNCLD_EVNTS.sql",
        "EYAL.EYAL_CTL"
    ),
    (
        "HANA 1.XX XML Views/BW_ON_HANA/CV_INVENTORY_ORDERS.xml",
        "VALIDATED/hana/CV_INVENTORY_ORDERS.sql",
        "Macabi_BI.EYAL.EYAL_CDS"
    ),
    (
        "HANA 1.XX XML Views/BW_ON_HANA/CV_PURCHASE_ORDERS.xml",
        "VALIDATED/hana/CV_PURCHASE_ORDERS.sql",
        "Macabi_BI.EYAL.EYAL_CDS"
    ),
    (
        "HANA 1.XX XML Views/BW_ON_HANA/CV_EQUIPMENT_STATUSES.xml",
        "VALIDATED/hana/CV_EQUIPMENT_STATUSES.sql",
        "Macabi_BI.EYAL.EYAL_CDS"
    ),
    (
        "HANA 1.XX XML Views/BW_ON_HANA/CV_TOP_PTHLGY.xml",
        "VALIDATED/hana/CV_TOP_PTHLGY.sql",
        "Macabi_BI.EYAL.EYAL_CDS"
    ),
    (
        "HANA 1.XX XML Views/ECC_ON_HANA/CV_MCM_CNTRL_Q51.xml",
        "VALIDATED/hana/CV_MCM_CNTRL_Q51.sql",
        ""  # No package - deferred BUG-002
    ),
    (
        "HANA 1.XX XML Views/ECC_ON_HANA/CV_MCM_CNTRL_REJECTED.xml",
        "VALIDATED/hana/CV_MCM_CNTRL_REJECTED.sql",
        ""
    ),
    (
        "HANA 1.XX XML Views/BW_ON_HANA/CV_UPRT_PTLG.xml",
        "VALIDATED/hana/CV_UPRT_PTLG.sql",
        "Macabi_BI.EYAL.EYAL_CDS"
    ),
    (
        "HANA 1.XX XML Views/BW_ON_HANA/CV_ELIG_TRANS_01.xml",
        "VALIDATED/hana/CV_ELIG_TRANS_01.sql",
        "Macabi_BI.Eligibility"
    ),
    (
        "HANA 1.XX XML Views/ECC_ON_HANA/CV_COMMACT_UNION.xml",
        "VALIDATED/hana/CV_COMMACT_UNION.sql",
        ""
    ),
    (
        "HANA 1.XX XML Views/BW_ON_HANA/CV_INVENTORY_STO.xml",
        "VALIDATED/hana/CV_INVENTORY_STO.sql",
        "Macabi_BI.EYAL.EYAL_CDS"
    ),
    (
        "HANA 1.XX XML Views/BW_ON_HANA/CV_PURCHASING_YASMIN.xml",
        "VALIDATED/hana/CV_PURCHASING_YASMIN.sql",
        "Macabi_BI.EYAL.EYAL_CDS"
    ),
]

def convert_xml(xml_path: str, package_path: str) -> tuple[str, list[str]]:
    """Convert XML to SQL."""
    full_path = SOURCE_DIR / xml_path
    with open(full_path, 'rb') as f:
        xml_content = f.read()

    # Convert using the web converter service
    result = convert_xml_to_sql(
        xml_content=xml_content,
        database_mode='hana',
        hana_version='2.0',
        hana_package=package_path,
        view_schema='SAPABAP1',
        schema_overrides={'ABAP': 'SAPABAP1'},
        auto_fix=False
    )

    if result.error:
        raise ValueError(result.error)

    return result.sql_content, result.warnings

def compare_sql_strict(generated: str, validated: str) -> tuple[bool, str, list[str]]:
    """
    Byte-level comparison (strict mode).

    Returns: (is_identical, status_message, diff_lines)
    """
    if generated == validated:
        return True, "IDENTICAL (byte-level)", []

    # Generate detailed diff
    diff = list(difflib.unified_diff(
        validated.splitlines(keepends=True),
        generated.splitlines(keepends=True),
        fromfile="Golden Copy",
        tofile="Generated",
        lineterm=''
    ))

    return False, f"DIFFERENT (byte-level)", diff


def compare_sql_normalized(generated: str, validated: str) -> tuple[bool, str, list[str]]:
    """
    Normalized comparison (ignores whitespace differences).

    Returns: (is_identical, status_message, diff_lines)
    """
    # Normalize whitespace for comparison
    gen_lines = [line.strip() for line in generated.split('\n') if line.strip()]
    val_lines = [line.strip() for line in validated.split('\n') if line.strip()]

    if gen_lines == val_lines:
        return True, "IDENTICAL (normalized)", []

    # Find differences
    diff_count = 0
    diff_lines = []
    for i, (gen_line, val_line) in enumerate(zip(gen_lines, val_lines)):
        if gen_line != val_line:
            diff_count += 1
            if diff_count <= 5:  # Show first 5 differences
                diff_lines.append(f"Line {i+1}:")
                diff_lines.append(f"  Golden:    {val_line[:100]}")
                diff_lines.append(f"  Generated: {gen_line[:100]}")

    if len(gen_lines) != len(val_lines):
        diff_lines.append(f"Line count: {len(val_lines)} vs {len(gen_lines)}")

    return False, f"DIFFERENT ({diff_count} lines differ)", diff_lines

def main():
    """Run regression tests."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Regression test: Compare generated SQL with golden copies"
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        help='Use byte-level comparison instead of normalized comparison'
    )
    parser.add_argument(
        '--update-golden',
        action='store_true',
        help='Update golden copies with newly generated SQL (requires HANA validation!)'
    )
    parser.add_argument(
        '--show-diffs',
        action='store_true',
        help='Show detailed diffs for failed comparisons'
    )

    args = parser.parse_args()

    # Warning for update-golden
    if args.update_golden:
        print("WARNING: You are about to update golden SQL copies")
        print("    This should ONLY be done after HANA Studio validation")
        response = input("    Are you sure? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            return 1

    print("=" * 80)
    print("REGRESSION TESTING - Validated XML Files (xsodus_converter)")
    print("=" * 80)
    print(f"Comparison mode: {'STRICT (byte-level)' if args.strict else 'NORMALIZED (whitespace-agnostic)'}")
    print(f"Base directory: {BASE_DIR}")
    print("=" * 80)
    print()

    results = []

    for xml_path, validated_sql_path, package_path in TEST_CASES:
        xml_name = Path(xml_path).name
        print(f"Testing: {xml_name}")
        if package_path:
            print(f"  Package: {package_path}")

        try:
            # Check if validated SQL exists
            full_validated_path = TARGET_DIR / validated_sql_path
            if not full_validated_path.exists():
                results.append((xml_name, False, "SKIPPED - no golden copy"))
                print(f"  Result: SKIPPED - no golden copy at {validated_sql_path}")
                print()
                continue

            # Convert XML
            generated_sql, warnings = convert_xml(xml_path, package_path)

            # Read validated SQL
            with open(full_validated_path, 'r', encoding='utf-8') as f:
                validated_sql = f.read()

            # Compare (choose method based on --strict flag)
            if args.strict:
                match, status, diff_lines = compare_sql_strict(generated_sql, validated_sql)
            else:
                match, status, diff_lines = compare_sql_normalized(generated_sql, validated_sql)

            results.append((xml_name, match, status))
            print(f"  Result: {'PASS' if match else 'FAIL'} - {status}")

            # Show diffs if requested and test failed
            if not match and args.show_diffs and diff_lines:
                print("  Differences:")
                for line in diff_lines[:20]:  # Show first 20 lines
                    print(f"    {line}")
                if len(diff_lines) > 20:
                    print(f"    ... {len(diff_lines) - 20} more lines")

            if warnings:
                print(f"  Warnings: {len(warnings)}")

            # Update golden copy if requested
            if args.update_golden:
                print(f"  Updating golden copy: {validated_sql_path}")
                full_validated_path.parent.mkdir(parents=True, exist_ok=True)
                with open(full_validated_path, 'w', encoding='utf-8') as f:
                    f.write(generated_sql)
                print("  Golden copy updated")

        except Exception as e:
            results.append((xml_name, False, f"ERROR: {str(e)}"))
            print(f"  Result: ERROR: {str(e)}")

        print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    passed = sum(1 for _, match, _ in results if match)
    total = len(results)

    for xml_name, match, status in results:
        marker = "PASS" if match else "FAIL"
        print(f"  [{marker}] {xml_name}: {status}")

    print()
    print(f"PASSED: {passed}/{total} ({passed*100//total if total > 0 else 0}%)")
    print("=" * 80)

    if passed < total:
        print()
        print("REGRESSION DETECTED - Generated SQL differs from golden copies")
        print("    1. Review differences with --show-diffs flag")
        print("    2. If changes are intentional and HANA-validated:")
        print("       python utilities/regression_test.py --update-golden")
        print("    3. Update GOLDEN_COMMIT.yaml with new commit hash")
        print("    4. Commit both updated SQL files and GOLDEN_COMMIT.yaml")

    return 0 if passed == total else 1

if __name__ == '__main__':
    sys.exit(main())
