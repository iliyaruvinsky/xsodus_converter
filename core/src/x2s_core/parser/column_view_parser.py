"""Parser for legacy SAP HANA ColumnView XML format."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from lxml import etree

from ..domain import (
    AggregationNode,
    AggregationSpec,
    Attribute,
    AttributeMapping,
    CalculatedAttribute,
    DataSource,
    DataSourceType,
    DataTypeSpec,
    Expression,
    ExpressionType,
    JoinCondition,
    JoinNode,
    JoinType,
    LogicalModel,
    Node,
    NodeKind,
    OrderBySpec,
    Predicate,
    PredicateKind,
    RankNode,
    Scenario,
    ScenarioMetadata,
    SnowflakeType,
    UnionNode,
    Variable,
)

_NS = {
    "view": "http://www.sap.com/ndb/ViewModelView.ecore",
    "type": "http://www.sap.com/ndb/DataModelType.ecore",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}


@dataclass(slots=True)
class ElementInfo:
    name: str
    data_type: Optional[DataTypeSpec] = None
    formula: Optional[str] = None
    formula_language: Optional[str] = None
    aggregation_behavior: Optional[str] = None
    description: Optional[str] = None


def parse_column_view(path: Path, root: etree._Element) -> Scenario:
    """Parse a ColumnView XML definition into Scenario IR."""

    scenario_id = root.get("name") or path.stem
    metadata = ScenarioMetadata(
        scenario_id=scenario_id,
        description=_get_label(root),
        default_client=None,
        default_language=None,
    )
    scenario = Scenario(metadata=metadata)

    _parse_parameters(scenario, root)
    _parse_view_nodes(scenario, root)

    default_node = root.get("defaultNode")
    if default_node:
        default_node_id = _clean_ref(default_node)
        scenario.set_logical_model(LogicalModel(model_id=default_node_id, base_node_id=default_node_id))

    return scenario


def _parse_parameters(scenario: Scenario, root: etree._Element) -> None:
    for parameter in root.findall("./view:parameter", namespaces=_NS) + root.findall("./parameter"):
        name = parameter.get("name")
        if not name:
            continue

        description = _get_label(parameter)
        inline_type = parameter.find("./view:inlineType", namespaces=_NS) or parameter.find("./inlineType")
        data_type = inline_type.get("primitiveType") if inline_type is not None else None

        default_value_el = parameter.find("./view:defaultValue", namespaces=_NS) or parameter.find("./defaultValue")
        default_value = None
        if default_value_el is not None and default_value_el.get(f"{{{_NS['xsi']}}}nil", "false").lower() != "true":
            default_value = (default_value_el.text or "").strip() or None

        variable = Variable(
            variable_id=name,
            description=description,
            data_type=data_type,
            mandatory=parameter.get("mandatory", "false").lower() == "true",
            default_value=default_value,
            selection_type="Multiple" if parameter.get("multipleSelections", "false").lower() == "true" else "Single",
        )
        scenario.add_variable(variable)


def _parse_view_nodes(scenario: Scenario, root: etree._Element) -> None:
    for node_el in root.findall("./view:viewNode", namespaces=_NS) + root.findall("./viewNode"):
        node = _parse_view_node(scenario, node_el)
        scenario.add_node(node)


def _parse_view_node(scenario: Scenario, node_el: etree._Element) -> Node:
    node_name = node_el.get("name") or node_el.get("id")
    if not node_name:
        raise ValueError("Encountered view node without identifier")

    xsi_type = node_el.get(f"{{{_NS['xsi']}}}type", "")
    node_type = xsi_type.split(":")[-1] if xsi_type else ""

    elements = _collect_elements(node_el)
    filters = _collect_filters(node_el)
    inputs, mappings = _collect_inputs(scenario, node_el, elements)
    view_attributes = [info.name for info in elements.values()]
    calculated_attributes = {
        name: CalculatedAttribute(
            name=name,
            expression=Expression(ExpressionType.RAW, info.formula or "", data_type=info.data_type, language=info.formula_language),
            data_type=info.data_type,
            description=info.description,
        )
        for name, info in elements.items()
        if info.formula
    }

    output_attributes = {
        name: Attribute(name=name, data_type=info.data_type or DataTypeSpec(SnowflakeType.VARCHAR))
        for name, info in elements.items()
    }

    if node_type.endswith("Projection"):
        return Node(
            node_id=node_name,
            kind=NodeKind.PROJECTION,
            inputs=inputs,
            mappings=mappings,
            filters=filters,
            output_attributes=output_attributes,
            view_attributes=view_attributes,
            calculated_attributes=calculated_attributes,
        )

    if node_type.endswith("Aggregation"):
        group_by, aggregations = _collect_aggregations(elements)
        # Include calculated_attributes from elements with formulas
        return AggregationNode(
            node_id=node_name,
            kind=NodeKind.AGGREGATION,
            inputs=inputs,
            mappings=mappings,
            filters=filters,
            group_by=group_by,
            aggregations=aggregations,
            output_attributes=output_attributes,
            view_attributes=view_attributes,
            calculated_attributes=calculated_attributes,  # Already built from elements with formulas
        )

    if node_type.endswith("Union"):
        return UnionNode(
            node_id=node_name,
            kind=NodeKind.UNION,
            inputs=inputs,
            mappings=mappings,
            filters=filters,
            output_attributes=output_attributes,
            view_attributes=view_attributes,
            calculated_attributes=calculated_attributes,
            union_all=True,
        )

    if node_type.endswith("JoinNode"):
        # Parse JOIN-specific attributes
        join_type = _parse_join_type(node_el)
        join_conditions = _parse_join_conditions(node_el, inputs)
        
        return JoinNode(
            node_id=node_name,
            kind=NodeKind.JOIN,
            inputs=inputs,
            mappings=mappings,
            filters=filters,
            join_type=join_type,
            conditions=join_conditions,
            properties={},
            output_attributes=output_attributes,
            view_attributes=view_attributes,
            calculated_attributes=calculated_attributes,
        )

    if node_type.endswith("Rank"):
        partition_cols, order_specs, rank_column, threshold = _parse_rank_window(node_el)
        return RankNode(
            node_id=node_name,
            kind=NodeKind.RANK,
            inputs=inputs,
            mappings=mappings,
            filters=filters,
            output_attributes=output_attributes,
            view_attributes=view_attributes,
            calculated_attributes=calculated_attributes,
            partition_by=partition_cols,
            order_by=order_specs,
            rank_column=rank_column,
            threshold=threshold,
        )

    return Node(
        node_id=node_name,
        kind=NodeKind.CALCULATION,
        inputs=inputs,
        mappings=mappings,
        filters=filters,
        output_attributes=output_attributes,
        view_attributes=view_attributes,
        calculated_attributes=calculated_attributes,
    )


def _collect_elements(node_el: etree._Element) -> Dict[str, ElementInfo]:
    elements: Dict[str, ElementInfo] = {}

    for element_el in node_el.findall("./view:element", namespaces=_NS) + node_el.findall("./element"):
        name = element_el.get("name")
        if not name:
            continue

        inline_type = element_el.find("./view:inlineType", namespaces=_NS) or element_el.find("./inlineType")
        data_type = _parse_type_spec(
            inline_type.get("primitiveType") if inline_type is not None else None,
            inline_type.get("length") if inline_type is not None else None,
            inline_type.get("scale") if inline_type is not None else None,
            inline_type.get("precision") if inline_type is not None else None,
        )

        formula_el = element_el.find("./view:calculationDefinition", namespaces=_NS) or element_el.find("./calculationDefinition")
        formula = None
        formula_language = None
        if formula_el is not None:
            language = formula_el.get("language")
            formula_text = formula_el.find("./view:formula", namespaces=_NS) or formula_el.find("./formula")
            formula = (formula_text.text or "").strip() if formula_text is not None else ""
            formula_language = language

        elements[name] = ElementInfo(
            name=name,
            data_type=data_type,
            formula=formula,
            formula_language=formula_language,
            aggregation_behavior=element_el.get("aggregationBehavior"),
            description=_get_label(element_el),
        )

    return elements


def _collect_filters(node_el: etree._Element) -> List[Predicate]:
    filters: List[Predicate] = []
    filter_el = node_el.find("./view:filterExpression", namespaces=_NS) or node_el.find("./filterExpression")
    if filter_el is not None:
        formula_el = filter_el.find("./view:formula", namespaces=_NS) or filter_el.find("./formula")
        if formula_el is not None:
            formula = (formula_el.text or "").strip()
            if formula:
                language = filter_el.get("language")
                filters.append(
                    Predicate(
                        kind=PredicateKind.RAW,
                        left=Expression(ExpressionType.RAW, formula, language=language),
                    )
                )
    return filters


def _collect_inputs(
    scenario: Scenario,
    node_el: etree._Element,
    elements: Dict[str, ElementInfo],
) -> Tuple[List[str], List[AttributeMapping]]:
    inputs: List[str] = []
    mappings: List[AttributeMapping] = []

    for input_el in node_el.findall("./view:input", namespaces=_NS) + node_el.findall("./input"):
        input_id = _resolve_input_source(scenario, input_el)
        if input_id:
            inputs.append(input_id)
        for mapping_el in input_el.findall("./view:mapping", namespaces=_NS) + input_el.findall("./mapping"):
            mapping = _create_mapping(mapping_el, elements, input_id)
            if mapping:
                mappings.append(mapping)

    return inputs, mappings


def _resolve_input_source(scenario: Scenario, input_el: etree._Element) -> Optional[str]:
    node_ref = input_el.get("node")
    if node_ref:
        return _clean_ref(node_ref)

    view_node_ref = input_el.find("./view:viewNode", namespaces=_NS) or input_el.find("./viewNode")
    if view_node_ref is not None and view_node_ref.text:
        return _clean_ref(view_node_ref.text)

    entity_el = input_el.find("./view:entity", namespaces=_NS) or input_el.find("./entity")
    if entity_el is not None and entity_el.text:
        schema_name, object_name = _parse_entity(entity_el.text)
        source_id = input_el.get("alias") or _normalize_identifier(object_name)
        if source_id not in scenario.data_sources:
            scenario.data_sources[source_id] = DataSource(
                source_id=source_id,
                source_type=DataSourceType.TABLE,
                schema_name=schema_name or "",
                object_name=object_name or "",
            )
        return source_id

    return None


def _create_mapping(
    mapping_el: etree._Element,
    elements: Dict[str, ElementInfo],
    source_node: Optional[str],
) -> Optional[AttributeMapping]:
    target = mapping_el.get("targetName") or mapping_el.get("target")
    if not target:
        return None

    data_spec = elements.get(target).data_type if target in elements else None
    xsi_type = mapping_el.get(f"{{{_NS['xsi']}}}type", "")
    mapping_type = xsi_type.split(":")[-1] if xsi_type else ""

    if mapping_type.endswith("ElementMapping"):
        source_name = mapping_el.get("sourceName") or mapping_el.get("source")
        if not source_name:
            return None
        expression = Expression(ExpressionType.COLUMN, source_name, data_spec)
    elif mapping_type.endswith("ConstantElementMapping"):
        if mapping_el.get("null", "false").lower() == "true":
            expression = Expression(ExpressionType.RAW, "NULL", data_type=data_spec)
        else:
            value = mapping_el.get("value", "")
            expression = Expression(ExpressionType.LITERAL, value, data_spec)
    else:
        return None

    return AttributeMapping(
        target_name=target,
        expression=expression,
        data_type=data_spec,
        source_node=source_node,
    )


def _parse_join_type(node_el: etree._Element) -> JoinType:
    """Parse join type from ColumnView JOIN node."""
    join_el = node_el.find("./view:join", namespaces=_NS) or node_el.find("./join")
    if join_el is None:
        return JoinType.INNER
    
    join_type_str = join_el.get("joinType", "inner").lower()
    
    type_map = {
        "inner": JoinType.INNER,
        "leftouter": JoinType.LEFT_OUTER,
        "left_outer": JoinType.LEFT_OUTER,
        "rightouter": JoinType.RIGHT_OUTER,
        "right_outer": JoinType.RIGHT_OUTER,
        "fullouter": JoinType.FULL_OUTER,
        "full_outer": JoinType.FULL_OUTER,
    }
    
    return type_map.get(join_type_str, JoinType.INNER)


def _parse_join_conditions(node_el: etree._Element, inputs: List[str]) -> List[JoinCondition]:
    """Parse join conditions from ColumnView JOIN node."""
    from ..domain import JoinCondition
    
    join_el = node_el.find("./view:join", namespaces=_NS) or node_el.find("./join")
    if join_el is None:
        return []
    
    # Get left and right column names
    left_elements = []
    right_elements = []
    
    for left_el in join_el.findall("./view:leftElementName", namespaces=_NS) + join_el.findall("./leftElementName"):
        if left_el.text:
            left_elements.append(left_el.text)
    
    for right_el in join_el.findall("./view:rightElementName", namespaces=_NS) + join_el.findall("./rightElementName"):
        if right_el.text:
            right_elements.append(right_el.text)
    
    # Create join conditions (pair left and right elements)
    conditions = []
    for left_col, right_col in zip(left_elements, right_elements):
        left_expr = Expression(ExpressionType.COLUMN, left_col)
        right_expr = Expression(ExpressionType.COLUMN, right_col)
        conditions.append(JoinCondition(
            left=left_expr,
            right=right_expr,
            operator="="
        ))
    
    return conditions


def _extract_column_name(ref: Optional[str]) -> Optional[str]:
    if not ref:
        return None
    cleaned = _clean_ref(ref)
    return cleaned.split("/")[-1] if "/" in cleaned else cleaned


def _parse_rank_window(node_el: etree._Element) -> Tuple[List[str], List[OrderBySpec], str, Optional[int]]:
    window_el = node_el.find("./view:windowFunction", namespaces=_NS) or node_el.find("./windowFunction")
    partition_cols: List[str] = []
    order_specs: List[OrderBySpec] = []
    rank_column = "RANK_COLUMN"
    threshold: Optional[int] = None

    if window_el is None:
        return partition_cols, order_specs, rank_column, threshold

    for partition_el in window_el.findall("./view:partitionElement", namespaces=_NS) + window_el.findall("./partitionElement"):
        col_name = _extract_column_name(partition_el.text)
        if col_name:
            partition_cols.append(col_name)

    for order_el in window_el.findall("./view:order", namespaces=_NS) + window_el.findall("./order"):
        by_element = order_el.get("byElement")
        col_name = _extract_column_name(by_element)
        if col_name:
            direction = order_el.get("direction", "ASC").upper()
            order_specs.append(OrderBySpec(column=col_name, direction=direction))

    rank_el = window_el.find("./view:rankElement", namespaces=_NS) or window_el.find("./rankElement")
    if rank_el is not None and rank_el.text:
        rank_col_name = _extract_column_name(rank_el.text)
        if rank_col_name:
            rank_column = rank_col_name

    threshold_el = window_el.find("./view:rankThreshold", namespaces=_NS) or window_el.find("./rankThreshold")
    if threshold_el is not None:
        constant_el = threshold_el.find("./view:constantValue", namespaces=_NS) or threshold_el.find("./constantValue")
        if constant_el is not None and constant_el.text:
            try:
                threshold = int(constant_el.text.strip())
            except ValueError:
                threshold = None

    return partition_cols, order_specs, rank_column, threshold


def _collect_aggregations(elements: Dict[str, ElementInfo]) -> Tuple[List[str], List[AggregationSpec]]:
    group_by: List[str] = []
    aggregations: List[AggregationSpec] = []

    for name, info in elements.items():
        behavior = (info.aggregation_behavior or "").upper()
        if behavior and behavior != "NONE":
            aggregations.append(
                AggregationSpec(
                    target_name=name,
                    function=behavior,
                    expression=Expression(ExpressionType.COLUMN, name, info.data_type),
                    data_type=info.data_type,
                )
            )
        else:
            group_by.append(name)

    return group_by, aggregations


def _parse_entity(value: str) -> Tuple[Optional[str], Optional[str]]:
    text = value.strip()
    # Strip XML metadata prefixes: #// or #/0/ or #/N/
    if text.startswith("#//"):
        text = text[3:]
    elif text.startswith("#/"):
        # Strip #/0/ or #/N/ prefix (external reference notation)
        slash_pos = text.find("/", 2)
        if slash_pos > 0:
            text = text[slash_pos + 1:]

    schema_name: Optional[str] = None
    object_name: Optional[str] = None

    # BUG-025 PARSER FIX: Handle CV references with :: separator
    # Example: "Macabi_BI.Eligibility::CV_MD_EYPOSPER"
    # Package path before :: → schema_name (for CV reference context)
    # CV name after :: → object_name
    if "::" in text and not text.startswith('"'):
        parts = text.split("::", 1)
        if len(parts) == 2:
            schema_name = parts[0]  # e.g., "Macabi_BI.Eligibility"
            object_name = parts[1]  # e.g., "CV_MD_EYPOSPER"
        else:
            object_name = text
    elif text.startswith('"'):
        # Pattern: "SCHEMA".OBJECT or "SCHEMA"./BIC/OBJ
        end_quote = text.find('"', 1)
        schema_name = text[1:end_quote]
        remainder = text[end_quote + 2 :] if len(text) > end_quote + 1 else ""
        object_name = remainder.strip('"')
    else:
        parts = text.split(".", 1)
        if len(parts) == 2:
            schema_name, object_name = parts[0], parts[1]
        elif parts:
            object_name = parts[0]

    if object_name:
        object_name = object_name.replace('"', "")

    return schema_name, object_name


def _normalize_identifier(value: Optional[str]) -> str:
    if not value:
        return "SOURCE"
    sanitized = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in value)
    if sanitized and sanitized[0].isdigit():
        sanitized = f"DS_{sanitized}"
    return sanitized or "SOURCE"


def _clean_ref(value: str) -> str:
    text = value.strip()
    if text.startswith("#//"):
        return text[3:]
    if text.startswith("#/"):
        return text[2:]
    if text.startswith("#"):
        return text[1:]
    return text


def _get_label(element: etree._Element) -> Optional[str]:
    end_user = element.find("./view:endUserTexts", namespaces=_NS) or element.find("./endUserTexts")
    if end_user is not None:
        label = end_user.get("label")
        if label:
            return label
    return None


def _parse_type_spec(
    datatype: Optional[str],
    length: Optional[str],
    scale: Optional[str],
    precision: Optional[str],
) -> Optional[DataTypeSpec]:
    if not datatype:
        return None

    normalized = datatype.upper()
    length_val = _safe_int(length) or _safe_int(precision)
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

    return DataTypeSpec(SnowflakeType.VARCHAR, length=length_val or 255)


def _safe_int(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


__all__ = ["parse_column_view"]


