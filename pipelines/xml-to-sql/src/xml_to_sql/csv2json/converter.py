"""
SAP Datasource Metadata to JSON Converter
==========================================
Converts SAP BW/ECC Datasource metadata from CSV format
into a standardized JSON schema for cloud data warehouse migrations.

Based on specification: docs/pipes/CSV_2_JSON/SAP_DATASOURCE_JSON_CONVERTER_SPEC.md
"""

import json
import csv
import io
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from .models import (
    ConverterConfig,
    ColumnDefinition,
    ConversionError,
    ConversionStats,
    ConversionResult,
    DatasourceInfo,
    TYPE_MAPPING,
    STRING_TYPES,
    DECIMAL_TYPES,
    CSVColumns,
)

logger = logging.getLogger(__name__)


class SAPDatasourceConverter:
    """
    Converts SAP datasource metadata from CSV to JSON format.

    Usage:
        converter = SAPDatasourceConverter()
        result = converter.convert(csv_content, primary_key_fields=["MATNR"])

        if result.success:
            print(result.json_output)
        else:
            for error in result.errors:
                print(f"Error: {error.message}")
    """

    def __init__(self, config: Optional[ConverterConfig] = None):
        """
        Initialize the converter with optional configuration.

        Args:
            config: Converter configuration options
        """
        self.config = config or ConverterConfig()
        self.errors: List[ConversionError] = []
        self.warnings: List[str] = []

    def convert(
        self,
        csv_content: str,
        primary_key_fields: Optional[List[str]] = None,
        config_overrides: Optional[Dict[str, str]] = None
    ) -> ConversionResult:
        """
        Convert SAP datasource CSV metadata to JSON format.

        Args:
            csv_content: Tab-separated CSV content as string
            primary_key_fields: List of field names to mark as primary keys
            config_overrides: Optional overrides for header-level fields

        Returns:
            ConversionResult with json_output or error details
        """
        start_time = datetime.now()
        self.errors = []
        self.warnings = []
        stats = ConversionStats()

        primary_key_fields = primary_key_fields or []
        config_overrides = config_overrides or {}

        try:
            # Parse CSV content
            rows = self._parse_csv(csv_content)

            if not rows:
                self._add_error("EMPTY_INPUT", "Empty input file")
                return self._build_error_result(stats, start_time)

            # Separate header and data rows
            header_row = rows[0]
            data_rows = rows[1:]

            if not data_rows:
                self._add_error("NO_DATA", "No data rows found in CSV")
                return self._build_error_result(stats, start_time)

            stats.total_rows = len(data_rows)

            # Validate header columns
            if not self._validate_header(header_row):
                return self._build_error_result(stats, start_time)

            # Extract header-level metadata from first data row
            first_row = data_rows[0]
            datasource_name = self._get_field(first_row, CSVColumns.OLTPSOURCE, "")
            delta_indicator = self._get_field(first_row, CSVColumns.DELTA, "")

            # Determine load type
            load_type = self._determine_load_type(delta_indicator)

            # Process all columns
            columns: List[ColumnDefinition] = []
            for row_idx, row in enumerate(data_rows, start=2):  # Start at 2 (1-indexed + header)
                column = self._process_row(row, row_idx, primary_key_fields)
                if column:
                    columns.append(column)
                    stats.columns_processed += 1
                else:
                    stats.skipped_rows += 1

            if not columns:
                self._add_error("NO_COLUMNS", "No valid columns were processed")
                return self._build_error_result(stats, start_time)

            # Check for primary key
            has_primary_key = any(col.primary_key for col in columns)
            if not has_primary_key:
                self.warnings.append("No primary key defined. Consider specifying primary_key_fields.")

            # Check for duplicate column names
            column_names = [col.name for col in columns]
            duplicates = self._find_duplicates(column_names)
            if duplicates:
                self._add_error(
                    "DUPLICATE_COLUMNS",
                    f"Duplicate column names found: {', '.join(duplicates)}"
                )
                if self.config.strict_mode:
                    return self._build_error_result(stats, start_time)

            # Build output JSON structure
            output = {
                "environment": config_overrides.get("environment", self.config.environment),
                "source_system": config_overrides.get("source_system", self.config.source_system),
                "data_source": datasource_name,
                "file_type": config_overrides.get("file_type", self.config.file_type),
                "load_type": load_type,
                "columns": [col.to_dict() for col in columns]
            }

            # Convert to JSON string
            json_output = json.dumps(output, indent=2, ensure_ascii=False)

            # Calculate processing time
            stats.processing_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            return ConversionResult(
                success=True,
                json_output=json_output,
                errors=self.errors,
                warnings=self.warnings,
                stats=stats
            )

        except Exception as e:
            logger.exception("Unexpected error during conversion")
            self._add_error("CONVERSION_ERROR", f"Unexpected error: {str(e)}")
            return self._build_error_result(stats, start_time)

    def _detect_delimiter(self, csv_content: str) -> str:
        """
        Auto-detect CSV delimiter (tab or comma).

        Examines the first line to determine the delimiter.
        """
        first_line = csv_content.split('\n')[0] if csv_content else ''
        # Count occurrences - prefer tab if present (more specific)
        tab_count = first_line.count('\t')
        comma_count = first_line.count(',')

        if tab_count >= 5:  # Expect at least 5 columns for valid CSV
            return '\t'
        elif comma_count >= 5:
            return ','
        elif tab_count > comma_count:
            return '\t'
        else:
            return ','  # Default to comma

    def _parse_csv(self, csv_content: str) -> List[List[str]]:
        """Parse CSV content with auto-detected delimiter."""
        delimiter = self._detect_delimiter(csv_content)
        rows = []
        reader = csv.reader(io.StringIO(csv_content), delimiter=delimiter)
        for row in reader:
            rows.append(row)
        return rows

    def _validate_header(self, header: List[str]) -> bool:
        """Validate that required columns exist."""
        required_columns = ["OLTPSOURCE", "DELTA", "FIELDNAME", "DATATYPE", "LENG", "DECIMALS", "DDTEXT"]
        header_upper = [h.upper().strip() for h in header]

        for col in required_columns:
            if col not in header_upper:
                self._add_error("MISSING_COLUMN", f"Required column missing: {col}")
                return False
        return True

    def _get_field(self, row: List[str], index: int, default: str = "") -> str:
        """Safely get a field value from a row."""
        if index < len(row):
            return row[index].strip()
        return default

    def _determine_load_type(self, delta_indicator: str) -> str:
        """
        Determine load type based on delta indicator.

        Rule: If DELTA field is empty/null/whitespace -> "FULL", else -> "DELTA"
        """
        if not delta_indicator or not delta_indicator.strip():
            return "FULL"
        return "DELTA"

    def _map_datatype(self, sap_type: str) -> str:
        """Map SAP data type to JSON schema type."""
        sap_type_upper = sap_type.upper().strip()
        json_type = TYPE_MAPPING.get(sap_type_upper)

        if json_type is None:
            self.warnings.append(f"Unknown SAP data type '{sap_type}', defaulting to '{self.config.default_type}'")
            return self.config.default_type

        return json_type

    def _transform_business_story(self, ddtext: str) -> str:
        """
        Transform DDTEXT to business_story format.

        Rule: Replace all spaces with underscores, preserve other characters.
        """
        return ddtext.replace(" ", "_")

    def _parse_int(self, value: str, field_name: str, row_idx: int, default: int = 0) -> int:
        """Safely parse an integer value."""
        try:
            return int(value) if value.strip() else default
        except ValueError:
            self.warnings.append(f"Row {row_idx}: Invalid {field_name} value '{value}', using {default}")
            return default

    def _process_row(
        self,
        row: List[str],
        row_idx: int,
        primary_key_fields: List[str]
    ) -> Optional[ColumnDefinition]:
        """Process a single CSV row into a ColumnDefinition."""

        # Extract field values
        fieldname = self._get_field(row, CSVColumns.FIELDNAME)
        datatype = self._get_field(row, CSVColumns.DATATYPE)
        leng = self._get_field(row, CSVColumns.LENG)
        decimals = self._get_field(row, CSVColumns.DECIMALS)
        ddtext = self._get_field(row, CSVColumns.DDTEXT)

        # Validate required fields
        if not fieldname:
            self.warnings.append(f"Row {row_idx}: Empty FIELDNAME, skipping row")
            return None

        if not datatype:
            self.warnings.append(f"Row {row_idx}: Empty DATATYPE for field '{fieldname}', defaulting to CHAR")
            datatype = "CHAR"

        # Map data type
        json_type = self._map_datatype(datatype)

        # Parse length and precision
        length_value = self._parse_int(leng, "LENG", row_idx)
        precision_value = self._parse_int(decimals, "DECIMALS", row_idx)

        # Determine if primary key (case-insensitive match)
        is_primary_key = fieldname.upper() in [pk.upper() for pk in primary_key_fields]

        # Build column definition
        column = ColumnDefinition(
            name=fieldname,
            type=json_type,
            primary_key=is_primary_key,
            business_name=fieldname,
            business_name_desc=fieldname,
            business_story=self._transform_business_story(ddtext),
            length=length_value if json_type in STRING_TYPES else None,
            precision=precision_value if json_type in DECIMAL_TYPES else None
        )

        return column

    def _find_duplicates(self, items: List[str]) -> List[str]:
        """Find duplicate items in a list."""
        seen = set()
        duplicates = set()
        for item in items:
            if item in seen:
                duplicates.add(item)
            seen.add(item)
        return list(duplicates)

    def _add_error(
        self,
        code: str,
        message: str,
        row: Optional[int] = None,
        field: Optional[str] = None,
        value: Optional[str] = None,
        suggestion: Optional[str] = None
    ):
        """Add an error to the errors list."""
        self.errors.append(ConversionError(
            code=code,
            message=message,
            row=row,
            field=field,
            value=value,
            suggestion=suggestion
        ))

    def _build_error_result(self, stats: ConversionStats, start_time: datetime) -> ConversionResult:
        """Build an error result."""
        stats.processing_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        return ConversionResult(
            success=False,
            json_output=None,
            errors=self.errors,
            warnings=self.warnings,
            stats=stats
        )

    # =========================================================================
    # MULTI-DATASOURCE METHODS
    # =========================================================================

    def list_datasources(self, csv_content: str) -> List[DatasourceInfo]:
        """
        List all unique datasources in the CSV with metadata.

        Args:
            csv_content: CSV content as string

        Returns:
            List of DatasourceInfo objects with metadata about each datasource
        """
        rows = self._parse_csv(csv_content)

        if len(rows) < 2:
            return []

        # Skip header row
        data_rows = rows[1:]

        # Group rows by OLTPSOURCE
        datasource_map: Dict[str, Dict[str, Any]] = {}

        for row in data_rows:
            ds_name = self._get_field(row, CSVColumns.OLTPSOURCE)
            if not ds_name:
                continue

            if ds_name not in datasource_map:
                datasource_map[ds_name] = {
                    'type': self._get_field(row, CSVColumns.TYPE),
                    'description': self._get_field(row, CSVColumns.TXTLG),
                    'delta': self._get_field(row, CSVColumns.DELTA),
                    'field_count': 0
                }
            datasource_map[ds_name]['field_count'] += 1

        # Convert to DatasourceInfo list
        result = []
        for name, info in sorted(datasource_map.items()):
            result.append(DatasourceInfo(
                name=name,
                type=info['type'],
                description=info['description'],
                field_count=info['field_count'],
                has_delta=bool(info['delta'] and info['delta'].strip())
            ))

        return result

    def convert_multiple(
        self,
        csv_content: str,
        datasource_names: List[str],
        primary_key_mapping: Optional[Dict[str, List[str]]] = None,
        config_overrides: Optional[Dict[str, str]] = None
    ) -> ConversionResult:
        """
        Convert multiple datasources from CSV to a single JSON output.

        Args:
            csv_content: CSV content as string
            datasource_names: List of datasource names to include
            primary_key_mapping: Dict mapping datasource name to list of primary key fields
                                 e.g., {"0MATERIAL_ATTR": ["MATNR"], "0CUSTOMER_ATTR": ["KUNNR"]}
            config_overrides: Optional overrides for header-level fields

        Returns:
            ConversionResult with json_output containing all datasources
        """
        start_time = datetime.now()
        self.errors = []
        self.warnings = []
        stats = ConversionStats()

        primary_key_mapping = primary_key_mapping or {}
        config_overrides = config_overrides or {}

        try:
            rows = self._parse_csv(csv_content)

            if len(rows) < 2:
                self._add_error("EMPTY_INPUT", "Empty or invalid input file")
                return self._build_error_result(stats, start_time)

            header_row = rows[0]
            data_rows = rows[1:]

            if not self._validate_header(header_row):
                return self._build_error_result(stats, start_time)

            # Group rows by datasource
            datasource_rows: Dict[str, List[List[str]]] = {}
            for row in data_rows:
                ds_name = self._get_field(row, CSVColumns.OLTPSOURCE)
                if ds_name in datasource_names:
                    if ds_name not in datasource_rows:
                        datasource_rows[ds_name] = []
                    datasource_rows[ds_name].append(row)

            # Check for missing datasources
            found_datasources = set(datasource_rows.keys())
            requested_datasources = set(datasource_names)
            missing = requested_datasources - found_datasources
            if missing:
                self.warnings.append(f"Requested datasources not found: {', '.join(sorted(missing))}")

            if not datasource_rows:
                self._add_error("NO_DATASOURCES", "No matching datasources found in CSV")
                return self._build_error_result(stats, start_time)

            # Process each datasource
            datasources_output = []
            for ds_name in datasource_names:
                if ds_name not in datasource_rows:
                    continue

                ds_rows = datasource_rows[ds_name]
                primary_keys = primary_key_mapping.get(ds_name, [])

                # Get delta indicator from first row
                delta_indicator = self._get_field(ds_rows[0], CSVColumns.DELTA, "")
                load_type = self._determine_load_type(delta_indicator)

                # Process columns
                columns: List[ColumnDefinition] = []
                for row_idx, row in enumerate(ds_rows, start=1):
                    stats.total_rows += 1
                    column = self._process_row(row, row_idx, primary_keys)
                    if column:
                        columns.append(column)
                        stats.columns_processed += 1
                    else:
                        stats.skipped_rows += 1

                if columns:
                    datasources_output.append({
                        "data_source": ds_name,
                        "load_type": load_type,
                        "columns": [col.to_dict() for col in columns]
                    })

            # Build output JSON structure
            output = {
                "environment": config_overrides.get("environment", self.config.environment),
                "source_system": config_overrides.get("source_system", self.config.source_system),
                "file_type": config_overrides.get("file_type", self.config.file_type),
                "generated_at": datetime.now().isoformat(),
                "datasources": datasources_output
            }

            json_output = json.dumps(output, indent=2, ensure_ascii=False)
            stats.processing_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            return ConversionResult(
                success=True,
                json_output=json_output,
                errors=self.errors,
                warnings=self.warnings,
                stats=stats
            )

        except Exception as e:
            logger.exception("Unexpected error during multi-datasource conversion")
            self._add_error("CONVERSION_ERROR", f"Unexpected error: {str(e)}")
            return self._build_error_result(stats, start_time)

    def convert_to_array_format(
        self,
        csv_content: str,
        datasource_names: List[str],
        primary_key_mapping: Optional[Dict[str, List[str]]] = None,
        config_overrides: Optional[Dict[str, str]] = None,
        progress_callback: Optional[callable] = None,
        cancel_check: Optional[callable] = None
    ) -> ConversionResult:
        """
        Convert multiple datasources to array format JSON (for Exodus platform).

        Output format: Array of datasource objects, each with its own environment/source_system.

        Args:
            csv_content: CSV content as string
            datasource_names: List of datasource names to include
            primary_key_mapping: Dict mapping datasource name to list of primary key fields
            config_overrides: Optional overrides for header-level fields
            progress_callback: Optional callback(current, total, message) for progress updates
            cancel_check: Optional callback() that returns True if operation should be cancelled

        Returns:
            ConversionResult with json_output as array of datasources
        """
        start_time = datetime.now()
        self.errors = []
        self.warnings = []
        stats = ConversionStats()

        primary_key_mapping = primary_key_mapping or {}
        config_overrides = config_overrides or {}

        env = config_overrides.get("environment", self.config.environment)
        source_sys = config_overrides.get("source_system", self.config.source_system)
        file_type = config_overrides.get("file_type", self.config.file_type)

        try:
            # Progress: Parsing CSV
            if progress_callback:
                progress_callback(0, len(datasource_names) + 1, "Parsing CSV file...")

            rows = self._parse_csv(csv_content)

            if len(rows) < 2:
                self._add_error("EMPTY_INPUT", "Empty or invalid input file")
                return self._build_error_result(stats, start_time)

            header_row = rows[0]
            data_rows = rows[1:]

            if not self._validate_header(header_row):
                return self._build_error_result(stats, start_time)

            # Group rows by datasource
            datasource_rows: Dict[str, List[List[str]]] = {}
            for row in data_rows:
                ds_name = self._get_field(row, CSVColumns.OLTPSOURCE)
                if ds_name in datasource_names:
                    if ds_name not in datasource_rows:
                        datasource_rows[ds_name] = []
                    datasource_rows[ds_name].append(row)

            # Check for missing datasources
            found_datasources = set(datasource_rows.keys())
            requested_datasources = set(datasource_names)
            missing = requested_datasources - found_datasources
            if missing:
                self.warnings.append(f"Requested datasources not found: {', '.join(sorted(missing))}")

            if not datasource_rows:
                self._add_error("NO_DATASOURCES", "No matching datasources found in CSV")
                return self._build_error_result(stats, start_time)

            # Process each datasource
            datasources_output = []
            for idx, ds_name in enumerate(datasource_names):
                # Check for cancellation
                if cancel_check and cancel_check():
                    self._add_error("CANCELLED", "Operation cancelled by user")
                    return self._build_error_result(stats, start_time)

                if ds_name not in datasource_rows:
                    continue

                # Progress update
                if progress_callback:
                    progress_callback(idx + 1, len(datasource_names) + 1,
                                      f"Processing {ds_name}...")

                ds_rows = datasource_rows[ds_name]
                primary_keys = primary_key_mapping.get(ds_name, [])

                # Get delta indicator from first row
                delta_indicator = self._get_field(ds_rows[0], CSVColumns.DELTA, "")
                load_type = self._determine_load_type(delta_indicator)

                # Process columns with new format
                columns_output = []
                for row_idx, row in enumerate(ds_rows):
                    stats.total_rows += 1

                    fieldname = self._get_field(row, CSVColumns.FIELDNAME)
                    datatype = self._get_field(row, CSVColumns.DATATYPE)
                    leng = self._get_field(row, CSVColumns.LENG)
                    ddtext = self._get_field(row, CSVColumns.DDTEXT)

                    if not fieldname:
                        stats.skipped_rows += 1
                        continue

                    if not datatype:
                        datatype = "CHAR"

                    json_type = self._map_datatype(datatype)
                    length_value = self._parse_int(leng, "LENG", row_idx)
                    is_primary_key = fieldname.upper() in [pk.upper() for pk in primary_keys]

                    # Build column in new format (business_name, business_name_desc)
                    col_dict = {
                        "name": fieldname,
                        "type": json_type,
                    }

                    # Add length only for string types
                    if json_type == "string" and length_value > 0:
                        col_dict["length"] = length_value

                    col_dict["primary_key"] = is_primary_key
                    col_dict["business_name"] = fieldname.upper()
                    col_dict["business_name_desc"] = ddtext if ddtext else fieldname

                    columns_output.append(col_dict)
                    stats.columns_processed += 1

                if columns_output:
                    datasources_output.append({
                        "environment": env,
                        "source_system": source_sys,
                        "data_source": ds_name,
                        "file_type": file_type,
                        "load_type": load_type,
                        "columns": columns_output
                    })

            # Final progress
            if progress_callback:
                progress_callback(len(datasource_names) + 1, len(datasource_names) + 1,
                                  "Generating JSON output...")

            # Output is array at root level
            json_output = json.dumps(datasources_output, indent=2, ensure_ascii=False)
            stats.processing_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            return ConversionResult(
                success=True,
                json_output=json_output,
                errors=self.errors,
                warnings=self.warnings,
                stats=stats
            )

        except Exception as e:
            logger.exception("Unexpected error during array format conversion")
            self._add_error("CONVERSION_ERROR", f"Unexpected error: {str(e)}")
            return self._build_error_result(stats, start_time)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def convert_sap_datasource_to_json(
    csv_content: str,
    primary_key_fields: Optional[List[str]] = None,
    config: Optional[ConverterConfig] = None
) -> ConversionResult:
    """
    Convenience function to convert SAP datasource CSV to JSON.

    Args:
        csv_content: Tab-separated CSV content as string
        primary_key_fields: List of field names to mark as primary keys
        config: Optional configuration overrides

    Returns:
        ConversionResult with json_output or error details
    """
    converter = SAPDatasourceConverter(config)
    return converter.convert(csv_content, primary_key_fields)


def convert_file(
    input_path: str,
    output_path: str,
    primary_key_fields: Optional[List[str]] = None,
    config: Optional[ConverterConfig] = None
) -> ConversionResult:
    """
    Convert a CSV file to JSON file.

    Args:
        input_path: Path to input CSV file
        output_path: Path to output JSON file
        primary_key_fields: List of field names to mark as primary keys
        config: Optional configuration overrides

    Returns:
        ConversionResult with json_output or error details
    """
    with open(input_path, 'r', encoding='utf-8') as f:
        csv_content = f.read()

    result = convert_sap_datasource_to_json(csv_content, primary_key_fields, config)

    if result.success and result.json_output:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result.json_output)

    return result
