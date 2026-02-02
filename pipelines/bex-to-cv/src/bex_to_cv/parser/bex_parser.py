"""Main BEx XML parser for asx:abap namespace.

This parser extracts BEx query structure from SAP BW BEx Query XML exports
and converts them into the BExQuery IR (Intermediate Representation).
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

from ..domain import (
    AggregationType,
    BExElement,
    BExElementType,
    BExKeyFigure,
    BExQuery,
    BExQueryMetadata,
    BExRange,
    BExSelection,
    BExVariable,
    DataType,
    RangeOperator,
    RangeSign,
    ReadMode,
    SelectionType,
)

logger = logging.getLogger(__name__)

# XML Namespaces used in BEx Query exports
NAMESPACES = {
    "asx": "http://www.sap.com/abapxml",
    "abap": "http://www.sap.com/abapxml/types/built-in",
}

# Known key figure InfoObjects (measures)
KEY_FIGURE_INFOOBJECTS = {
    "0QUANTITY",
    "0AMOUNT",
    "0VALUE",
    "0REVENUE",
    "0COST",
    "0PRICE",
    "0WEIGHT",
    "0VOLUME",
    "0NETVAL",
    "0GROSSVAL",
}


class BExParseError(Exception):
    """Raised when BEx XML parsing fails."""

    pass


def parse_bex_xml(xml_path: str) -> BExQuery:
    """Parse a BEx Query XML file.

    Args:
        xml_path: Path to the BEx XML file.

    Returns:
        BExQuery: Parsed query model.

    Raises:
        BExParseError: If parsing fails.
    """
    path = Path(xml_path)
    if not path.exists():
        raise BExParseError(f"File not found: {xml_path}")

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError as e:
        raise BExParseError(f"XML parsing error: {e}")

    return _parse_root(root, source_file=str(path))


def parse_bex_xml_string(xml_content: str, source_name: str = "string") -> BExQuery:
    """Parse BEx Query from XML string.

    Args:
        xml_content: XML content as string.
        source_name: Name to identify the source.

    Returns:
        BExQuery: Parsed query model.
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        raise BExParseError(f"XML parsing error: {e}")

    return _parse_root(root, source_file=source_name)


def _parse_root(root: ET.Element, source_file: str) -> BExQuery:
    """Parse the root element of BEx XML."""
    warnings: List[str] = []

    # Find the data section (asx:values/RSZCOMPDIR)
    # BEx exports use structure: asx:abap/asx:values/RSZCOMPDIR
    values = root.find(".//asx:values", NAMESPACES)
    if values is None:
        # Try without namespace
        values = root.find(".//values")
    if values is None:
        values = root  # Fallback to root

    # Find RSZCOMPDIR (main data container)
    rszcompdir = values.find("RSZCOMPDIR")
    if rszcompdir is None:
        rszcompdir = values.find(".//RSZCOMPDIR")
    if rszcompdir is None:
        # The root might already be the data container
        rszcompdir = values

    # Parse metadata from G_S_RKB1D
    metadata = _parse_metadata(rszcompdir, warnings)

    # Parse element directory from G_T_ELTDIR
    elements = _parse_elements(rszcompdir, warnings)

    # Parse variables from G_T_GLOBV
    variables = _parse_variables(rszcompdir, warnings)

    # Parse selections from G_T_SELECT
    selections = _parse_selections(rszcompdir, elements, warnings)

    # Parse ranges from G_T_RANGE
    ranges = _parse_ranges(rszcompdir, warnings)

    # Extract key figures from elements
    key_figures = _extract_key_figures(elements, warnings)

    return BExQuery(
        metadata=metadata,
        elements=elements,
        variables=variables,
        selections=selections,
        ranges=ranges,
        key_figures=key_figures,
        source_file=source_file,
        parse_warnings=warnings,
    )


