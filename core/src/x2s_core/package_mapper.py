"""HANA Package Mapping System for Calculation Views.

This module provides automatic package path lookup for HANA Calculation Views
based on their names. The mappings are loaded from MBD instance export.

Usage:
    from xml_to_sql.package_mapper import PackageMapper

    mapper = PackageMapper()
    package = mapper.get_package("CV_CNCLD_EVNTS")
    # Returns: "EYAL.EYAL_CTL"
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)


class PackageMapper:
    """Manager for HANA Calculation View package mappings."""

    def __init__(self, mapping_file: Optional[Path] = None):
        """Initialize package mapper.

        Args:
            mapping_file: Path to package_mapping.json.
                         If None, uses default location in project root.
        """
        if mapping_file is None:
            # Default to package_mapping.json in project root
            project_root = Path(__file__).parent.parent.parent
            mapping_file = project_root / "package_mapping.json"

        self.mapping_file = mapping_file
        self._mappings: Dict[str, str] = {}
        self._reverse_mappings: Dict[str, List[str]] = {}
        self._metadata: Dict = {}

        self._load_mappings()

    def _load_mappings(self) -> None:
        """Load package mappings from JSON file."""
        if not self.mapping_file.exists():
            logger.warning(f"Package mapping file not found: {self.mapping_file}")
            return

        try:
            with open(self.mapping_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self._mappings = data.get('mappings', {})
            self._metadata = {
                k: v for k, v in data.items()
                if k.startswith('_')
            }

            # Build reverse mapping (package -> list of CVs)
            for cv_name, package in self._mappings.items():
                if package not in self._reverse_mappings:
                    self._reverse_mappings[package] = []
                self._reverse_mappings[package].append(cv_name)

            logger.info(
                f"Loaded {len(self._mappings)} CV package mappings from {self.mapping_file}"
            )

        except Exception as e:
            logger.error(f"Failed to load package mappings: {e}")
            raise

    def get_package(self, cv_name: str) -> Optional[str]:
        """Get package path for a given Calculation View name.

        Args:
            cv_name: Name of the Calculation View (e.g., "CV_CNCLD_EVNTS")

        Returns:
            Package path (e.g., "EYAL.EYAL_CTL") or None if not found
        """
        # Try exact match first
        package = self._mappings.get(cv_name)
        if package:
            return package.strip()

        # Try case-insensitive match
        cv_name_upper = cv_name.upper()
        for name, pkg in self._mappings.items():
            if name.upper() == cv_name_upper:
                return pkg.strip()

        return None

    def get_cvs_in_package(self, package: str) -> List[str]:
        """Get all Calculation Views in a given package.

        Args:
            package: Package path (e.g., "EYAL.EYAL_CTL")

        Returns:
            List of CV names in the package
        """
        # Try exact match first
        cvs = self._reverse_mappings.get(package)
        if cvs:
            return cvs.copy()

        # Try with stripped whitespace
        package_stripped = package.strip()
        for pkg, cvs in self._reverse_mappings.items():
            if pkg.strip() == package_stripped:
                return cvs.copy()

        return []

    def validate_mapping(self, cv_name: str, expected_package: str) -> bool:
        """Validate that a CV is mapped to the expected package.

        Args:
            cv_name: Name of the Calculation View
            expected_package: Expected package path

        Returns:
            True if mapping matches, False otherwise
        """
        actual_package = self.get_package(cv_name)
        if actual_package is None:
            logger.warning(f"CV '{cv_name}' not found in package mappings")
            return False

        if actual_package.strip() != expected_package.strip():
            logger.warning(
                f"Package mismatch for '{cv_name}': "
                f"expected '{expected_package}', got '{actual_package}'"
            )
            return False

        return True

    def get_all_packages(self) -> List[str]:
        """Get list of all unique packages.

        Returns:
            Sorted list of package paths
        """
        return sorted(set(pkg.strip() for pkg in self._mappings.values()))

    def get_metadata(self) -> Dict:
        """Get metadata about the mapping file.

        Returns:
            Dictionary with metadata (source, date, instance, etc.)
        """
        return self._metadata.copy()

    def search_cv(self, pattern: str) -> List[tuple[str, str]]:
        """Search for Calculation Views by name pattern.

        Args:
            pattern: Search pattern (case-insensitive substring match)

        Returns:
            List of (cv_name, package) tuples matching the pattern
        """
        pattern_upper = pattern.upper()
        results = []

        for cv_name, package in self._mappings.items():
            if pattern_upper in cv_name.upper():
                results.append((cv_name, package.strip()))

        return sorted(results)

    @property
    def total_cvs(self) -> int:
        """Get total number of mapped Calculation Views."""
        return len(self._mappings)

    @property
    def total_packages(self) -> int:
        """Get total number of unique packages."""
        return len(self._reverse_mappings)


# Global singleton instance
_mapper: Optional[PackageMapper] = None


def get_mapper() -> PackageMapper:
    """Get the global PackageMapper singleton instance."""
    global _mapper
    if _mapper is None:
        _mapper = PackageMapper()
    return _mapper


def get_package(cv_name: str) -> Optional[str]:
    """Convenience function to get package for a CV name.

    Args:
        cv_name: Name of the Calculation View

    Returns:
        Package path or None if not found

    Note:
        This function now queries the PackageMappingDB (SQLite database)
        instead of the legacy package_mapping.json file. The database
        is populated via the Web UI "Mappings" tab.
    """
    try:
        from .package_mapping_db import PackageMappingDB

        db = PackageMappingDB()
        result = db.get_package(cv_name)

        if result:
            return result

        # Fallback to old JSON-based system if database lookup fails
        return get_mapper().get_package(cv_name)

    except Exception as e:
        logger.warning(f"Database lookup failed for '{cv_name}': {e}. Falling back to JSON.")
        # Fallback to old JSON-based system
        return get_mapper().get_package(cv_name)


__all__ = [
    "PackageMapper",
    "get_mapper",
    "get_package",
]
