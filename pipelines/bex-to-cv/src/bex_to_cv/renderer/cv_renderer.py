"""HANA Calculation View XML Renderer.

This renderer converts a BExQuery IR (Intermediate Representation) into
a valid HANA Calculation View XML (.hdbcalculationview format).
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from lxml import etree

from ..catalog import get_infoobject, get_table_mapping, InfoObjectMetadata
from ..domain import (
    BExKeyFigure,
    BExQuery,
    BExSelection,
    BExVariable,
    RangeSign,
    SelectionType,
)

logger = logging.getLogger(__name__)

# XML Namespaces for HANA Calculation View
CV_NSMAP = {
    None: "http://www.sap.com/ndb/BiModelCalculationView.ecore",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}

# Element namespace for type declarations
XSI_TYPE = "{http://www.w3.org/2001/XMLSchema-instance}type"


@dataclass
class RenderContext:
    """Context for rendering CV XML."""

    query: BExQuery
    schema: str = "SAPABAP1"
    package_path: str = ""
    view_name: str = ""
    node_counter: int = 0
    warnings: List[str] = field(default_factory=list)

    def next_node_id(self, prefix: str = "node") -> str:
        """Generate unique node ID."""
        self.node_counter += 1
        return f"{prefix}_{self.node_counter}"


class CVRenderError(Exception):
    """Raised when CV rendering fails."""

    pass


def render_calculation_view(
    query: BExQuery,
    schema: str = "SAPABAP1",
    package_path: str = "",
) -> str:
    """Render a BExQuery as a HANA Calculation View XML.

    Args:
        query: The BExQuery IR to render.
        schema: Target HANA schema.
        package_path: Optional HANA package path.

    Returns:
        XML string of the Calculation View.

    Raises:
        CVRenderError: If rendering fails.
    """
    # Determine view name from query
    view_name = f"CV_{query.metadata.query_id}"

    ctx = RenderContext(
        query=query,
        schema=schema,
        package_path=package_path,
        view_name=view_name,
    )

    try:
        root = _build_cv_root(ctx)
        _add_input_parameters(root, ctx)
        _add_data_sources(root, ctx)
        _add_calculation_nodes(root, ctx)
        _add_output_node(root, ctx)
        _add_layout(root, ctx)

        # Serialize to XML string
        xml_string = etree.tostring(
            root,
            pretty_print=True,
            xml_declaration=True,
            encoding="UTF-8",
        ).decode("utf-8")

        return xml_string

    except Exception as e:
        raise CVRenderError(f"Failed to render CV: {e}")


def _build_cv_root(ctx: RenderContext) -> etree._Element:
    """Build the root Calculation:scenario element."""
    root = etree.Element(
        "Calculation:scenario",
        nsmap={
            "Calculation": "http://www.sap.com/ndb/BiModelCalculation.ecore",
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
        },
        attrib={
            "id": ctx.view_name,
            "applyPrivilegeType": "NONE",
            "dataCategory": "CUBE",
            "dimensionType": "STANDARD",
            "schemaVersion": "3.0",
            "outputViewType": "Aggregation",
            "enforceSqlExecution": "false",
        },
    )

    # Add metadata section
    metadata = etree.SubElement(root, "metadata")
    metadata.set("activatedAt", datetime.now().isoformat())
    metadata.set("activatedBy", "BEX_TO_CV_CONVERTER")

    # Add origin section
    origin = etree.SubElement(metadata, "origin")
    origin.text = f"BEx Query: {ctx.query.metadata.query_id}"

    return root


def _add_input_parameters(root: etree._Element, ctx: RenderContext) -> None:
    """Add input parameters from BEx variables."""
    local_variables = etree.SubElement(root, "localVariables")

    for variable in ctx.query.get_input_variables():
        param_name = variable.to_input_parameter_name()

        # Determine parameter type from InfoObject
        infoobject_meta = get_infoobject(variable.infoobject)
        data_type = _get_hana_type(infoobject_meta)
        length = _get_type_length(infoobject_meta)

        var_elem = etree.SubElement(local_variables, "variable")
        var_elem.set("id", param_name)
        var_elem.set("parameter", "true")

        # Add mandatory/optional attribute
        if variable.is_mandatory:
            var_elem.set("mandatory", "true")
        else:
            var_elem.set("mandatory", "false")

        # Add selection type
        if variable.selection_type == SelectionType.MULTIPLE:
            var_elem.set("selectionType", "MultiRange")
        else:
            var_elem.set("selectionType", "SingleValue")

        # Add default value if present
        if variable.default_value:
            var_elem.set("defaultValue", variable.default_value)

        # Add data type
        var_type = etree.SubElement(var_elem, "variableProperties")
        var_type.set("datatype", data_type)
        if length > 0:
            var_type.set("length", str(length))

        logger.debug(f"Added input parameter: {param_name}")


def _add_data_sources(root: etree._Element, ctx: RenderContext) -> None:
    """Add data sources (fact tables) to the CV."""
    data_sources = etree.SubElement(root, "dataSources")

    # Get table mapping for the InfoCube
    table_mapping = get_table_mapping(ctx.query.metadata.infocube)

    if table_mapping:
        fact_table = table_mapping.fact_table
        schema = table_mapping.schema
    else:
        # Fallback: use InfoCube name as table name
        fact_table = ctx.query.metadata.infocube
        schema = ctx.schema
        ctx.warnings.append(
            f"No table mapping found for InfoCube {ctx.query.metadata.infocube}, "
            f"using {schema}.{fact_table}"
        )

    # Add the main data source
    ds = etree.SubElement(data_sources, "DataSource")
    ds.set("id", "fact_table")
    ds.set("type", "DATA_BASE_TABLE")

    resource_uri = etree.SubElement(ds, "resourceUri")
    resource_uri.text = f"{schema}.{fact_table}"

    logger.debug(f"Added data source: {schema}.{fact_table}")


def _add_calculation_nodes(root: etree._Element, ctx: RenderContext) -> None:
    """Add calculation nodes (Projection, Join, etc.)."""
    calc_nodes = etree.SubElement(root, "calculationViews")

    # Create projection node for base table
    projection = _create_projection_node(ctx, "Projection_1")
    calc_nodes.append(projection)

    # If there are filter conditions, add them to the projection
    _add_filters_to_projection(projection, ctx)


def _create_projection_node(ctx: RenderContext, node_id: str) -> etree._Element:
    """Create a Projection node for column selection."""
    projection = etree.Element("calculationView")
    projection.set(XSI_TYPE, "Calculation:ProjectionView")
    projection.set("id", node_id)

    # Add input from data source
    view_attrs = etree.SubElement(projection, "viewAttributes")

    # Add dimension columns
    for selection in ctx.query.get_dimensions():
        infoobj_meta = get_infoobject(selection.infoobject)
        column_name = _get_column_name(selection.infoobject, infoobj_meta)

        view_attr = etree.SubElement(view_attrs, "viewAttribute")
        view_attr.set("id", column_name)

    # Add key figure columns
    for key_figure in ctx.query.key_figures:
        infoobj_meta = get_infoobject(key_figure.infoobject)
        column_name = _get_column_name(key_figure.infoobject, infoobj_meta)

        view_attr = etree.SubElement(view_attrs, "viewAttribute")
        view_attr.set("id", column_name)
        view_attr.set("aggregationType", str(key_figure.aggregation.value))

    # Add calculated columns from variables (as filters)
    calc_attrs = etree.SubElement(projection, "calculatedViewAttributes")

    # Add input reference
    input_elem = etree.SubElement(projection, "input")
    input_elem.set("node", "fact_table")

    return projection


def _add_filters_to_projection(
    projection: etree._Element,
    ctx: RenderContext,
) -> None:
    """Add filter expressions from BEx ranges and variables."""
    filter_conditions: List[str] = []

    # Add variable-based filters
    for variable in ctx.query.get_input_variables():
        param_name = variable.to_input_parameter_name()
        infoobj_meta = get_infoobject(variable.infoobject)
        column_name = _get_column_name(variable.infoobject, infoobj_meta)

        # Generate filter expression using parameter
        if variable.selection_type == SelectionType.MULTIPLE:
            # For multi-value parameters, use IN with APPLY_FILTER
            filter_expr = f'"{column_name}" = $${param_name}$$'
        else:
            filter_expr = f'"{column_name}" = $${param_name}$$'

        filter_conditions.append(filter_expr)

    # Add range-based filters
    for eltuid, ranges in ctx.query.ranges.items():
        # Find the selection for this element
        selection = next(
            (s for s in ctx.query.selections if s.element_uid == eltuid),
            None,
        )
        if selection:
            infoobj_meta = get_infoobject(selection.infoobject)
            column_name = _get_column_name(selection.infoobject, infoobj_meta)

            for bex_range in ranges:
                condition = bex_range.to_sql_condition(column_name)
                filter_conditions.append(condition)

    # Add filter expression to projection
    if filter_conditions:
        filter_elem = etree.SubElement(projection, "filter")
        filter_expr = etree.SubElement(filter_elem, "expression")
        filter_expr.set("language", "SQL")
        # Combine all conditions with AND
        combined = " AND ".join(f"({c})" for c in filter_conditions)
        filter_expr.text = combined


def _add_output_node(root: etree._Element, ctx: RenderContext) -> None:
    """Add the output aggregation node."""
    logical_model = etree.SubElement(root, "logicalModel")
    logical_model.set("id", ctx.view_name)

    # Add attributes section
    attributes = etree.SubElement(logical_model, "attributes")

    for selection in ctx.query.get_dimensions():
        infoobj_meta = get_infoobject(selection.infoobject)
        column_name = _get_column_name(selection.infoobject, infoobj_meta)

        attr = etree.SubElement(attributes, "attribute")
        attr.set("id", column_name)
        attr.set("order", str(ctx.query.selections.index(selection) + 1))
        attr.set("displayAttribute", "false")
        attr.set("attributeHierarchyActive", "false")

        # Add key mapping
        key_mapping = etree.SubElement(attr, "keyMapping")
        key_mapping.set("columnObjectName", "Projection_1")
        key_mapping.set("columnName", column_name)

    # Add measures section
    measures = etree.SubElement(logical_model, "baseMeasures")

    for key_figure in ctx.query.key_figures:
        infoobj_meta = get_infoobject(key_figure.infoobject)
        column_name = _get_column_name(key_figure.infoobject, infoobj_meta)

        measure = etree.SubElement(measures, "measure")
        measure.set("id", column_name)
        measure.set("order", str(ctx.query.key_figures.index(key_figure) + 1))
        measure.set("aggregationType", str(key_figure.aggregation.value))
        measure.set("measureType", "simple")

        # Add mapping
        measure_mapping = etree.SubElement(measure, "measureMapping")
        measure_mapping.set("columnObjectName", "Projection_1")
        measure_mapping.set("columnName", column_name)


def _add_layout(root: etree._Element, ctx: RenderContext) -> None:
    """Add layout information for HANA Studio visualization."""
    layout = etree.SubElement(root, "layout")
    layout.set("schemaVersion", "3.0")

    shapes = etree.SubElement(layout, "shapes")

    # Add shape for projection node
    shape = etree.SubElement(shapes, "shape")
    shape.set("expanded", "true")
    shape.set("modelObjectName", "Projection_1")
    shape.set("modelObjectNameSpace", "CalculationView")

    # Add shape for output
    output_shape = etree.SubElement(shapes, "shape")
    output_shape.set("expanded", "true")
    output_shape.set("modelObjectName", ctx.view_name)
    output_shape.set("modelObjectNameSpace", "CalculationView")


def _get_hana_type(infoobject_meta: Optional[InfoObjectMetadata]) -> str:
    """Map InfoObject data type to HANA type."""
    if infoobject_meta is None:
        return "NVARCHAR"

    type_map = {
        "NVARCHAR": "NVARCHAR",
        "CHAR": "NVARCHAR",
        "NUMC": "NVARCHAR",
        "DATE": "DATE",
        "DATS": "DATE",
        "TIME": "TIME",
        "TIMS": "TIME",
        "DECIMAL": "DECIMAL",
        "DEC": "DECIMAL",
        "CURR": "DECIMAL",
        "QUAN": "DECIMAL",
        "INT1": "TINYINT",
        "INT2": "SMALLINT",
        "INT4": "INTEGER",
        "FLTP": "DOUBLE",
        "STRING": "NVARCHAR",
    }
    return type_map.get(infoobject_meta.data_type, "NVARCHAR")


def _get_type_length(infoobject_meta: Optional[InfoObjectMetadata]) -> int:
    """Get type length from InfoObject metadata."""
    if infoobject_meta is None:
        return 0
    return infoobject_meta.length


def _get_column_name(
    infoobject: str,
    infoobject_meta: Optional[InfoObjectMetadata],
) -> str:
    """Determine column name from InfoObject.

    Uses the key column from master data if available,
    otherwise uses the InfoObject name.
    """
    if infoobject_meta and infoobject_meta.key_column:
        return infoobject_meta.key_column

    # Strip leading "0" from standard InfoObjects
    if infoobject.startswith("0"):
        return infoobject[1:]

    return infoobject
