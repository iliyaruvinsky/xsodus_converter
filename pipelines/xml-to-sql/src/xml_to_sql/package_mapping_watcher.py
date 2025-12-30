"""File Watcher for Automatic Package Mapping Imports.

Monitors a folder for Excel file uploads and automatically imports them into the database.
"""
from __future__ import annotations

import time
import logging
from pathlib import Path
from typing import Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

from .package_mapping_db import get_db

logger = logging.getLogger(__name__)


class ExcelImportHandler(FileSystemEventHandler):
    """Handler for Excel file creation events."""

    def __init__(self, watch_directory: Path):
        """Initialize handler.

        Args:
            watch_directory: Directory to monitor for Excel files
        """
        self.watch_directory = watch_directory
        self.db = get_db()

    def on_created(self, event):
        """Handle file creation event."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Only process Excel files
        if file_path.suffix.lower() not in ['.xlsx', '.xls']:
            return

        logger.info(f"Detected new Excel file: {file_path.name}")

        # Wait a bit to ensure file is fully written
        time.sleep(2)

        # Parse instance name from filename
        # Expected format: "HANA_CV_{INSTANCE_NAME}.xlsx"
        # e.g., "HANA_CV_MBD.xlsx", "HANA_CV_BWD.xlsx"
        instance_name, instance_type = self._parse_filename(file_path.name)

        if not instance_name:
            logger.warning(
                f"Could not parse instance name from {file_path.name}. "
                f"Expected format: HANA_CV_{{INSTANCE}}.xlsx"
            )
            return

        # Import into database
        try:
            result = self.db.import_from_excel(
                excel_path=file_path,
                instance_name=instance_name,
                instance_type=instance_type
            )

            if result['status'] == 'SUCCESS':
                logger.info(
                    f"✅ Successfully imported {result['cv_count']} CVs "
                    f"from {file_path.name} for instance '{instance_name}'"
                )

                # Move to processed folder
                self._move_to_processed(file_path)
            else:
                logger.error(
                    f"❌ Failed to import {file_path.name}: {result.get('error')}"
                )
                # Move to failed folder
                self._move_to_failed(file_path, result.get('error'))

        except Exception as e:
            logger.error(f"❌ Error processing {file_path.name}: {e}")
            self._move_to_failed(file_path, str(e))

    def _parse_filename(self, filename: str) -> tuple[Optional[str], Optional[str]]:
        """Parse instance name and type from filename.

        Expected formats:
        - HANA_CV_MBD.xlsx → ("MBD (ECC)", "ECC")
        - HANA_CV_BWD.xlsx → ("BWD (BW)", "BW")
        - HANA_CV_S4D.xlsx → ("S4D (S4HANA)", "S4HANA")

        Returns:
            Tuple of (instance_name, instance_type)
        """
        name = Path(filename).stem  # Remove extension

        # Remove HANA_CV_ prefix
        if name.startswith('HANA_CV_'):
            instance_code = name[8:]  # Everything after "HANA_CV_"

            # Map common codes to full names and types
            instance_map = {
                'MBD': ('MBD (ECC)', 'ECC'),
                'BWD': ('BWD (BW)', 'BW'),
                'S4D': ('S4D (S4HANA)', 'S4HANA'),
                'PRD': ('PRD (Production)', 'ECC'),
                'DEV': ('DEV (Development)', 'ECC'),
                'QAS': ('QAS (Quality)', 'ECC'),
            }

            if instance_code in instance_map:
                return instance_map[instance_code]
            else:
                # Use code as-is
                return (instance_code, None)

        return (None, None)

    def _move_to_processed(self, file_path: Path):
        """Move file to processed folder."""
        processed_dir = self.watch_directory / "processed"
        processed_dir.mkdir(exist_ok=True)

        try:
            target = processed_dir / file_path.name
            # Add timestamp if file exists
            if target.exists():
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                target = processed_dir / f"{file_path.stem}_{timestamp}{file_path.suffix}"

            file_path.rename(target)
            logger.info(f"Moved {file_path.name} to processed/")
        except Exception as e:
            logger.error(f"Failed to move {file_path.name}: {e}")

    def _move_to_failed(self, file_path: Path, error: Optional[str] = None):
        """Move file to failed folder."""
        failed_dir = self.watch_directory / "failed"
        failed_dir.mkdir(exist_ok=True)

        try:
            target = failed_dir / file_path.name
            # Add timestamp if file exists
            if target.exists():
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                target = failed_dir / f"{file_path.stem}_{timestamp}{file_path.suffix}"

            file_path.rename(target)
            logger.info(f"Moved {file_path.name} to failed/")

            # Write error log
            if error:
                error_file = target.with_suffix('.error.txt')
                error_file.write_text(f"Error: {error}\nTime: {time.ctime()}")

        except Exception as e:
            logger.error(f"Failed to move {file_path.name}: {e}")


class PackageMappingWatcher:
    """File system watcher for package mapping imports."""

    def __init__(self, watch_directory: Optional[Path] = None):
        """Initialize watcher.

        Args:
            watch_directory: Directory to monitor for Excel uploads.
                           If None, uses default: project_root/package_mappings/uploads/
        """
        if watch_directory is None:
            project_root = Path(__file__).parent.parent.parent
            watch_directory = project_root / "package_mappings" / "uploads"

        self.watch_directory = watch_directory
        self.watch_directory.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (self.watch_directory / "processed").mkdir(exist_ok=True)
        (self.watch_directory / "failed").mkdir(exist_ok=True)

        self.observer = Observer()
        self.handler = ExcelImportHandler(self.watch_directory)

        logger.info(f"Initialized package mapping watcher on: {self.watch_directory}")

    def start(self):
        """Start watching for file changes."""
        self.observer.schedule(self.handler, str(self.watch_directory), recursive=False)
        self.observer.start()
        logger.info(f"📁 Watching for Excel files in: {self.watch_directory}")

    def stop(self):
        """Stop watching."""
        self.observer.stop()
        self.observer.join()
        logger.info("Stopped package mapping watcher")

    def is_running(self) -> bool:
        """Check if watcher is running."""
        return self.observer.is_alive()


# Global watcher instance
_watcher: Optional[PackageMappingWatcher] = None


def start_watcher(watch_directory: Optional[Path] = None) -> PackageMappingWatcher:
    """Start the global file watcher.

    Args:
        watch_directory: Directory to monitor (optional)

    Returns:
        PackageMappingWatcher instance
    """
    global _watcher
    if _watcher is None or not _watcher.is_running():
        _watcher = PackageMappingWatcher(watch_directory)
        _watcher.start()
    return _watcher


def stop_watcher():
    """Stop the global file watcher."""
    global _watcher
    if _watcher and _watcher.is_running():
        _watcher.stop()
        _watcher = None


__all__ = ["PackageMappingWatcher", "start_watcher", "stop_watcher"]
