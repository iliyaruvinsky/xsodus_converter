"""Catalog module for InfoObject and table mappings."""

from .loader import (
    get_infoobject_catalog,
    get_table_mappings,
    InfoObjectMetadata,
    TableMapping,
)

__all__ = [
    "get_infoobject_catalog",
    "get_table_mappings",
    "InfoObjectMetadata",
    "TableMapping",
]
