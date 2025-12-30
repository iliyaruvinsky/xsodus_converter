"""CLI helper for package path management.

This module provides CLI commands to work with HANA package mappings:
- Lookup package for a CV name
- List all CVs in a package
- Search for CVs
- Validate package mappings
- Convert XML with automatic package lookup
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from ..package_mapper import get_mapper


def lookup_package(cv_name: str) -> int:
    """Lookup package for a Calculation View.

    Args:
        cv_name: Name of the Calculation View

    Returns:
        Exit code (0 for success, 1 for not found)
    """
    mapper = get_mapper()
    package = mapper.get_package(cv_name)

    if package:
        print(f"✅ {cv_name}")
        print(f"   Package: {package}")
        return 0
    else:
        print(f"❌ {cv_name}")
        print(f"   NOT FOUND in package mappings")
        print(f"\n   Total mapped CVs: {mapper.total_cvs}")
        print(f"   Available packages: {mapper.total_packages}")
        return 1


def list_cvs_in_package(package: str) -> int:
    """List all Calculation Views in a package.

    Args:
        package: Package name

    Returns:
        Exit code (0 for success)
    """
    mapper = get_mapper()
    cvs = mapper.get_cvs_in_package(package)

    print(f"📦 Package: {package}")
    print(f"   Total CVs: {len(cvs)}")

    if cvs:
        print("\n   Calculation Views:")
        for cv in sorted(cvs):
            print(f"   - {cv}")
    else:
        print("\n   ⚠️ No CVs found in this package")
        print("\n   Available packages:")
        for pkg in mapper.get_all_packages()[:10]:
            print(f"   - {pkg}")

    return 0


def search_cvs(pattern: str) -> int:
    """Search for Calculation Views by pattern.

    Args:
        pattern: Search pattern (case-insensitive)

    Returns:
        Exit code (0 for success)
    """
    mapper = get_mapper()
    results = mapper.search_cv(pattern)

    print(f"🔍 Search: '{pattern}'")
    print(f"   Results: {len(results)}")

    if results:
        print("\n   Matches:")
        for cv, pkg in results:
            print(f"   {cv:40} → {pkg}")
    else:
        print("\n   ⚠️ No matches found")

    return 0


def list_all_packages() -> int:
    """List all packages with CV counts.

    Returns:
        Exit code (0 for success)
    """
    mapper = get_mapper()
    packages = mapper.get_all_packages()

    print(f"📦 All Packages ({len(packages)} total)")
    print()

    for pkg in packages:
        cv_count = len(mapper.get_cvs_in_package(pkg))
        print(f"   {pkg:45} ({cv_count:3} CVs)")

    return 0


def show_mapping_info() -> int:
    """Show package mapping metadata.

    Returns:
        Exit code (0 for success)
    """
    mapper = get_mapper()
    metadata = mapper.get_metadata()

    print("📊 Package Mapping Information")
    print()
    print(f"   Source:       {metadata.get('_source')}")
    print(f"   Generated:    {metadata.get('_generated_date')}")
    print(f"   Instance:     {metadata.get('_instance')}")
    print(f"   Total CVs:    {mapper.total_cvs}")
    print(f"   Total Packages: {mapper.total_packages}")

    if '_note' in metadata:
        print(f"\n   Note: {metadata['_note']}")

    return 0


def validate_cv_package(cv_name: str, expected_package: str) -> int:
    """Validate that a CV is mapped to the expected package.

    Args:
        cv_name: Name of the Calculation View
        expected_package: Expected package path

    Returns:
        Exit code (0 for valid, 1 for invalid)
    """
    mapper = get_mapper()
    actual_package = mapper.get_package(cv_name)

    print(f"🔍 Validating: {cv_name}")
    print(f"   Expected: {expected_package}")
    print(f"   Actual:   {actual_package or 'NOT FOUND'}")

    if actual_package is None:
        print(f"\n   ❌ CV not found in package mappings")
        return 1

    if actual_package.strip() == expected_package.strip():
        print(f"\n   ✅ Package mapping is correct")
        return 0
    else:
        print(f"\n   ❌ Package mapping mismatch")
        return 1


def main():
    """Main entry point for CLI commands."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m xml_to_sql.cli.package_helper lookup <cv_name>")
        print("  python -m xml_to_sql.cli.package_helper list <package>")
        print("  python -m xml_to_sql.cli.package_helper search <pattern>")
        print("  python -m xml_to_sql.cli.package_helper packages")
        print("  python -m xml_to_sql.cli.package_helper info")
        print("  python -m xml_to_sql.cli.package_helper validate <cv_name> <expected_package>")
        return 1

    command = sys.argv[1]

    if command == "lookup" and len(sys.argv) >= 3:
        return lookup_package(sys.argv[2])
    elif command == "list" and len(sys.argv) >= 3:
        return list_cvs_in_package(sys.argv[2])
    elif command == "search" and len(sys.argv) >= 3:
        return search_cvs(sys.argv[2])
    elif command == "packages":
        return list_all_packages()
    elif command == "info":
        return show_mapping_info()
    elif command == "validate" and len(sys.argv) >= 4:
        return validate_cv_package(sys.argv[2], sys.argv[3])
    else:
        print(f"Unknown command or missing arguments: {command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
