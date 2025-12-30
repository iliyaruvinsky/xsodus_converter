"""Generate wrapper views for BW calculation views."""

from __future__ import annotations

from typing import Optional

from ..domain import Scenario


def generate_bw_wrapper(
    scenario: Scenario,
    bw_package: Optional[str] = None,
    view_name: Optional[str] = None,
) -> str:
    """Generate a wrapper view that queries an existing BW calculation view.
    
    BW calculation views are stored in _SYS_BIC and should be queried directly
    rather than expanded to base tables (which use complex BW naming and schemas).
    
    Args:
        scenario: Parsed scenario (used to extract view name if not provided)
        bw_package: BW package path (e.g., "Macabi_BI.COOM")
        view_name: View name to create (defaults to scenario ID)
    
    Returns:
        SQL string creating a wrapper view
    
    Example:
        CREATE VIEW CV_INVENTORY_ORDERS AS
        SELECT * FROM "_SYS_BIC"."Macabi_BI.COOM/CV_INVENTORY_ORDERS";
    """
    
    # Determine view name
    wrapper_view_name = view_name or scenario.metadata.scenario_id
    
    # Determine BW package and original view name
    # Try to extract from scenario metadata or use provided
    original_view_name = scenario.metadata.scenario_id
    
    if not bw_package:
        # Try to infer from scenario metadata or use a default
        bw_package = "DEFAULT_PACKAGE"
    
    # Build _SYS_BIC path
    sys_bic_path = f'"{bw_package}/{original_view_name}"'
    
    # Generate wrapper SQL
    sql_lines = [
        f"CREATE VIEW {wrapper_view_name} AS",
        f'SELECT * FROM "_SYS_BIC".{sys_bic_path};',
    ]
    
    return "\n".join(sql_lines)


def extract_bw_package_from_xml_path(xml_path: str) -> Optional[str]:
    """Extract BW package from XML file path or content.
    
    Args:
        xml_path: Path to XML file
    
    Returns:
        BW package path or None
    
    Example:
        "Macabi_BI.COOM" from XML metadata
    """
    # Placeholder for future implementation
    # Would parse XML to find package information
    return None


def detect_is_bw_object(scenario: Scenario) -> bool:
    """Detect if this is a BW object based on data sources.
    
    Args:
        scenario: Parsed scenario
    
    Returns:
        True if BW object, False if ECC/other
    
    BW Indicators:
    - Table names start with /BIC/ or /BI0/
    - Schema name is "ABAP" (BW placeholder)
    - Data category is CUBE with BW characteristics
    """
    
    for data_source in scenario.data_sources.values():
        table_name = data_source.object_name or ""
        schema_name = data_source.schema_name or ""
        
        # BW table naming patterns
        if table_name.startswith("/BIC/") or table_name.startswith("/BI0/"):
            return True
        
        # BW generic schema
        if schema_name.upper() == "ABAP":
            return True
    
    return False


__all__ = ["generate_bw_wrapper", "detect_is_bw_object", "extract_bw_package_from_xml_path"]

