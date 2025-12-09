"""Domain models describing the intermediate representation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence

from .types import DataTypeSpec, SnowflakeType


class DataSourceType(str, Enum):
    TABLE = "TABLE"
    VIEW = "VIEW"
    CALCULATION_VIEW = "CALCULATION_VIEW"
    UNKNOWN = "UNKNOWN"


@dataclass(slots=True)
class Attribute:
    name: str
    data_type: DataTypeSpec
    description: Optional[str] = None


class ExpressionType(str, Enum):
    COLUMN = "COLUMN"
    LITERAL = "LITERAL"
    FUNCTION = "FUNCTION"
    CASE = "CASE"
    RAW = "RAW"


@dataclass(slots=True)
class Expression:
    expression_type: ExpressionType
    value: str
    arguments: Sequence["Expression"] | None = None
    data_type: Optional[DataTypeSpec] = None
    language: Optional[str] = None


@dataclass(slots=True)
class AttributeMapping:
    target_name: str
    expression: Expression
    data_type: Optional[DataTypeSpec] = None
    source_node: Optional[str] = None


@dataclass(slots=True)
class CalculatedAttribute:
    name: str
    expression: Expression
    data_type: Optional[DataTypeSpec] = None
    description: Optional[str] = None
    hidden: bool = False
    properties: Dict[str, str] = field(default_factory=dict)


class PredicateKind(str, Enum):
    COMPARISON = "COMPARISON"
    BETWEEN = "BETWEEN"
    IN_LIST = "IN_LIST"
    IS_NULL = "IS_NULL"
    RAW = "RAW"


@dataclass(slots=True)
class Predicate:
    kind: PredicateKind
    left: Expression
    operator: Optional[str] = None
    right: Optional[Expression] = None
    including: bool = True


class NodeKind(str, Enum):
    PROJECTION = "PROJECTION"
    JOIN = "JOIN"
    AGGREGATION = "AGGREGATION"
    CALCULATION = "CALCULATION"
    UNION = "UNION"
    RANK = "RANK"


@dataclass(slots=True)
class Node:
    node_id: str
    kind: NodeKind
    inputs: List[str] = field(default_factory=list)
    mappings: List[AttributeMapping] = field(default_factory=list)
    filters: List[Predicate] = field(default_factory=list)
    properties: Dict[str, str] = field(default_factory=dict)
    output_attributes: Dict[str, Attribute] = field(default_factory=dict)
    view_attributes: List[str] = field(default_factory=list)
    calculated_attributes: Dict[str, CalculatedAttribute] = field(default_factory=dict)


class JoinType(str, Enum):
    INNER = "INNER"
    LEFT_OUTER = "LEFT OUTER"
    RIGHT_OUTER = "RIGHT OUTER"
    FULL_OUTER = "FULL OUTER"


@dataclass(slots=True)
class JoinCondition:
    left: Expression
    right: Expression
    operator: str = "="


@dataclass(slots=True)
class JoinNode(Node):
    join_type: JoinType = JoinType.INNER
    conditions: List[JoinCondition] = field(default_factory=list)


@dataclass(slots=True)
class AggregationSpec:
    target_name: str
    function: str
    expression: Expression
    data_type: Optional[DataTypeSpec] = None


@dataclass(slots=True)
class AggregationNode(Node):
    group_by: List[str] = field(default_factory=list)
    aggregations: List[AggregationSpec] = field(default_factory=list)


@dataclass(slots=True)
class UnionNode(Node):
    """Union node with multiple inputs that are combined with UNION ALL."""

    union_all: bool = True


@dataclass(slots=True)
class OrderBySpec:
    column: str
    direction: str = "ASC"


@dataclass(slots=True)
class RankNode(Node):
    partition_by: List[str] = field(default_factory=list)
    order_by: List[OrderBySpec] = field(default_factory=list)
    rank_column: str = "RANK_COLUMN"
    threshold: Optional[int] = None


@dataclass(slots=True)
class CurrencyConversion:
    source_currency: Expression
    target_currency: Expression
    client: Expression
    reference_date: Expression
    rate_type: str
    schema: Optional[str] = None


@dataclass(slots=True)
class Measure:
    name: str
    expression: Expression
    aggregation: str
    data_type: DataTypeSpec
    currency_conversion: Optional[CurrencyConversion] = None


@dataclass(slots=True)
class Variable:
    variable_id: str
    description: Optional[str] = None
    data_type: Optional[str] = None
    mandatory: bool = False
    default_value: Optional[str] = None
    selection_type: Optional[str] = None
    multi_line: Optional[bool] = None
    attribute_name: Optional[str] = None


@dataclass(slots=True)
class LogicalAttribute:
    name: str
    column_name: Optional[str] = None
    column_object: Optional[str] = None
    schema_name: Optional[str] = None
    order: Optional[int] = None
    description: Optional[str] = None
    key: bool = False
    display: bool = True
    hidden: bool = False
    semantic_type: Optional[str] = None
    local_variable: Optional[str] = None


@dataclass(slots=True)
class LogicalCalculatedAttribute:
    name: str
    expression: Expression
    data_type: Optional[DataTypeSpec] = None
    order: Optional[int] = None
    description: Optional[str] = None
    hidden: bool = False


@dataclass(slots=True)
class LogicalMeasure:
    name: str
    aggregation: Optional[str] = None
    column_name: Optional[str] = None
    description: Optional[str] = None
    measure_type: Optional[str] = None
    data_type: Optional[DataTypeSpec] = None
    formula: Optional[str] = None
    currency_attribute: Optional[str] = None
    fixed_currency: Optional[str] = None
    currency_conversion: Optional[CurrencyConversion] = None


@dataclass(slots=True)
class LogicalModel:
    model_id: str
    attributes: List[LogicalAttribute] = field(default_factory=list)
    calculated_attributes: List[LogicalCalculatedAttribute] = field(default_factory=list)
    measures: List[LogicalMeasure] = field(default_factory=list)
    base_node_id: Optional[str] = None


@dataclass(slots=True)
class DataSource:
    source_id: str
    source_type: DataSourceType
    schema_name: str
    object_name: str
    columns: Dict[str, Attribute] = field(default_factory=dict)
    resource_uri: Optional[str] = None


@dataclass(slots=True)
class ScenarioMetadata:
    scenario_id: str
    description: Optional[str] = None
    default_client: Optional[str] = None
    default_language: Optional[str] = None


@dataclass(slots=True)
class Scenario:
    metadata: ScenarioMetadata
    data_sources: Dict[str, DataSource] = field(default_factory=dict)
    nodes: Dict[str, Node] = field(default_factory=dict)
    measures: List[Measure] = field(default_factory=list)
    variables: List[Variable] = field(default_factory=list)
    logical_model: Optional[LogicalModel] = None

    def add_node(self, node: Node) -> None:
        self.nodes[node.node_id] = node

    def add_variable(self, variable: Variable) -> None:
        self.variables.append(variable)

    def set_logical_model(self, logical_model: LogicalModel) -> None:
        self.logical_model = logical_model


__all__ = [
    "Attribute",
    "AggregationNode",
    "AggregationSpec",
    "AttributeMapping",
    "CalculatedAttribute",
    "CurrencyConversion",
    "DataSource",
    "DataSourceType",
    "LogicalAttribute",
    "LogicalCalculatedAttribute",
    "LogicalMeasure",
    "LogicalModel",
    "Expression",
    "ExpressionType",
    "JoinCondition",
    "JoinNode",
    "JoinType",
    "Measure",
    "Node",
    "NodeKind",
    "Predicate",
    "PredicateKind",
    "Scenario",
    "ScenarioMetadata",
    "SnowflakeType",
    "DataTypeSpec",
    "UnionNode",
    "OrderBySpec",
    "RankNode",
    "Variable",
]

