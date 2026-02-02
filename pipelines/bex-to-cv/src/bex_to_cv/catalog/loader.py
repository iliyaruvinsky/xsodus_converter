"""Catalog loader for InfoObject and table mappings.

This module loads catalog data from YAML files that map BEx InfoObjects
to actual HANA database tables and columns.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

# Default catalog data directory
DEFAULT_CATALOG_DIR = Path(__file__).parent / "data"


@dataclass
class InfoObjectMetadata:
    """Metadata for a BEx InfoObject.

    Maps a BEx InfoObject (like 0PLANT) to its corresponding
    HANA master data tables and columns.
    """

    name: str  # InfoObject name (e.g., "0PLANT")
    description: str = ""
    master_data_table: Optional[str] = None  # Table for master data
    text_table: Optional[str] = None  # Table for text/descriptions
    key_column: Optional[str] = None  # Primary key column name
    text_column: Optional[str] = None  # Description column name
    data_type: str = "NVARCHAR"  # HANA data type
    length: int = 0  # Field length
    is_key_figure: bool = False  # True if this is a measure
    aggregation: str = "NONE"  # Default aggregation (SUM, AVG, etc.)


@dataclass
class TableMapping:
    """Mapping from InfoCube/InfoProvider to HANA tables.

    Maps a BEx InfoCube (like ZSAPLOM) to its corresponding
    HANA fact and dimension tables.
    """

    infocube: str  # InfoCube/InfoProvider name
    fact_table: str  # Main fact table in HANA
    schema: str = "SAPABAP1"  # Default HANA schema
    dimension_tables: Dict[str, str] = field(default_factory=dict)  # InfoObject -> table
    description: str = ""


class CatalogLoadError(Exception):
    """Raised when catalog loading fails."""

    pass


_infoobject_cache: Optional[Dict[str, InfoObjectMetadata]] = None
_table_mapping_cache: Optional[Dict[str, TableMapping]] = None


def get_infoobject_catalog(
    catalog_dir: Optional[Path] = None,
    reload: bool = False,
) -> Dict[str, InfoObjectMetadata]:
    """Load InfoObject catalog from YAML file.

    Args:
        catalog_dir: Directory containing catalog YAML files.
        reload: Force reload even if cached.

    Returns:
        Dict mapping InfoObject names to their metadata.
    """
    global _infoobject_cache

    if _infoobject_cache is not None and not reload:
        return _infoobject_cache

    catalog_dir = catalog_dir or DEFAULT_CATALOG_DIR
    catalog_file = catalog_dir / "infoobjects.yaml"

    if not catalog_file.exists():
        logger.warning(f"InfoObject catalog not found: {catalog_file}")
        _infoobject_cache = _get_default_infoobjects()
        return _infoobject_cache

    try:
        with open(catalog_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        raise CatalogLoadError(f"Failed to load InfoObject catalog: {e}")

    catalog: Dict[str, InfoObjectMetadata] = {}

    for item in data.get("infoobjects", []):
        name = item.get("name", "")
        if not name:
            continue

        metadata = InfoObjectMetadata(
            name=name,
            description=item.get("description", ""),
            master_data_table=item.get("master_data_table"),
            text_table=item.get("text_table"),
            key_column=item.get("key_column"),
            text_column=item.get("text_column"),
            data_type=item.get("data_type", "NVARCHAR"),
            length=item.get("length", 0),
            is_key_figure=item.get("type", "").upper() == "KYF",
            aggregation=item.get("aggregation", "NONE"),
        )
        catalog[name] = metadata

    _infoobject_cache = catalog
    logger.info(f"Loaded {len(catalog)} InfoObjects from catalog")
    return catalog


def get_table_mappings(
    catalog_dir: Optional[Path] = None,
    reload: bool = False,
) -> Dict[str, TableMapping]:
    """Load table mappings from YAML file.

    Args:
        catalog_dir: Directory containing catalog YAML files.
        reload: Force reload even if cached.

    Returns:
        Dict mapping InfoCube names to their table mappings.
    """
    global _table_mapping_cache

    if _table_mapping_cache is not None and not reload:
        return _table_mapping_cache

    catalog_dir = catalog_dir or DEFAULT_CATALOG_DIR
    catalog_file = catalog_dir / "table_mappings.yaml"

    if not catalog_file.exists():
        logger.warning(f"Table mappings not found: {catalog_file}")
        _table_mapping_cache = {}
        return _table_mapping_cache

    try:
        with open(catalog_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        raise CatalogLoadError(f"Failed to load table mappings: {e}")

    mappings: Dict[str, TableMapping] = {}

    for item in data.get("table_mappings", []):
        infocube = item.get("infocube", "")
        if not infocube:
            continue

        mapping = TableMapping(
            infocube=infocube,
            fact_table=item.get("fact_table", ""),
            schema=item.get("schema", "SAPABAP1"),
            dimension_tables=item.get("dimension_tables", {}),
            description=item.get("description", ""),
        )
        mappings[infocube] = mapping

    _table_mapping_cache = mappings
    logger.info(f"Loaded {len(mappings)} table mappings from catalog")
    return mappings


def get_infoobject(name: str) -> Optional[InfoObjectMetadata]:
    """Get metadata for a specific InfoObject.

    Args:
        name: InfoObject name (e.g., "0PLANT").

    Returns:
        InfoObjectMetadata or None if not found.
    """
    catalog = get_infoobject_catalog()
    return catalog.get(name)


def get_table_mapping(infocube: str) -> Optional[TableMapping]:
    """Get table mapping for a specific InfoCube.

    Args:
        infocube: InfoCube/InfoProvider name.

    Returns:
        TableMapping or None if not found.
    """
    mappings = get_table_mappings()
    return mappings.get(infocube)


def _get_default_infoobjects() -> Dict[str, InfoObjectMetadata]:
    """Return default InfoObject definitions for common SAP InfoObjects."""
    defaults = [
        InfoObjectMetadata(
            name="0PLANT",
            description="Plant",
            master_data_table="T001W",
            text_table="T001WT",
            key_column="WERKS",
            text_column="NAME1",
            data_type="NVARCHAR",
            length=4,
        ),
        InfoObjectMetadata(
            name="0MATERIAL",
            description="Material",
            master_data_table="MARA",
            text_table="MAKT",
            key_column="MATNR",
            text_column="MAKTX",
            data_type="NVARCHAR",
            length=18,
        ),
        InfoObjectMetadata(
            name="0CUSTOMER",
            description="Customer",
            master_data_table="KNA1",
            text_table="KNA1",
            key_column="KUNNR",
            text_column="NAME1",
            data_type="NVARCHAR",
            length=10,
        ),
        InfoObjectMetadata(
            name="0VENDOR",
            description="Vendor",
            master_data_table="LFA1",
            text_table="LFA1",
            key_column="LIFNR",
            text_column="NAME1",
            data_type="NVARCHAR",
            length=10,
        ),
        InfoObjectMetadata(
            name="0CALDAY",
            description="Calendar Day",
            data_type="DATE",
        ),
        InfoObjectMetadata(
            name="0CALMONTH",
            description="Calendar Month",
            data_type="NVARCHAR",
            length=6,
        ),
        InfoObjectMetadata(
            name="0CALYEAR",
            description="Calendar Year",
            data_type="NVARCHAR",
            length=4,
        ),
        InfoObjectMetadata(
            name="0QUANTITY",
            description="Quantity",
            data_type="DECIMAL",
            length=17,
            is_key_figure=True,
            aggregation="SUM",
        ),
        InfoObjectMetadata(
            name="0AMOUNT",
            description="Amount",
            data_type="DECIMAL",
            length=17,
            is_key_figure=True,
            aggregation="SUM",
        ),
        InfoObjectMetadata(
            name="0UNIT",
            description="Unit of Measure",
            master_data_table="T006A",
            key_column="MSEHI",
            text_column="MSEHT",
            data_type="NVARCHAR",
            length=3,
        ),
        InfoObjectMetadata(
            name="0CURRENCY",
            description="Currency",
            master_data_table="TCURC",
            key_column="WAERS",
            text_column="LTEXT",
            data_type="NVARCHAR",
            length=5,
        ),
    ]
    return {io.name: io for io in defaults}


def clear_cache() -> None:
    """Clear the catalog caches."""
    global _infoobject_cache, _table_mapping_cache
    _infoobject_cache = None
    _table_mapping_cache = None
