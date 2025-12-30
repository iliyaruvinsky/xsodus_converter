"""
Data models for CSV to JSON conversion.

This module contains dataclasses for:
- Configuration options
- Column definitions
- Error handling
- Conversion results
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any


@dataclass
class ConverterConfig:
    """Configuration options for the converter."""
    environment: str = "Development"
    source_system: str = "SAPECC"
    file_type: str = "CSV"
    default_type: str = "string"
    strict_mode: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ColumnDefinition:
    """Represents a single column in the output JSON."""
    name: str
    type: str
    primary_key: bool
    business_name: str
    business_name_desc: str
    business_story: str
    length: Optional[int] = None
    precision: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values appropriately."""
        result = {
            "name": self.name,
            "type": self.type,
        }
        # Add length only for string types
        if self.type == "string" and self.length is not None:
            result["length"] = self.length
        # Add precision only for decimal types
        if self.type == "decimal" and self.precision is not None:
            result["precision"] = self.precision

        result["primary_key"] = self.primary_key
        result["business_name"] = self.business_name
        result["business_name_desc"] = self.business_name_desc
        result["business_story"] = self.business_story

        return result


@dataclass
class ConversionError:
    """Represents a conversion error."""
    code: str
    message: str
    row: Optional[int] = None
    field: Optional[str] = None
    value: Optional[str] = None
    suggestion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {"code": self.code, "message": self.message}
        if self.row is not None:
            result["row"] = self.row
        if self.field is not None:
            result["field"] = self.field
        if self.value is not None:
            result["value"] = self.value
        if self.suggestion is not None:
            result["suggestion"] = self.suggestion
        return result


@dataclass
class ConversionStats:
    """Statistics about the conversion process."""
    total_rows: int = 0
    columns_processed: int = 0
    skipped_rows: int = 0
    processing_time_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConversionResult:
    """Result of a conversion operation."""
    success: bool
    json_output: Optional[str] = None
    errors: List[ConversionError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    stats: ConversionStats = field(default_factory=ConversionStats)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "json_output": self.json_output,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": self.warnings,
            "stats": self.stats.to_dict()
        }


# Type mapping: SAP DATATYPE -> JSON type
TYPE_MAPPING: Dict[str, str] = {
    # String types (include length)
    "CHAR": "string",
    "NUMC": "string",
    "UNIT": "string",
    "CUKY": "string",
    "LANG": "string",
    "CLNT": "string",
    "LCHR": "string",
    "SSTR": "string",
    "STRG": "string",
    # Decimal types (include precision)
    "QUAN": "decimal",
    "DEC": "decimal",
    "CURR": "decimal",
    "FLTP": "decimal",
    # Date/Time types (no additional properties)
    "DATS": "date",
    "TIMS": "timestamp",
    # Integer types (no additional properties)
    "INT1": "integer",
    "INT2": "integer",
    "INT4": "integer",
    "INT8": "integer",
    "PREC": "integer",
}

# Types that require 'length' property
STRING_TYPES = {"string"}

# Types that require 'precision' property
DECIMAL_TYPES = {"decimal"}


class CSVColumns:
    """CSV Column indices (0-based)."""
    OLTPSOURCE = 0
    OBJVERS = 1
    TYPE = 2
    EXTRACTOR = 3
    EXSTRUCT = 4
    TXTLG = 5
    DELTA = 6
    FIELDNAME = 7
    ROLLNAME = 8
    DATATYPE = 9
    LENG = 10
    DECIMALS = 11
    DDTEXT = 12


@dataclass
class DatasourceInfo:
    """Metadata about a datasource in the CSV."""
    name: str           # OLTPSOURCE value
    type: str           # TYPE value (ATTR, TEXT, TRAN)
    description: str    # TXTLG value
    field_count: int    # Number of fields
    has_delta: bool     # Whether DELTA field is populated

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
