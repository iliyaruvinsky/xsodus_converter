"""
CSV to JSON Converter Module
============================
Converts SAP BW/ECC metadata from CSV format
to standardized JSON schema for the Exodus migration platform.

Supported object types:
- DataSources (SAPDatasourceConverter)
- DSOs (SAPDSOConverter)

Part of the xml2sql package.
"""

from .converter import (
    SAPDatasourceConverter,
    convert_sap_datasource_to_json,
    convert_file,
)
from .dso_converter import (
    SAPDSOConverter,
    DSOConverterConfig,
    DSOInfo,
    convert_dso_csv_to_json,
    convert_dso_file,
)
from .models import (
    ConverterConfig,
    ColumnDefinition,
    ConversionError,
    ConversionStats,
    ConversionResult,
    DatasourceInfo,
)

__all__ = [
    # DataSource converter
    "SAPDatasourceConverter",
    "convert_sap_datasource_to_json",
    "convert_file",
    # DSO converter
    "SAPDSOConverter",
    "DSOConverterConfig",
    "DSOInfo",
    "convert_dso_csv_to_json",
    "convert_dso_file",
    # Data classes
    "ConverterConfig",
    "ColumnDefinition",
    "ConversionError",
    "ConversionStats",
    "ConversionResult",
    "DatasourceInfo",
]
