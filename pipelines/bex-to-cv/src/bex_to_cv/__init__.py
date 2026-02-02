"""
BEx-to-CV Pipeline

Convert SAP BW BEx Query XML to HANA Calculation View XML.

This pipeline parses the asx:abap namespace BEx query definitions and generates
valid .hdbcalculationview XML files that can be imported into HANA Studio.

Architecture:
    BEx XML (asx:abap) -> Parser -> BExQuery IR -> CV Renderer -> CV XML
"""

__version__ = "0.1.0"

# Main conversion function
from .parser import BExParseError, parse_bex_xml, parse_bex_xml_string, validate_bex_query
from .renderer import CVRenderError, render_calculation_view

__all__ = [
    # Version
    "__version__",
    # Parser
    "parse_bex_xml",
    "parse_bex_xml_string",
    "validate_bex_query",
    "BExParseError",
    # Renderer
    "render_calculation_view",
    "CVRenderError",
]


def convert_bex_to_cv(
    xml_path: str,
    schema: str = "SAPABAP1",
    package_path: str = "",
) -> str:
    """Convert a BEx Query XML file to HANA Calculation View XML.

    This is the main entry point for the bex-to-cv pipeline.

    Args:
        xml_path: Path to the BEx XML file.
        schema: Target HANA schema (default: SAPABAP1).
        package_path: Optional HANA package path.

    Returns:
        CV XML string.

    Raises:
        BExParseError: If parsing fails.
        CVRenderError: If rendering fails.
    """
    # Parse BEx XML
    query = parse_bex_xml(xml_path)

    # Validate query
    is_valid, errors = validate_bex_query(query)
    if not is_valid:
        raise BExParseError(f"Validation errors: {', '.join(errors)}")

    # Render to CV XML
    return render_calculation_view(query, schema=schema, package_path=package_path)