def _parse_metadata(parent: ET.Element, warnings: List[str]) -> BExQueryMetadata:
    """Parse G_S_RKB1D section for query metadata."""
    rkb1d = parent.find(".//G_S_RKB1D")
    if rkb1d is None:
        warnings.append("G_S_RKB1D section not found, using defaults")
        return BExQueryMetadata(query_id="UNKNOWN", infocube="UNKNOWN")

    query_id = _get_text(rkb1d, "COMPID", "UNKNOWN")
    infocube = _get_text(rkb1d, "INFOCUBE", "UNKNOWN")
    read_mode_str = _get_text(rkb1d, "READMODE", "H")
    app_name = _get_text(rkb1d, "APPLNM", "")

    try:
        read_mode = ReadMode(read_mode_str)
    except ValueError:
        read_mode = ReadMode.H

    return BExQueryMetadata(
        query_id=query_id,
        infocube=infocube,
        read_mode=read_mode,
        application_name=app_name,
    )


def _parse_elements(parent: ET.Element, warnings: List[str]) -> Dict[str, BExElement]:
    """Parse G_T_ELTDIR section for element directory."""
    elements: Dict[str, BExElement] = {}

    eltdir = parent.find(".//G_T_ELTDIR")
    if eltdir is None:
        warnings.append("G_T_ELTDIR section not found")
        return elements

    for item in eltdir.findall("item"):
        eltuid = _get_text(item, "ELTUID", "")
        if not eltuid:
            continue

        deftp = _get_text(item, "DEFTP", "UNKNOWN")
        try:
            element_type = BExElementType(deftp)
        except ValueError:
            element_type = BExElementType.UNKNOWN

        element = BExElement(
            element_uid=eltuid,
            element_type=element_type,
            component_id=_get_text(item, "COMPID", ""),
            infoobject=_get_text(item, "IOBJNM", None) or None,
            key_figure_name=_get_text(item, "1KYFNM", None) or None,
        )
        elements[eltuid] = element

    logger.debug(f"Parsed {len(elements)} elements from G_T_ELTDIR")
    return elements


def _parse_variables(parent: ET.Element, warnings: List[str]) -> List[BExVariable]:
    """Parse G_T_GLOBV section for variables."""
    variables: List[BExVariable] = []

    globv = parent.find(".//G_T_GLOBV")
    if globv is None:
        warnings.append("G_T_GLOBV section not found")
        return variables

    for item in globv.findall("item"):
        vnam = _get_text(item, "VNAM", "")
        if not vnam:
            continue

        iobjnm = _get_text(item, "IOBJNM", "")
        vparsel = _get_text(item, "VPARSEL", "M")
        varinput = _get_text(item, "VARINPUT", "")
        optionfl = _get_text(item, "OPTIONFL", "")
        defaultv = _get_text(item, "DEFAULTV", "")

        try:
            selection_type = SelectionType(vparsel)
        except ValueError:
            selection_type = SelectionType.MULTIPLE

        variable = BExVariable(
            variable_name=vnam,
            infoobject=iobjnm,
            selection_type=selection_type,
            is_input=(varinput == "X"),
            is_mandatory=(optionfl != "X"),  # OPTIONFL='X' means optional
            default_value=defaultv,
        )
        variables.append(variable)

    logger.debug(f"Parsed {len(variables)} variables from G_T_GLOBV")
    return variables


def _parse_selections(
    parent: ET.Element,
    elements: Dict[str, BExElement],
    warnings: List[str],
) -> List[BExSelection]:
    """Parse G_T_SELECT section for selections/dimensions."""
    selections: List[BExSelection] = []

    select = parent.find(".//G_T_SELECT")
    if select is None:
        warnings.append("G_T_SELECT section not found")
        return selections

    for item in select.findall("item"):
        eltuid = _get_text(item, "ELTUID", "")
        if not eltuid:
            continue

        sotp = _get_text(item, "SOTP", "2")
        iobjnm = _get_text(item, "IOBJNM", "")
        chanm = _get_text(item, "CHANM", "")
        axsno = _get_text(item, "AXSNO", "000")

        try:
            selection_type = int(sotp)
        except ValueError:
            selection_type = 2

        try:
            axis_number = int(axsno)
        except ValueError:
            axis_number = 0

        selection = BExSelection(
            element_uid=eltuid,
            infoobject=iobjnm or chanm,  # Fallback to characteristic name
            characteristic=chanm,
            selection_type=selection_type,
            axis_number=axis_number,
        )
        selections.append(selection)

    logger.debug(f"Parsed {len(selections)} selections from G_T_SELECT")
    return selections


