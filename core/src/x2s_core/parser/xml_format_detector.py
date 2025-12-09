"""XML format detection for HANA calculation views."""

from __future__ import annotations

from typing import Optional

from lxml import etree

from ..domain.types import XMLFormat, HanaVersion


def detect_xml_format(root: etree._Element) -> XMLFormat:
    """Detect whether XML is ColumnView or Calculation:scenario format.
    
    Args:
        root: Root element of the XML document
        
    Returns:
        XMLFormat enum value
        
    Raises:
        ValueError: If XML format is not recognized
    """
    tag = root.tag
    
    if 'ColumnView' in tag:
        return XMLFormat.COLUMN_VIEW
    elif 'scenario' in tag:
        return XMLFormat.CALCULATION_SCENARIO
    else:
        raise ValueError(f"Unknown XML format: {tag}")


def detect_hana_version_hint(root: etree._Element) -> Optional[HanaVersion]:
    """Attempt to detect HANA version from XML features (best effort).
    
    This function analyzes the XML structure and features to infer the
    minimum HANA version that would support the features used.
    
    Args:
        root: Root element of the XML document
        
    Returns:
        HanaVersion enum value or None if cannot be determined
    """
    # Check XML format - ColumnView is older
    try:
        xml_format = detect_xml_format(root)
        if xml_format == XMLFormat.COLUMN_VIEW:
            # ColumnView format is from HANA 1.0 era
            return HanaVersion.HANA_1_0
    except ValueError:
        pass
    
    # Check schemaVersion attribute
    schema_version = root.get('schemaVersion')
    
    # Look for version-specific node types (using namespace-aware search)
    nsmap = root.nsmap or {}
    
    # Check for HANA 2.0 SPS03+ features (Hierarchy, Window functions)
    # These would appear as specific calculationView types
    for calc_view in root.iter():
        if calc_view.tag.endswith('calculationView'):
            view_type = calc_view.get('{http://www.w3.org/2001/XMLSchema-instance}type', '')
            
            # Hierarchy nodes require HANA 2.0 SPS03+
            if 'HierarchyView' in view_type:
                return HanaVersion.HANA_2_0_SPS03
            
            # Window function nodes require HANA 2.0 SPS03+
            if 'WindowFunctionView' in view_type:
                return HanaVersion.HANA_2_0_SPS03
    
    # Check for HANA 2.0 SPS01+ features (Intersect, Minus)
    for calc_view in root.iter():
        if calc_view.tag.endswith('calculationView'):
            view_type = calc_view.get('{http://www.w3.org/2001/XMLSchema-instance}type', '')
            
            if 'IntersectView' in view_type or 'MinusView' in view_type:
                return HanaVersion.HANA_2_0_SPS01
    
    # Check for modern Calculation:scenario format (HANA 2.0)
    if root.tag.endswith('scenario'):
        # Modern format, likely HANA 2.0+
        return HanaVersion.HANA_2_0
    
    # Cannot determine - return None to use configured default
    return None


def get_recommended_hana_version(root: etree._Element, configured: Optional[HanaVersion] = None) -> HanaVersion:
    """Get recommended HANA version considering both XML hints and configuration.
    
    Args:
        root: Root element of the XML document
        configured: Configured HANA version (if any)
        
    Returns:
        Recommended HanaVersion enum value
    """
    detected = detect_hana_version_hint(root)
    
    # If detected version requires newer features, use it
    if detected:
        if configured:
            # Use the newer of the two
            detected_value = detected.value
            configured_value = configured.value
            
            # Simple comparison (works for our version naming)
            if detected_value > configured_value:
                return detected
        else:
            return detected
    
    # Fall back to configured or default
    return configured or HanaVersion.HANA_2_0

