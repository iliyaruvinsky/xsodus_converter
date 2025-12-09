"""Package Mapping Database Management.

This module handles SQLite database storage for package mappings from multiple HANA instances.
Supports importing Excel files and managing multi-instance mappings.
"""
from __future__ import annotations

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)


class PackageMappingDB:
    """Database manager for package mappings from multiple HANA instances."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file.
                    If None, uses default location in project root.
        """
        if db_path is None:
            # Default to project root
            project_root = Path(__file__).parent.parent.parent
            db_path = project_root / "package_mappings.db"

        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize database schema if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Table: hana_instances
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hana_instances (
                    instance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    instance_name TEXT UNIQUE NOT NULL,  -- e.g., "MBD (ECC)", "BWD (BW)"
                    instance_type TEXT,                  -- "ECC", "BW", "S4HANA"
                    description TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Table: package_mappings
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS package_mappings (
                    mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    instance_id INTEGER NOT NULL,
                    cv_name TEXT NOT NULL,               -- e.g., "CV_CNCLD_EVNTS"
                    package_path TEXT NOT NULL,          -- e.g., "EYAL.EYAL_CTL"
                    source_file TEXT,                    -- Original Excel filename
                    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    FOREIGN KEY (instance_id) REFERENCES hana_instances(instance_id),
                    UNIQUE(instance_id, cv_name)         -- One mapping per CV per instance
                )
            """)

            # Table: import_history
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS import_history (
                    import_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    instance_id INTEGER NOT NULL,
                    source_file TEXT NOT NULL,
                    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    cv_count INTEGER,
                    status TEXT,                         -- "SUCCESS", "FAILED", "PARTIAL"
                    error_message TEXT,
                    FOREIGN KEY (instance_id) REFERENCES hana_instances(instance_id)
                )
            """)

            # Index for fast CV lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_cv_lookup
                ON package_mappings(cv_name, is_active)
            """)

            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")

    def import_from_excel(self, excel_path: Path, instance_name: str,
                         instance_type: Optional[str] = None) -> Dict:
        """Import package mappings from Excel file.

        Args:
            excel_path: Path to Excel file with columns: PACKAGE_ID, OBJECT_NAME
            instance_name: Name of HANA instance (e.g., "MBD (ECC)")
            instance_type: Type of instance (e.g., "ECC", "BW")

        Returns:
            Dictionary with import results
        """
        import pandas as pd

        try:
            # Read Excel file
            df = pd.read_excel(excel_path)
            df.columns = df.columns.str.strip()

            # Validate columns
            required_cols = ['PACKAGE_ID', 'OBJECT_NAME']
            if not all(col in df.columns for col in required_cols):
                raise ValueError(f"Excel must have columns: {required_cols}")

            # Get or create instance
            instance_id = self._get_or_create_instance(
                instance_name, instance_type
            )

            # Import mappings
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Deactivate old mappings for this instance
                cursor.execute("""
                    UPDATE package_mappings
                    SET is_active = 0
                    WHERE instance_id = ?
                """, (instance_id,))

                # Insert new mappings
                imported_count = 0
                for _, row in df.iterrows():
                    cv_name = str(row['OBJECT_NAME']).strip()
                    package_path = str(row['PACKAGE_ID']).strip()

                    cursor.execute("""
                        INSERT OR REPLACE INTO package_mappings
                        (instance_id, cv_name, package_path, source_file, is_active)
                        VALUES (?, ?, ?, ?, 1)
                    """, (instance_id, cv_name, package_path, excel_path.name))

                    imported_count += 1

                # Record import history
                cursor.execute("""
                    INSERT INTO import_history
                    (instance_id, source_file, cv_count, status)
                    VALUES (?, ?, ?, 'SUCCESS')
                """, (instance_id, excel_path.name, imported_count))

                conn.commit()

                logger.info(
                    f"Imported {imported_count} mappings from {excel_path.name} "
                    f"for instance '{instance_name}'"
                )

                return {
                    "status": "SUCCESS",
                    "instance_name": instance_name,
                    "instance_id": instance_id,
                    "cv_count": imported_count,
                    "source_file": excel_path.name
                }

        except Exception as e:
            logger.error(f"Failed to import {excel_path}: {e}")

            # Record failed import
            try:
                instance_id = self._get_instance_id(instance_name)
                if instance_id:
                    with sqlite3.connect(self.db_path) as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO import_history
                            (instance_id, source_file, status, error_message)
                            VALUES (?, ?, 'FAILED', ?)
                        """, (instance_id, excel_path.name, str(e)))
                        conn.commit()
            except:
                pass

            return {
                "status": "FAILED",
                "error": str(e)
            }

    def _get_or_create_instance(self, instance_name: str,
                                instance_type: Optional[str] = None) -> int:
        """Get or create HANA instance record."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Try to get existing
            cursor.execute("""
                SELECT instance_id FROM hana_instances
                WHERE instance_name = ?
            """, (instance_name,))

            row = cursor.fetchone()
            if row:
                return row[0]

            # Create new
            cursor.execute("""
                INSERT INTO hana_instances (instance_name, instance_type)
                VALUES (?, ?)
            """, (instance_name, instance_type))

            conn.commit()
            return cursor.lastrowid

    def _get_instance_id(self, instance_name: str) -> Optional[int]:
        """Get instance ID by name."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT instance_id FROM hana_instances
                WHERE instance_name = ?
            """, (instance_name,))

            row = cursor.fetchone()
            return row[0] if row else None

    def get_package(self, cv_name: str,
                   instance_name: Optional[str] = None) -> Optional[str]:
        """Get package path for a CV name.

        Args:
            cv_name: Name of Calculation View
            instance_name: Specific instance to search (optional)
                          If None, searches all active instances

        Returns:
            Package path or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if instance_name:
                # Search specific instance
                cursor.execute("""
                    SELECT pm.package_path
                    FROM package_mappings pm
                    JOIN hana_instances hi ON pm.instance_id = hi.instance_id
                    WHERE pm.cv_name = ?
                      AND hi.instance_name = ?
                      AND pm.is_active = 1
                      AND hi.is_active = 1
                """, (cv_name, instance_name))
            else:
                # Search all instances (prioritize most recently updated)
                cursor.execute("""
                    SELECT pm.package_path
                    FROM package_mappings pm
                    JOIN hana_instances hi ON pm.instance_id = hi.instance_id
                    WHERE pm.cv_name = ?
                      AND pm.is_active = 1
                      AND hi.is_active = 1
                    ORDER BY hi.updated_at DESC
                    LIMIT 1
                """, (cv_name,))

            row = cursor.fetchone()
            return row[0].strip() if row else None

    def search_cv(self, pattern: str,
                 instance_name: Optional[str] = None) -> List[tuple]:
        """Search for CVs by name pattern.

        Args:
            pattern: Search pattern (case-insensitive substring)
            instance_name: Specific instance to search (optional)

        Returns:
            List of (cv_name, package_path, instance_name) tuples
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if instance_name:
                cursor.execute("""
                    SELECT pm.cv_name, pm.package_path, hi.instance_name
                    FROM package_mappings pm
                    JOIN hana_instances hi ON pm.instance_id = hi.instance_id
                    WHERE pm.cv_name LIKE ?
                      AND hi.instance_name = ?
                      AND pm.is_active = 1
                      AND hi.is_active = 1
                    ORDER BY pm.cv_name
                """, (f'%{pattern}%', instance_name))
            else:
                cursor.execute("""
                    SELECT pm.cv_name, pm.package_path, hi.instance_name
                    FROM package_mappings pm
                    JOIN hana_instances hi ON pm.instance_id = hi.instance_id
                    WHERE pm.cv_name LIKE ?
                      AND pm.is_active = 1
                      AND hi.is_active = 1
                    ORDER BY pm.cv_name
                """, (f'%{pattern}%',))

            return cursor.fetchall()

    def get_instances(self) -> List[Dict]:
        """Get all HANA instances."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    hi.instance_id,
                    hi.instance_name,
                    hi.instance_type,
                    hi.description,
                    hi.is_active,
                    COUNT(pm.mapping_id) as cv_count
                FROM hana_instances hi
                LEFT JOIN package_mappings pm
                    ON hi.instance_id = pm.instance_id
                    AND pm.is_active = 1
                GROUP BY hi.instance_id
                ORDER BY hi.instance_name
            """)

            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_import_history(self, limit: int = 10) -> List[Dict]:
        """Get recent import history."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    ih.*,
                    hi.instance_name
                FROM import_history ih
                JOIN hana_instances hi ON ih.instance_id = hi.instance_id
                ORDER BY ih.import_date DESC
                LIMIT ?
            """, (limit,))

            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_statistics(self) -> Dict:
        """Get database statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Total instances
            cursor.execute("""
                SELECT COUNT(*) FROM hana_instances WHERE is_active = 1
            """)
            total_instances = cursor.fetchone()[0]

            # Total CVs
            cursor.execute("""
                SELECT COUNT(DISTINCT cv_name)
                FROM package_mappings WHERE is_active = 1
            """)
            total_cvs = cursor.fetchone()[0]

            # Total mappings
            cursor.execute("""
                SELECT COUNT(*) FROM package_mappings WHERE is_active = 1
            """)
            total_mappings = cursor.fetchone()[0]

            return {
                "total_instances": total_instances,
                "total_cvs": total_cvs,
                "total_mappings": total_mappings
            }


# Global singleton
_db: Optional[PackageMappingDB] = None


def get_db() -> PackageMappingDB:
    """Get global database instance."""
    global _db
    if _db is None:
        _db = PackageMappingDB()
    return _db


__all__ = ["PackageMappingDB", "get_db"]
