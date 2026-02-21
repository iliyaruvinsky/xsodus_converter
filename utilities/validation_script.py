#!/usr/bin/env python3
"""
Xsodus Converter - Documentation & Code Alignment Validation Script

This script validates consistency between documentation and code across the project.
Run this before commits to ensure alignment for LLM-based development.

Checks performed:
1. Referenced files exist
2. API routes match frontend calls
3. Module exports match imports
4. Bug IDs are consistent
5. Path references are correct
6. Duplicate content detection

Usage:
    python utilities/validation_script.py [--fix] [--verbose]
"""

import os
import re
import yaml
import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Optional


class ValidationResult:
    """Container for validation results."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

    def add_error(self, msg: str):
        self.errors.append(msg)

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def add_info(self, msg: str):
        self.info.append(msg)

    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        return f"Errors: {len(self.errors)}, Warnings: {len(self.warnings)}, Info: {len(self.info)}"


class XsodusValidator:
    """Main validator class for Xsodus Converter project."""

    def __init__(self, root_path: str = None):
        if root_path:
            self.root = Path(root_path)
        else:
            # Auto-detect project root
            self.root = Path(__file__).parent.parent

        self.xml_to_sql_path = self.root / "pipelines" / "xml-to-sql"
        self.sql_to_abap_path = self.root / "pipelines" / "sql-to-abap"
        self.results = ValidationResult()

    def validate_all(self) -> ValidationResult:
        """Run all validation checks."""
        print("=" * 60)
        print("XSODUS CONVERTER VALIDATION")
        print("=" * 60)

        self._check_file_references()
        self._check_api_alignment()
        self._check_module_exports()
        self._check_bug_id_consistency()
        self._check_path_consistency()
        self._check_duplicate_content()
        self._check_golden_commit_alignment()

        return self.results

    def _check_file_references(self):
        """Check that files referenced in documentation exist."""
        print("\n[1] Checking file references in documentation...")

        # Files to check for references
        doc_files = [
            self.root / ".claude" / "CLAUDE.md",
            self.root / ".claude" / "MANDATORY_PROCEDURES.md",
            self.xml_to_sql_path / "docs" / "BUG_TRACKER.md",
            self.xml_to_sql_path / "docs" / "SOLVED_BUGS.md",
            self.sql_to_abap_path / "README.md",
        ]

        # Patterns to find file references
        patterns = [
            r'`([^`]+\.(?:py|yaml|md|tsx|jsx|js|sql))`',  # backtick paths
            r'\[([^\]]+)\]\(([^)]+\.(?:py|yaml|md|tsx|jsx|js))\)',  # markdown links
            r'File:\s*`?([^\s`]+\.(?:py|yaml|md|tsx|jsx|js))`?',  # "File: path" patterns
        ]

        for doc_file in doc_files:
            if not doc_file.exists():
                self.results.add_warning(f"Doc file not found: {doc_file.relative_to(self.root)}")
                continue

            content = doc_file.read_text(encoding='utf-8', errors='ignore')

            for pattern in patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    # Handle tuple matches from markdown links
                    ref_path = match[-1] if isinstance(match, tuple) else match

                    # Skip URLs, anchors, and short filenames (just basename)
                    if ref_path.startswith('http') or ref_path.startswith('#'):
                        continue

                    # Skip short filenames that are just basename references (e.g., "renderer.py")
                    # These are typically informal references, not path references
                    if '/' not in ref_path and '\\' not in ref_path:
                        continue

                    # Normalize the path
                    if ref_path.startswith('src/'):
                        check_path = self.xml_to_sql_path / ref_path
                    elif ref_path.startswith('pipelines/'):
                        check_path = self.root / ref_path
                    elif ref_path.startswith('utilities/'):
                        check_path = self.root / ref_path
                    elif ref_path.startswith('.claude/'):
                        check_path = self.root / ref_path
                    elif ref_path.startswith('xml2sql/'):
                        # Old path format - check equivalent new path
                        new_ref = ref_path.replace('xml2sql/', 'pipelines/xml-to-sql/')
                        check_path = self.root / new_ref
                        self.results.add_warning(
                            f"Old path format in {doc_file.name}: '{ref_path}' -> should be '{new_ref}'"
                        )
                    else:
                        # Try relative to doc file first, then ROOT
                        check_path = doc_file.parent / ref_path
                        if not check_path.exists():
                            # Also try from ROOT for docs/ paths
                            check_path = self.root / ref_path

                    if not check_path.exists() and '::' not in ref_path:  # Skip function refs
                        self.results.add_warning(
                            f"Referenced file not found: '{ref_path}' in {doc_file.name}"
                        )

        self.results.add_info(f"File reference check complete")

    def _check_api_alignment(self):
        """Check that API routes match frontend calls."""
        print("\n[2] Checking API route alignment...")

        routes_file = self.xml_to_sql_path / "src" / "xml_to_sql" / "web" / "api" / "routes.py"
        api_file = self.xml_to_sql_path / "web_frontend" / "src" / "services" / "api.js"

        if not routes_file.exists():
            self.results.add_error(f"Backend routes file not found: {routes_file}")
            return
        if not api_file.exists():
            self.results.add_error(f"Frontend API file not found: {api_file}")
            return

        # Extract backend routes
        routes_content = routes_file.read_text(encoding='utf-8')
        backend_routes = set()

        # Match @router.get/post/delete("/path")
        route_pattern = r'@router\.(get|post|delete|put)\(["\']([^"\']+)["\']'
        for match in re.finditer(route_pattern, routes_content):
            method, path = match.groups()
            backend_routes.add((method.upper(), path))

        # Extract frontend API calls
        api_content = api_file.read_text(encoding='utf-8')
        frontend_calls = set()

        # Match api.get/post/delete('/path')
        call_pattern = r'api\.(get|post|delete|put)\([`"\']([^`"\']+)[`"\']'
        for match in re.finditer(call_pattern, api_content):
            method, path = match.groups()
            # Normalize path variables
            path = re.sub(r'\$\{[^}]+\}', '{id}', path)
            frontend_calls.add((method.upper(), path))

        # Also check fetch calls
        fetch_pattern = r'fetch\([`"\']([^`"\']+)[`"\'],\s*\{[^}]*method:\s*["\'](\w+)["\']'
        for match in re.finditer(fetch_pattern, api_content):
            url, method = match.groups()
            # Extract path from URL
            path_match = re.search(r'/api(/[^"\'`]+)', url)
            if path_match:
                path = path_match.group(1)
                path = re.sub(r'\$\{[^}]+\}', '{id}', path)
                frontend_calls.add((method.upper(), path))

        # Compare
        backend_normalized = {(m, p.replace('{conversion_id}', '{id}').replace('{batch_id}', '{id}').replace('{instance_id}', '{id}')) for m, p in backend_routes}
        frontend_normalized = {(m, p.replace('{id}', '{id}')) for m, p in frontend_calls}

        missing_in_frontend = backend_normalized - frontend_normalized
        if missing_in_frontend:
            for method, path in missing_in_frontend:
                self.results.add_info(f"Backend route not used in frontend: {method} {path}")

        self.results.add_info(f"API alignment check complete: {len(backend_routes)} backend, {len(frontend_calls)} frontend")

    def _check_module_exports(self):
        """Check that module exports match what's imported elsewhere."""
        print("\n[3] Checking module exports...")

        # Check ABAP module exports
        abap_init = self.xml_to_sql_path / "src" / "xml_to_sql" / "abap" / "__init__.py"
        routes_file = self.xml_to_sql_path / "src" / "xml_to_sql" / "web" / "api" / "routes.py"

        if abap_init.exists() and routes_file.exists():
            init_content = abap_init.read_text(encoding='utf-8')
            routes_content = routes_file.read_text(encoding='utf-8')

            # Find what's exported from abap module
            exports = set(re.findall(r'from \.[\w.]+ import (\w+)', init_content))

            # Find what's imported in routes
            imports = set(re.findall(r'from \.\.\.abap import (\w+)', routes_content))

            missing_exports = imports - exports
            if missing_exports:
                for func in missing_exports:
                    self.results.add_error(
                        f"Function '{func}' imported in routes.py but not exported from abap/__init__.py"
                    )

        self.results.add_info("Module export check complete")

    def _check_bug_id_consistency(self):
        """Check that bug IDs are consistent across documentation."""
        print("\n[4] Checking bug ID consistency...")

        bug_tracker = self.xml_to_sql_path / "docs" / "BUG_TRACKER.md"
        solved_bugs = self.xml_to_sql_path / "docs" / "SOLVED_BUGS.md"

        if not bug_tracker.exists() or not solved_bugs.exists():
            self.results.add_warning("Bug tracking files not found")
            return

        tracker_content = bug_tracker.read_text(encoding='utf-8')
        solved_content = solved_bugs.read_text(encoding='utf-8')

        # Find all BUG-XXX references
        tracker_bugs = set(re.findall(r'BUG-(\d+)', tracker_content))
        solved_bugs_ids = set(re.findall(r'BUG-(\d+)', solved_content))
        solved_ids = set(re.findall(r'SOLVED-(\d+)', solved_content))

        # Check for duplicates in the same file
        tracker_duplicates = [bug for bug in tracker_bugs if tracker_content.count(f'### BUG-{bug}') > 1]
        if tracker_duplicates:
            self.results.add_warning(f"Duplicate bug entries in BUG_TRACKER.md: BUG-{', BUG-'.join(tracker_duplicates)}")

        # Check for bugs in both tracker and solved (should be moved)
        in_both = tracker_bugs & solved_bugs_ids
        if in_both:
            for bug in in_both:
                # Only warn if it's in the active section, not just referenced
                if f'### BUG-{bug}' in tracker_content:
                    self.results.add_warning(f"BUG-{bug} appears in both BUG_TRACKER.md and SOLVED_BUGS.md")

        self.results.add_info(f"Bug ID check complete: {len(tracker_bugs)} in tracker, {len(solved_bugs_ids)} in solved")

    def _check_path_consistency(self):
        """Check for old path formats that should be updated."""
        print("\n[5] Checking path consistency...")

        old_path_patterns = [
            (r'xml2sql/', 'pipelines/xml-to-sql/'),
            (r'src/api/', 'src/xml_to_sql/web/api/'),
            (r'src/renderer\.py', 'src/xml_to_sql/sql/renderer.py'),
        ]

        # Files to check
        files_to_check = list(self.root.glob(".claude/*.md"))
        files_to_check.extend(self.xml_to_sql_path.glob("docs/*.md"))
        files_to_check.extend(self.sql_to_abap_path.glob("docs/*.md"))

        for file_path in files_to_check:
            if not file_path.exists():
                continue

            content = file_path.read_text(encoding='utf-8', errors='ignore')

            for old_pattern, new_pattern in old_path_patterns:
                if re.search(old_pattern, content):
                    self.results.add_warning(
                        f"Old path format in {file_path.name}: '{old_pattern}' -> should be '{new_pattern}'"
                    )

        self.results.add_info("Path consistency check complete")

    def _check_duplicate_content(self):
        """Check for duplicate content in documentation files."""
        print("\n[6] Checking for duplicate content...")

        doc_files = [
            self.xml_to_sql_path / "docs" / "SOLVED_BUGS.md",
        ]

        for doc_file in doc_files:
            if not doc_file.exists():
                continue

            content = doc_file.read_text(encoding='utf-8', errors='ignore')
            lines = content.split('\n')

            # Look for repeated sections (same 10+ consecutive lines)
            # with at least 50 lines gap to avoid false positives from similar code patterns
            seen_blocks = {}
            block_size = 10  # Increased from 5 for more meaningful matches
            min_gap = 50     # Minimum lines apart to be considered true duplicate

            for i in range(len(lines) - block_size):
                block = '\n'.join(lines[i:i+block_size]).strip()
                if len(block) > 200:  # Only check significant blocks
                    if block in seen_blocks:
                        first_occurrence = seen_blocks[block]
                        # Only report if they're far apart (not consecutive)
                        if i - first_occurrence > min_gap:
                            self.results.add_warning(
                                f"Duplicate content in {doc_file.name}: lines {first_occurrence+1}-{first_occurrence+block_size} "
                                f"duplicated at lines {i+1}-{i+block_size}"
                            )
                    else:
                        seen_blocks[block] = i

        self.results.add_info("Duplicate content check complete")

    def _check_golden_commit_alignment(self):
        """Check that GOLDEN_COMMIT.yaml is aligned with actual validated XMLs."""
        print("\n[7] Checking GOLDEN_COMMIT.yaml alignment...")

        golden_xml = self.xml_to_sql_path / "GOLDEN_COMMIT.yaml"
        golden_abap = self.sql_to_abap_path / "GOLDEN_COMMIT.yaml"

        for golden_file in [golden_xml, golden_abap]:
            if not golden_file.exists():
                self.results.add_warning(f"GOLDEN_COMMIT.yaml not found: {golden_file}")
                continue

            try:
                with open(golden_file, 'r', encoding='utf-8') as f:
                    golden_data = yaml.safe_load(f)

                if not golden_data:
                    continue

                # Check XML validated count matches list
                if 'validated_xmls' in golden_data:
                    count = golden_data['validated_xmls'].get('count', 0)
                    files = golden_data['validated_xmls'].get('files', [])

                    if count != len(files):
                        self.results.add_error(
                            f"GOLDEN_COMMIT.yaml count mismatch in {golden_file.name}: "
                            f"count={count} but {len(files)} files listed"
                        )

                # Check ABAP validated count
                if 'validated_programs' in golden_data:
                    count = golden_data['validated_programs'].get('count', 0)
                    files = golden_data['validated_programs'].get('files', [])

                    if count != len(files):
                        self.results.add_error(
                            f"GOLDEN_COMMIT.yaml count mismatch in {golden_file.name}: "
                            f"count={count} but {len(files)} programs listed"
                        )

            except Exception as e:
                self.results.add_error(f"Error parsing {golden_file.name}: {e}")

        self.results.add_info("GOLDEN_COMMIT alignment check complete")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Validate Xsodus Converter documentation and code alignment')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show all messages including info')
    parser.add_argument('--fix', action='store_true', help='Attempt to fix issues (not implemented yet)')
    args = parser.parse_args()

    validator = XsodusValidator()
    results = validator.validate_all()

    print("\n" + "=" * 60)
    print("VALIDATION RESULTS")
    print("=" * 60)

    if results.errors:
        print(f"\n{len(results.errors)} ERRORS:")
        for error in results.errors:
            print(f"  [ERROR] {error}")

    if results.warnings:
        print(f"\n{len(results.warnings)} WARNINGS:")
        for warning in results.warnings:
            print(f"  [WARN]  {warning}")

    if args.verbose and results.info:
        print(f"\n{len(results.info)} INFO:")
        for info in results.info:
            print(f"  [INFO]  {info}")

    print("\n" + "=" * 60)
    print(f"SUMMARY: {results.summary()}")
    print("=" * 60)

    if results.is_valid():
        print("\nVALIDATION PASSED (errors=0)")
        return 0
    else:
        print(f"\nVALIDATION FAILED ({len(results.errors)} errors)")
        return 1


if __name__ == "__main__":
    exit(main())