def _parse_ranges(
    parent: ET.Element,
    warnings: List[str],
) -> Dict[str, List[BExRange]]:
    """Parse G_T_RANGE section for filter conditions."""
    ranges: Dict[str, List[BExRange]] = {}

    range_section = parent.find(".//G_T_RANGE")
    if range_section is None:
        warnings.append("G_T_RANGE section not found")
        return ranges

    for item in range_section.findall("item"):
        # Each item contains ELTUID and a RANGE table
        eltuid = _get_text(item, "ELTUID", "")
        if not eltuid:
            continue

        range_table = item.find("RANGE")
        if range_table is None:
            continue

        element_ranges: List[BExRange] = []
        for range_item in range_table.findall("item"):
            sign = _get_text(range_item, "SIGN", "I")
            opt = _get_text(range_item, "OPT", "EQ")
            low = _get_text(range_item, "LOW", "")
            high = _get_text(range_item, "HIGH", "")

            try:
                range_sign = RangeSign(sign)
            except ValueError:
                range_sign = RangeSign.INCLUDE

            try:
                range_operator = RangeOperator(opt)
            except ValueError:
                range_operator = RangeOperator.EQ

            bex_range = BExRange(
                sign=range_sign,
                operator=range_operator,
                low=low,
                high=high,
            )
            element_ranges.append(bex_range)

        if element_ranges:
            ranges[eltuid] = element_ranges

    logger.debug(f"Parsed ranges for {len(ranges)} elements from G_T_RANGE")
    return ranges


def _extract_key_figures(
    elements: Dict[str, BExElement],
    warnings: List[str],
) -> List[BExKeyFigure]:
    """Extract key figures from elements.

    Key figures are identified by:
    1. Element type is KYF (key figure) or CKF (calculated key figure)
    2. InfoObject is a known key figure InfoObject (0QUANTITY, 0AMOUNT, etc.)
    3. 1KYFNM field is populated
    """
    key_figures: List[BExKeyFigure] = []

    for eltuid, element in elements.items():
        is_key_figure = False
        infoobject = element.infoobject or ""

        # Check if element type indicates key figure
        if element.element_type in (
            BExElementType.KYF,
            BExElementType.CKF,
            BExElementType.RKF,
        ):
            is_key_figure = True

        # Check if InfoObject is a known key figure
        if infoobject.upper() in KEY_FIGURE_INFOOBJECTS:
            is_key_figure = True

        # Check if 1KYFNM is populated
        if element.key_figure_name:
            is_key_figure = True

        if is_key_figure:
            key_figure = BExKeyFigure(
                element_uid=eltuid,
                infoobject=infoobject,
                name=element.key_figure_name or infoobject,
                aggregation=AggregationType.SUM,  # Default to SUM
                data_type=DataType.DEC,  # Default to decimal
            )
            key_figures.append(key_figure)

    logger.debug(f"Extracted {len(key_figures)} key figures")
    return key_figures


def _get_text(parent: ET.Element, tag: str, default: str = "") -> str:
    """Get text content of a child element."""
    element = parent.find(tag)
    if element is not None and element.text:
        return element.text.strip()
    return default


def validate_bex_query(query: BExQuery) -> Tuple[bool, List[str]]:
    """Validate a parsed BEx query for completeness.

    Returns:
        Tuple of (is_valid, list of validation errors)
    """
    errors: List[str] = []

    # Check required metadata
    if query.metadata.query_id == "UNKNOWN":
        errors.append("Query ID (COMPID) is missing")
    if query.metadata.infocube == "UNKNOWN":
        errors.append("InfoCube is missing")

    # Check for at least one selection or key figure
    if not query.selections and not query.key_figures:
        errors.append("Query has no selections or key figures")

    # Warn about variables without InfoObjects
    for var in query.variables:
        if not var.infoobject:
            errors.append(f"Variable {var.variable_name} has no InfoObject")

    return len(errors) == 0, errors
