"""Parser that converts SAP HANA calculation-view XML into Scenario IR objects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from lxml import etree

from ..domain import (
    AggregationNode,
    AggregationSpec,
    AttributeMapping,
    CalculatedAttribute,
    CurrencyConversion,
    DataSource,
    DataSourceType,
    DataTypeSpec,
    Expression,
    ExpressionType,
    JoinCondition,
    JoinNode,
    JoinType,
    LogicalAttribute,
    LogicalCalculatedAttribute,
    LogicalMeasure,
    LogicalModel,
    Node,
    NodeKind,
    Predicate,
    PredicateKind,
    Scenario,
    ScenarioMetadata,
    SnowflakeType,
    UnionNode,
    Variable,
)
from .column_view_parser import parse_column_view
from .type_inference import guess_attribute_type, guess_literal_type


_NS = {
    "calc": "http://www.sap.com/ndb/BiModelCalculation.ecore",
    "acc": "http://www.sap.com/ndb/SQLCoreModelAccessControl.ecore",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}


def _find_children(element: etree._Element, *tags: str) -> List[etree._Element]:
    """Find child elements that may or may not be prefixed with the calc namespace."""
    current: List[etree._Element] = [element]
    for tag in tags:
        next_level: List[etree._Element] = []
        for parent in current:
            next_level.extend(parent.findall(f"./calc:{tag}", namespaces=_NS))
            next_level.extend(parent.findall(f"./{tag}"))
        current = next_level
    return current


def _find_child(element: etree._Element, *tags: str) -> Optional[etree._Element]:
    children = _find_children(element, *tags)
    return children[0] if children else None


def _get_default_description(element: etree._Element) -> Optional[str]:
    descriptions_el = _find_child(element, "descriptions")
    if descriptions_el is not None:
        value = descriptions_el.get("defaultDescription")
        if value:
            return value
    return None


@dataclass(slots=True)
class ParseContext:
    scenario: Scenario
    path: Path


def parse_scenario(path: Path) -> Scenario:
    """Parse an XML calculation scenario into a Scenario IR object."""

    tree = etree.parse(str(path))
    root = tree.getroot()

    try:
        root_tag = etree.QName(root).localname
    except Exception:  # pragma: no cover - fallback for unexpected structures
        root_tag = root.tag

    if root_tag == "ColumnView":
        return parse_column_view(path, root)

    metadata = ScenarioMetadata(
        scenario_id=root.get("id"),
        description=_get_default_description(root),
        default_client=root.get("defaultClient"),
        default_language=root.get("defaultLanguage"),
    )
    scenario = Scenario(metadata=metadata)
    ctx = ParseContext(scenario=scenario, path=path)

    _parse_data_sources(ctx, root)
    _parse_variables(ctx, root)
    _parse_nodes(ctx, root)
    _parse_logical_model(ctx, root)
    return scenario


def _parse_data_sources(ctx: ParseContext, root: etree._Element) -> None:
    for ds_el in _find_children(root, "dataSources", "DataSource"):
        source_id = ds_el.get("id")
        ds_type = ds_el.get("type", "DATA_BASE_TABLE")
        schema_name: Optional[str] = None
        object_name: Optional[str] = None

        column_obj = _find_child(ds_el, "columnObject")
        if column_obj is not None:
            schema_name = column_obj.get("schemaName")
            object_name = column_obj.get("columnObjectName")
        resource = _find_child(ds_el, "resourceUri")
        resource_uri: Optional[str] = None
        if resource is not None:
            resource_uri = (resource.text or "") or resource.get("{http://www.w3.org/1999/xlink}href", "")
            if resource_uri:
                # BUG-027: Strip internal HANA Studio folder paths from resourceUri
                # These folders (/calculationviews/, /analyticviews/, /attributeviews/) are
                # XML organization folders in HANA Studio, not part of the actual view path
                # Example: /KMDM/calculationviews/MATERIAL_DETAILS -> KMDM/MATERIAL_DETAILS
                object_name = resource_uri
                for internal_folder in ['/calculationviews/', '/analyticviews/', '/attributeviews/']:
                    object_name = object_name.replace(internal_folder, '/')
                # Strip leading slash - resourceUri paths start with / but SQL references don't
                if object_name.startswith('/'):
                    object_name = object_name[1:]

        mapped_type = _map_data_source_type(ds_type)
        ctx.scenario.data_sources[source_id] = DataSource(
            source_id=source_id,
            source_type=mapped_type,
            schema_name=schema_name or "",
            object_name=object_name or "",
            resource_uri=resource_uri,
        )


def _parse_nodes(ctx: ParseContext, root: etree._Element) -> None:
    for node_el in _find_children(root, "calculationViews", "calculationView"):
        xsi_type = node_el.get(f"{{{_NS['xsi']}}}type", "")
        node_id = node_el.get("id")

        # BUG-028 FIX: Handle both view node references and table entity inputs
        inputs = []
        for inp in _find_children(node_el, "input"):
            # Check if input has a 'node' attribute (old-style reference)
            node_ref = inp.get("node", "")
            if node_ref:
                inputs.append(_clean_ref(node_ref))
                continue

            # Check if input has viewNode/dataSource child element (new-style reference)
            view_node_el = _find_child(inp, "viewNode")
            if view_node_el is not None and view_node_el.text:
                inputs.append(_clean_ref(view_node_el.text))
                continue

            data_source_el = _find_child(inp, "dataSource")
            if data_source_el is not None and data_source_el.text:
                inputs.append(_clean_ref(data_source_el.text))
                continue

            # Check if input has an entity element (table reference)
            entity_el = _find_child(inp, "entity")
            if entity_el is not None and entity_el.text:
                # Parse entity to get schema and table name
                from ..parser.column_view_parser import _parse_entity
                schema_name, object_name = _parse_entity(entity_el.text)

                # Get or create alias for this table
                alias = inp.get("alias", object_name.lower() if object_name else "table")

                # Create a synthetic projection node ID for this table
                synthetic_node_id = f"_synthetic_proj_{alias}"

                # Create DataSource if not exists
                if synthetic_node_id not in ctx.scenario.data_sources:
                    # BUG-025: Detect CV references and set correct source_type
                    # CV references have "CV_" prefix in object name or "::" in original entity text
                    is_cv_reference = (object_name and object_name.startswith("CV_")) or (entity_el.text and "::" in entity_el.text)
                    source_type = DataSourceType.CALCULATION_VIEW if is_cv_reference else DataSourceType.DATA_BASE_TABLE
                    
                    ctx.scenario.data_sources[synthetic_node_id] = DataSource(
                        source_id=synthetic_node_id,
                        source_type=source_type,
                        schema_name=schema_name or "",
                        object_name=object_name or "",
                        resource_uri=None,
                    )

                # Create synthetic projection node with mappings from input element
                mappings_from_input = []
                for mapping_el in _find_children(inp, "mapping"):
                    target_name = mapping_el.get("targetName", "")
                    source_name = mapping_el.get("sourceName", "")
                    if target_name and source_name:
                        mappings_from_input.append(
                            AttributeMapping(
                                target_name=target_name,
                                source_name=None,
                                expression=Expression(
                                    expression_type=ExpressionType.COLUMN,
                                    value=source_name,
                                    data_type=None,
                                ),
                                data_type=None,
                            )
                        )

                # Create synthetic projection node
                synthetic_projection = Node(
                    node_id=synthetic_node_id,
                    kind=NodeKind.PROJECTION,
                    inputs=[synthetic_node_id],  # Reference the data source
                    mappings=mappings_from_input,
                    filters=[],
                    view_attributes=[],
                    calculated_attributes={},
                )

                # Add synthetic projection to scenario
                ctx.scenario.add_node(synthetic_projection)

                # Use synthetic projection node ID as input
                inputs.append(synthetic_node_id)

        node_type = xsi_type.split(":")[-1] if xsi_type else ""
        if node_type.endswith("ProjectionView"):
            parsed = _parse_projection(node_el, node_id, inputs)
        elif node_type.endswith("JoinView"):
            parsed = _parse_join(node_el, node_id, inputs)
        elif node_type.endswith("AggregationView"):
            parsed = _parse_aggregation(node_el, node_id, inputs)
        elif node_type.endswith("UnionView"):
            parsed = _parse_union(node_el, node_id, inputs)
        else:
            view_attrs = _parse_view_attribute_ids(node_el)
            calculated_attrs = _parse_calculated_view_attributes(node_el)
            mappings, _ = _parse_mappings(node_el)
            filters = _parse_filters(node_el)
            parsed = Node(
                node_id=node_id,
                kind=NodeKind.CALCULATION,
                inputs=inputs,
                mappings=mappings,
                filters=filters,
                view_attributes=view_attrs,
                calculated_attributes=calculated_attrs,
            )
        ctx.scenario.add_node(parsed)


def _parse_variables(ctx: ParseContext, root: etree._Element) -> None:
    for var_el in _find_children(root, "localVariables", "variable"):
        var_id = var_el.get("id")
        if not var_id:
            continue
        description = _get_default_description(var_el)
        properties_el = _find_child(var_el, "variableProperties")
        data_type = properties_el.get("datatype") if properties_el is not None else None
        default_value = properties_el.get("defaultValue") if properties_el is not None else None
        mandatory = (
            properties_el.get("mandatory", "false").lower() == "true" if properties_el is not None else False
        )
        selection_type: Optional[str] = None
        multi_line: Optional[bool] = None
        attribute_name: Optional[str] = None
        if properties_el is not None:
            selection_el = _find_child(properties_el, "selection")
            if selection_el is not None:
                selection_type = selection_el.get("type")
                multi_attr = selection_el.get("multiLine")
                if multi_attr is not None:
                    multi_line = multi_attr.lower() == "true"
            value_domain_el = _find_child(properties_el, "valueDomain")
            if value_domain_el is not None:
                attribute_el = _find_child(value_domain_el, "attribute")
                if attribute_el is not None:
                    attribute_name = attribute_el.get("name")
        ctx.scenario.variables.append(
            Variable(
                variable_id=var_id,
                description=description,
                data_type=data_type,
                mandatory=mandatory,
                default_value=default_value,
                selection_type=selection_type,
                multi_line=multi_line,
                attribute_name=attribute_name,
            )
        )


def _parse_projection(node_el: etree._Element, node_id: str, inputs: List[str]) -> Node:
    mappings, _ = _parse_mappings(node_el)
    filters = _parse_filters(node_el)
    view_attrs = _parse_view_attribute_ids(node_el)
    calculated_attrs = _parse_calculated_view_attributes(node_el)
    return Node(
        node_id=node_id,
        kind=NodeKind.PROJECTION,
        inputs=inputs,
        mappings=mappings,
        filters=filters,
        view_attributes=view_attrs,
        calculated_attributes=calculated_attrs,
    )


def _parse_join(node_el: etree._Element, node_id: str, inputs: List[str]) -> JoinNode:
    mappings, per_input = _parse_mappings(node_el)
    filters = _parse_filters(node_el)
    join_type = _map_join_type(node_el.get("joinType", "inner"))
    join_attrs = list(_iter_join_attributes(node_el))
    conditions = _build_join_conditions(join_attrs, per_input)
    properties = {}
    join_order = node_el.get("joinOrder")
    if join_order:
        properties["joinOrder"] = join_order
    view_attrs = _parse_view_attribute_ids(node_el)
    calculated_attrs = _parse_calculated_view_attributes(node_el)
    return JoinNode(
        node_id=node_id,
        kind=NodeKind.JOIN,
        inputs=inputs,
        mappings=mappings,
        filters=filters,
        join_type=join_type,
        conditions=conditions,
        properties=properties,
        view_attributes=view_attrs,
        calculated_attributes=calculated_attrs,
    )


def _parse_aggregation(node_el: etree._Element, node_id: str, inputs: List[str]) -> AggregationNode:
    mappings, _ = _parse_mappings(node_el)
    filters = _parse_filters(node_el)
    view_attrs = _parse_view_attribute_ids(node_el)
    calculated_attrs = _parse_calculated_view_attributes(node_el)
    group_by: List[str] = []
    aggregations: List[AggregationSpec] = []
    for attr_el in _find_children(node_el, "viewAttributes", "viewAttribute"):
        attr_id = attr_el.get("id")
        if not attr_id:
            continue
        agg_type = attr_el.get("aggregationType")
        if agg_type:
            base_expr = Expression(ExpressionType.COLUMN, attr_id, guess_attribute_type(attr_id))
            aggregations.append(
                AggregationSpec(
                    target_name=attr_id,
                    function=agg_type.upper(),
                    expression=base_expr,
                    data_type=guess_attribute_type(attr_id),
                )
            )
        else:
            group_by.append(attr_id)
    return AggregationNode(
        node_id=node_id,
        kind=NodeKind.AGGREGATION,
        inputs=inputs,
        mappings=mappings,
        filters=filters,
        group_by=group_by,
        aggregations=aggregations,
        view_attributes=view_attrs,
        calculated_attributes=calculated_attrs,
    )


def _parse_union(node_el: etree._Element, node_id: str, inputs: List[str]) -> UnionNode:
    """Parse a UnionView node."""
    mappings, _ = _parse_mappings(node_el)
    filters = _parse_filters(node_el)
    view_attrs = _parse_view_attribute_ids(node_el)
    calculated_attrs = _parse_calculated_view_attributes(node_el)
    union_all = True
    return UnionNode(
        node_id=node_id,
        kind=NodeKind.UNION,
        inputs=inputs,
        mappings=mappings,
        filters=filters,
        view_attributes=view_attrs,
        calculated_attributes=calculated_attrs,
        union_all=union_all,
    )


def _parse_mappings(node_el: etree._Element) -> Tuple[List[AttributeMapping], List[Tuple[str, Dict[str, AttributeMapping]]]]:
    mappings: List[AttributeMapping] = []
    per_input: List[Tuple[str, Dict[str, AttributeMapping]]] = []
    for input_el in _find_children(node_el, "input"):
        source_ref = _clean_ref(input_el.get("node", ""))
        collected: Dict[str, AttributeMapping] = {}
        for mapping_el in _find_children(input_el, "mapping"):
            target = mapping_el.get("target") or mapping_el.get("targetName")
            source = mapping_el.get("source") or mapping_el.get("sourceName")
            if not target or not source:
                continue
            data_type = guess_attribute_type(target)
            expr = Expression(ExpressionType.COLUMN, source, data_type)
            mapping = AttributeMapping(
                target_name=target,
                expression=expr,
                data_type=data_type,
                source_node=source_ref or None,
            )
            mappings.append(mapping)
            collected[target] = mapping
        per_input.append((source_ref or "", collected))
    return mappings, per_input


def _parse_filters(node_el: etree._Element) -> List[Predicate]:
    predicates: List[Predicate] = []
    for attr_el in _find_children(node_el, "viewAttributes", "viewAttribute"):
        column_name = attr_el.get("id")
        if not column_name:
            continue
        filter_el = attr_el.find("./acc:filter", namespaces=_NS) or _find_child(attr_el, "filter")
        if filter_el is None:
            continue

        # Get the including attribute (default True)
        including = filter_el.get("including", "true").lower() == "true"
        left_expr = Expression(ExpressionType.COLUMN, column_name, guess_attribute_type(column_name))

        # Check for SingleValueFilter (direct value attribute)
        value = filter_el.get("value")
        if value is not None:
            literal_type = guess_literal_type(value) or guess_attribute_type(column_name)
            right_expr = Expression(ExpressionType.LITERAL, value, literal_type)
            predicates.append(
                Predicate(
                    kind=PredicateKind.COMPARISON,
                    left=left_expr,
                    operator=_map_filter_operator(filter_el.get("operator")),
                    right=right_expr,
                    including=including,
                )
            )
            continue

        # BUG-035: Check for ListValueFilter with <operands> children
        operands = filter_el.findall("./acc:operands", namespaces=_NS)
        if not operands:
            operands = filter_el.findall(".//operands")
        if operands:
            # Collect all operand values
            values = []
            for operand in operands:
                op_value = operand.get("value")
                if op_value is not None:
                    # Quote string values
                    values.append(f"'{op_value}'")
            if values:
                # Create IN list expression like "('value1', 'value2')"
                in_list = f"({', '.join(values)})"
                right_expr = Expression(ExpressionType.RAW, in_list, "VARCHAR")
                predicates.append(
                    Predicate(
                        kind=PredicateKind.COMPARISON,
                        left=left_expr,
                        operator="IN",  # Will be negated to NOT IN if including=False
                        right=right_expr,
                        including=including,
                    )
                )

    return predicates


def _iter_join_attributes(node_el: etree._Element) -> Iterable[str]:
    """Extract join attribute names from a join node element."""
    # Try with namespace first
    for join_attr in node_el.findall("./calc:joinAttribute", namespaces=_NS):
        name = join_attr.get("name")
        if name:
            yield name
    # Also try without namespace (some XML files may not use namespaces consistently)
    for join_attr in node_el.findall(".//joinAttribute"):
        name = join_attr.get("name")
        if name:
            yield name


def _build_join_conditions(
    join_attributes: Sequence[str],
    per_input: List[Tuple[str, Dict[str, AttributeMapping]]],
) -> List[JoinCondition]:
    if not join_attributes or len(per_input) < 2:
        return []

    conditions: List[JoinCondition] = []
    left_source, left_mappings = per_input[0]
    for right_source, right_mappings in per_input[1:]:
        for join_name in join_attributes:
            left_mapping = _resolve_join_mapping(join_name, left_mappings)
            right_mapping = _resolve_join_mapping(join_name, right_mappings)
            if not left_mapping or not right_mapping:
                continue
            left_expr = _mapping_to_join_expression(left_mapping)
            right_expr = _mapping_to_join_expression(right_mapping)
            conditions.append(
                JoinCondition(
                    left=left_expr,
                    right=right_expr,
                )
            )
    return conditions


def _resolve_join_mapping(name: str, mappings: Dict[str, AttributeMapping]) -> Optional[AttributeMapping]:
    """Resolve a join attribute name to an AttributeMapping.
    
    Tries multiple strategies:
    1. Exact match by target name
    2. Match by segments (for JOIN$X$Y patterns)
    3. Match by removing JOIN$ prefix
    """
    # First try exact match
    if name in mappings:
        return mappings[name]
    
    # For patterns like "JOIN$MATNR$MATNR", try matching segments
    # Split by $ and try each segment in reverse order (most specific first)
    if "$" in name:
        segments = [s for s in name.split("$") if s]
        # Try full segments in reverse order
        for i in range(len(segments), 0, -1):
            variant = "$".join(segments[:i])
            if variant in mappings:
                return mappings[variant]
        # Try individual segments in reverse order
        for segment in reversed(segments):
            if segment in mappings:
                return mappings[segment]
    
    # Try removing JOIN$ prefix
    if name.startswith("JOIN$"):
        collapsed = name.replace("JOIN$", "", 1)  # Only replace first occurrence
        if collapsed in mappings:
            return mappings[collapsed]
        # Also try removing all JOIN$ prefixes
        fully_collapsed = name.replace("JOIN$", "")
        if fully_collapsed in mappings:
            return mappings[fully_collapsed]
    
    return None


def _mapping_to_join_expression(mapping: AttributeMapping) -> Expression:
    """Convert an AttributeMapping to an Expression for use in join conditions.
    
    Note: We use the raw column name (mapping.expression.value) without the source_node
    prefix, because the renderer will use the table alias parameter to qualify the column.
    """
    value = mapping.expression.value
    # Don't include source_node here - the renderer will use the table alias
    return Expression(ExpressionType.COLUMN, value, mapping.expression.data_type)


def _parse_view_attribute_ids(node_el: etree._Element) -> List[str]:
    """Parse view attribute IDs, excluding hidden attributes."""
    ids: List[str] = []
    for attr_el in _find_children(node_el, "viewAttributes", "viewAttribute"):
        attr_id = attr_el.get("id")
        is_hidden = attr_el.get("hidden", "false").lower() == "true"
        # Only include non-hidden attributes
        if attr_id and not is_hidden:
            ids.append(attr_id)
    return ids


def _parse_calculated_view_attributes(node_el: etree._Element) -> Dict[str, CalculatedAttribute]:
    calculated: Dict[str, CalculatedAttribute] = {}
    for calc_el in _find_children(node_el, "calculatedViewAttributes", "calculatedViewAttribute"):
        attr_id = calc_el.get("id")
        if not attr_id:
            continue
        data_type = _parse_type_spec(calc_el.get("datatype"), calc_el.get("length"), calc_el.get("scale"))
        formula_el = _find_child(calc_el, "formula")
        formula = (formula_el.text or "").strip() if formula_el is not None else ""
        expression = Expression(ExpressionType.RAW, formula, data_type=data_type)
        calculated[attr_id] = CalculatedAttribute(
            name=attr_id,
            expression=expression,
            data_type=data_type,
            description=_get_default_description(calc_el),
            hidden=calc_el.get("hidden", "false").lower() == "true",
            properties={
                "expressionLanguage": calc_el.get("expressionLanguage", ""),
            },
        )
    return calculated


def _parse_logical_model(ctx: ParseContext, root: etree._Element) -> None:
    logical_el = _find_child(root, "logicalModel")
    if logical_el is None:
        return

    model_id = logical_el.get("id") or ""
    logical = LogicalModel(model_id=model_id, base_node_id=logical_el.get("id"))

    for attr_el in _find_children(logical_el, "attributes", "attribute"):
        parsed_attr = _parse_logical_attribute(attr_el)
        if parsed_attr is not None:
            logical.attributes.append(parsed_attr)

    for calc_attr_el in _find_children(logical_el, "calculatedAttributes", "calculatedAttribute"):
        parsed_calc = _parse_logical_calculated_attribute(calc_attr_el)
        if parsed_calc is not None:
            logical.calculated_attributes.append(parsed_calc)

    for measure_el in _find_children(logical_el, "baseMeasures", "measure"):
        parsed_measure = _parse_logical_measure(measure_el, calculated=False)
        if parsed_measure is not None:
            logical.measures.append(parsed_measure)

    for measure_el in _find_children(logical_el, "calculatedMeasures", "calculatedMeasure"):
        parsed_measure = _parse_logical_measure(measure_el, calculated=True)
        if parsed_measure is not None:
            logical.measures.append(parsed_measure)

    ctx.scenario.logical_model = logical


def _parse_logical_attribute(attr_el: etree._Element) -> Optional[LogicalAttribute]:
    attr_id = attr_el.get("id")
    if not attr_id:
        return None
    order = attr_el.get("order")
    key_attr = attr_el.get("key", "false").lower() == "true"
    display_attr = attr_el.get("displayAttribute", "true").lower() == "true"
    hidden_attr = attr_el.get("hidden", "false").lower() == "true"
    description = _get_default_description(attr_el)
    semantic_type = attr_el.get("semanticType")
    local_variable_el = _find_child(attr_el, "localVariable")
    local_variable = local_variable_el.text if local_variable_el is not None else None
    key_mapping_el = _find_child(attr_el, "keyMapping")
    schema_name = key_mapping_el.get("schemaName") if key_mapping_el is not None else None
    column_object = key_mapping_el.get("columnObjectName") if key_mapping_el is not None else None
    column_name = key_mapping_el.get("columnName") if key_mapping_el is not None else None
    return LogicalAttribute(
        name=attr_id,
        column_name=column_name,
        column_object=column_object,
        schema_name=schema_name,
        order=int(order) if order and order.isdigit() else None,
        description=description,
        key=key_attr,
        display=display_attr,
        hidden=hidden_attr,
        semantic_type=semantic_type,
        local_variable=local_variable,
    )


def _parse_logical_calculated_attribute(calc_el: etree._Element) -> Optional[LogicalCalculatedAttribute]:
    attr_id = calc_el.get("id")
    if not attr_id:
        return None
    description = _get_default_description(calc_el)
    order = calc_el.get("order")
    
    # Try keyCalculation/formula first (common in logical model), then expression
    formula_el = _find_child(calc_el, "keyCalculation", "formula")
    if formula_el is None:
        formula_el = _find_child(calc_el, "expression")
    if formula_el is None:
        formula_el = _find_child(calc_el, "formula")
    
    expression_text = (formula_el.text or "").strip() if formula_el is not None else ""
    
    # Get datatype from keyCalculation or from calc_el directly
    key_calc_el = _find_child(calc_el, "keyCalculation")
    if key_calc_el is not None:
        data_type = _parse_type_spec(key_calc_el.get("datatype"), key_calc_el.get("length"), key_calc_el.get("scale"))
    else:
        data_type = _parse_type_spec(calc_el.get("datatype"), calc_el.get("length"), calc_el.get("scale"))
    
    expression = Expression(ExpressionType.RAW, expression_text, data_type=data_type)
    return LogicalCalculatedAttribute(
        name=attr_id,
        expression=expression,
        data_type=data_type,
        order=int(order) if order and order.isdigit() else None,
        description=description,
        hidden=calc_el.get("hidden", "false").lower() == "true",
    )


def _parse_logical_measure(measure_el: etree._Element, *, calculated: bool) -> Optional[LogicalMeasure]:
    measure_id = measure_el.get("id")
    if not measure_id:
        return None
    description = _get_default_description(measure_el)
    aggregation = measure_el.get("aggregationType")
    column_name = measure_el.get("columnName") or measure_el.get("sourceColumn")
    measure_type = measure_el.get("measureType")
    data_type = _parse_type_spec(measure_el.get("datatype"), measure_el.get("length"), measure_el.get("scale"))
    formula = None
    if calculated:
        formula_el = _find_child(measure_el, "expression") or _find_child(measure_el, "calculation")
        if formula_el is not None:
            formula = (formula_el.text or "").strip()

    currency_attribute = measure_el.get("currency")
    fixed_currency = measure_el.get("fixedCurrency")

    conversion_el = _find_child(measure_el, "currencyConversion")
    currency_conversion = _parse_currency_conversion(conversion_el) if conversion_el is not None else None

    return LogicalMeasure(
        name=measure_id,
        aggregation=aggregation,
        column_name=column_name,
        description=description,
        measure_type=measure_type,
        data_type=data_type,
        formula=formula,
        currency_attribute=currency_attribute,
        fixed_currency=fixed_currency,
        currency_conversion=currency_conversion,
    )


def _parse_currency_conversion(conv_el: etree._Element) -> CurrencyConversion:
    def _expr(text: Optional[str]) -> Expression:
        value = (text or "").strip()
        return Expression(ExpressionType.RAW, value)

    source_currency = _expr(conv_el.get("sourceCurrency"))
    target_currency = _expr(conv_el.get("targetCurrency"))
    client = _expr(conv_el.get("client"))
    reference_date = _expr(conv_el.get("referenceDate"))
    rate_type = conv_el.get("rateType", "")
    schema = conv_el.get("schema")
    return CurrencyConversion(
        source_currency=source_currency,
        target_currency=target_currency,
        client=client,
        reference_date=reference_date,
        rate_type=rate_type,
        schema=schema,
    )


def _map_filter_operator(value: Optional[str]) -> str:
    if not value:
        return "="
    normalized = value.upper()
    mapping = {
        "EQ": "=",
        "NE": "<>",
        "GT": ">",
        "GE": ">=",
        "LT": "<",
        "LE": "<=",
        "BETWEEN": "BETWEEN",
        "IN": "IN",
        "LIKE": "LIKE",
    }
    return mapping.get(normalized, normalized)


def _parse_type_spec(datatype: Optional[str], length: Optional[str], scale: Optional[str]) -> Optional[DataTypeSpec]:
    if not datatype:
        return None
    normalized = datatype.upper()
    length_val = _safe_int(length)
    scale_val = _safe_int(scale)

    if normalized in {"VARCHAR", "NVARCHAR", "ALPHANUM", "CHAR"}:
        return DataTypeSpec(SnowflakeType.VARCHAR, length=length_val or 255)
    if normalized in {"DECIMAL", "NUMERIC"}:
        return DataTypeSpec(SnowflakeType.NUMBER, length=length_val or 38, scale=scale_val or 0)
    if normalized in {"INTEGER", "INT", "SMALLINT", "BIGINT"}:
        return DataTypeSpec(SnowflakeType.NUMBER, length=length_val or 38, scale=0)
    if normalized in {"DOUBLE", "FLOAT", "REAL"}:
        return DataTypeSpec(SnowflakeType.NUMBER, length=length_val or 38, scale=scale_val)
    if normalized in {"BOOLEAN"}:
        return DataTypeSpec(SnowflakeType.BOOLEAN)
    if normalized in {"DATE"}:
        return DataTypeSpec(SnowflakeType.DATE)
    if normalized in {"TIMESTAMP", "SECONDDATE", "TIMESTAMP_NTZ"}:
        return DataTypeSpec(SnowflakeType.TIMESTAMP_NTZ)
    # Fallback to string
    return DataTypeSpec(SnowflakeType.VARCHAR, length=length_val or 255)


def _safe_int(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _map_data_source_type(source_type: str) -> DataSourceType:
    normalized = source_type.upper()
    if normalized == "DATA_BASE_TABLE":
        return DataSourceType.TABLE
    if normalized == "CALCULATION_VIEW":
        return DataSourceType.CALCULATION_VIEW
    return DataSourceType.VIEW


def _clean_ref(value: str) -> str:
    """Clean node reference by stripping XML metadata prefixes.

    Examples:
        #/0/Star Join/Join_1 -> Star Join/Join_1
        #//Aggregation_1 -> Aggregation_1
        #/Projection_1 -> Projection_1
        Aggregation_1 -> Aggregation_1
    """
    text = value.strip()
    # Strip #// prefix
    if text.startswith("#//"):
        return text[3:]
    # Strip #/N/ prefix (e.g., #/0/, #/1/, etc.)
    if text.startswith("#/"):
        # Find the second slash and strip up to that point
        second_slash = text.find("/", 2)
        if second_slash > 0:
            return text[second_slash + 1:]
        # If no second slash, just strip #/
        return text[2:]
    # Strip single # prefix
    if text.startswith("#"):
        return text[1:]
    return text


def _map_join_type(value: str) -> JoinType:
    normalized = value.strip().lower()
    mapping = {
        "inner": JoinType.INNER,
        "leftouter": JoinType.LEFT_OUTER,
        "rightouter": JoinType.RIGHT_OUTER,
        "fullouter": JoinType.FULL_OUTER,
    }
    return mapping.get(normalized, JoinType.INNER)


__all__ = ["parse_scenario"]


