"""Heuristics for inferring Snowflake data types from HANA attribute names/values."""

from __future__ import annotations

import re
from typing import Optional

from ..domain import DataTypeSpec, SnowflakeType


_DATE_PATTERN = re.compile(r"(DATE|DAT$|DATUM|ERDAT|AEDAT|BUDAT|VALUT|DATENT|AUGDT)", re.IGNORECASE)
_TIMESTAMP_PATTERN = re.compile(r"(TIMESTAMP|TIME$|TSTMP|UTIME|UTS)", re.IGNORECASE)
_NUMERIC_PATTERN = re.compile(
    r"(AMT|AMOUNT|BETR|MENGE|QUAN|NUM|CNT|RATE|PRICE|VALUE|IDNRK|ANZ)", re.IGNORECASE
)


def guess_attribute_type(attribute_name: str) -> DataTypeSpec:
    """Infer a Snowflake type from an attribute name."""

    name = attribute_name.upper()
    if _DATE_PATTERN.search(name):
        return DataTypeSpec(SnowflakeType.DATE)
    if _TIMESTAMP_PATTERN.search(name):
        return DataTypeSpec(SnowflakeType.TIMESTAMP_NTZ)
    if _NUMERIC_PATTERN.search(name):
        return DataTypeSpec(SnowflakeType.NUMBER, length=38, scale=6)

    # Default: treat as textual ID/value; keep a reasonable length cap.
    default_length = 255 if len(name) > 10 else 40
    return DataTypeSpec(SnowflakeType.VARCHAR, length=default_length)


def guess_literal_type(value: str) -> Optional[DataTypeSpec]:
    """Infer type for a literal value if possible."""

    stripped = value.strip()
    if not stripped:
        return None
    if stripped.isdigit():
        length = min(len(stripped), 38)
        return DataTypeSpec(SnowflakeType.NUMBER, length=length)
    # Simple date literal detection (YYYYMMDD or YYYY-MM-DD)
    if re.fullmatch(r"\d{8}", stripped) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", stripped):
        return DataTypeSpec(SnowflakeType.DATE)
    return DataTypeSpec(SnowflakeType.VARCHAR, length=max(len(stripped), 10))


