"""Type system definitions for Snowflake-oriented IR."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class DatabaseMode(str, Enum):
    """Target database system for SQL generation."""

    SNOWFLAKE = "snowflake"
    HANA = "hana"
    # Future: DATABRICKS = "databricks"


class HanaVersion(str, Enum):
    """SAP HANA version for version-specific SQL syntax."""

    HANA_1_0 = "1.0"
    HANA_2_0 = "2.0"
    HANA_2_0_SPS01 = "2.0_SPS01"
    HANA_2_0_SPS03 = "2.0_SPS03"
    HANA_2_0_SPS04 = "2.0_SPS04"


class XMLFormat(str, Enum):
    """XML format type for HANA calculation views."""

    CALCULATION_SCENARIO = "calculation_scenario"  # Modern: Calculation:scenario
    COLUMN_VIEW = "column_view"  # Legacy: View:ColumnView


class SnowflakeType(str, Enum):
    """Subset of Snowflake data types relevant to calculation views."""

    VARCHAR = "VARCHAR"
    NUMBER = "NUMBER"
    BOOLEAN = "BOOLEAN"
    DATE = "DATE"
    TIMESTAMP_NTZ = "TIMESTAMP_NTZ"


@dataclass(frozen=True, slots=True)
class DataTypeSpec:
    """Represents a Snowflake type plus optional precision metadata."""

    type: SnowflakeType
    length: Optional[int] = None
    scale: Optional[int] = None

    def render(self) -> str:
        """Render the type as it should appear in SQL."""

        if self.type == SnowflakeType.VARCHAR and self.length:
            return f"{self.type.value}({self.length})"
        if self.type == SnowflakeType.NUMBER:
            if self.length is not None and self.scale is not None:
                return f"{self.type.value}({self.length}, {self.scale})"
            if self.length is not None:
                return f"{self.type.value}({self.length})"
        return self.type.value

