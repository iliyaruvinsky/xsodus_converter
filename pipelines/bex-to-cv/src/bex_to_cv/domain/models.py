"""BEx domain models for representing parsed query structure."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .types import (
    AggregationType,
    BExElementType,
    DataType,
    QueryType,
    RangeOperator,
    RangeSign,
    ReadMode,
    SelectionType,
)


@dataclass
class BExRange:
    """Represents a filter range condition from G_T_RANGE.

    Example XML:
        <item>
            <SIGN>I</SIGN>
            <OPT>EQ</OPT>
            <LOW>1000</LOW>
            <HIGH></HIGH>
        </item>
    """

    sign: RangeSign = RangeSign.INCLUDE
    operator: RangeOperator = RangeOperator.EQ
    low: str = ""
    high: str = ""

    def to_sql_condition(self, column_name: str) -> str:
        """Generate SQL condition for this range."""
        if self.operator == RangeOperator.EQ:
            condition = f'"{column_name}" = \'{self.low}\''
        elif self.operator == RangeOperator.NE:
            condition = f'"{column_name}" != \'{self.low}\''
        elif self.operator == RangeOperator.LT:
            condition = f'"{column_name}" < \'{self.low}\''
        elif self.operator == RangeOperator.LE:
            condition = f'"{column_name}" <= \'{self.low}\''
        elif self.operator == RangeOperator.GT:
            condition = f'"{column_name}" > \'{self.low}\''
        elif self.operator == RangeOperator.GE:
            condition = f'"{column_name}" >= \'{self.low}\''
        elif self.operator == RangeOperator.BT:
            condition = f'"{column_name}" BETWEEN \'{self.low}\' AND \'{self.high}\''
        elif self.operator == RangeOperator.NB:
            condition = f'NOT "{column_name}" BETWEEN \'{self.low}\' AND \'{self.high}\''
        elif self.operator == RangeOperator.CP:
            # Convert SAP pattern to SQL LIKE pattern
            pattern = self.low.replace("*", "%").replace("+", "_")
            condition = f'"{column_name}" LIKE \'{pattern}\''
        elif self.operator == RangeOperator.NP:
            pattern = self.low.replace("*", "%").replace("+", "_")
            condition = f'"{column_name}" NOT LIKE \'{pattern}\''
        else:
            condition = f'"{column_name}" = \'{self.low}\''

        if self.sign == RangeSign.EXCLUDE:
            condition = f"NOT ({condition})"

        return condition


@dataclass
class BExVariable:
    """Represents a BEx variable from G_T_GLOBV.

    Example XML:
        <item>
            <VNAM>VAR_PLANT</VNAM>
            <IOBJNM>0PLANT</IOBJNM>
            <VPARSEL>M</VPARSEL>
            <VARINPUT>X</VARINPUT>
            <DEFAULTV></DEFAULTV>
            <OPTIONFL>X</OPTIONFL>
        </item>
    """

    variable_name: str  # VNAM
    infoobject: str  # IOBJNM
    selection_type: SelectionType = SelectionType.MULTIPLE  # VPARSEL
    is_input: bool = True  # VARINPUT = 'X'
    is_mandatory: bool = True  # OPTIONFL != 'X' means mandatory
    default_value: str = ""  # DEFAULTV
    description: str = ""  # Description from texts

    def to_input_parameter_name(self) -> str:
        """Generate CV input parameter name."""
        # Convert VAR_PLANT -> IP_PLANT
        if self.variable_name.startswith("VAR_"):
            return "IP_" + self.variable_name[4:]
        return "IP_" + self.variable_name


@dataclass
class BExSelection:
    """Represents a selection (dimension) from G_T_SELECT.

    Example XML:
        <item>
            <SOTP>2</SOTP>
            <ELTUID>00O2TN3NK6BZ1GDYJ7S03R2FN</ELTUID>
            <IOBJNM>0PLANT</IOBJNM>
            <CHANM>0PLANT</CHANM>
            <AXSNO>000</AXSNO>
        </item>
    """

    element_uid: str  # ELTUID
    infoobject: str  # IOBJNM
    characteristic: str  # CHANM
    selection_type: int = 2  # SOTP: 1=Filter, 2=Characteristic
    axis_number: int = 0  # AXSNO
    description: str = ""

    @property
    def is_filter(self) -> bool:
        """Check if this selection is a filter (not displayed)."""
        return self.selection_type == 1


@dataclass
class BExKeyFigure:
    """Represents a key figure (measure) from G_T_ELTDIR.

    Key figures in BEx represent measurable values like quantity, amount, etc.
    They are identified by looking at the InfoObject type.
    """

    element_uid: str  # ELTUID
    infoobject: str  # IOBJNM (e.g., 0QUANTITY)
    name: str  # Technical name
    aggregation: AggregationType = AggregationType.SUM
    data_type: DataType = DataType.DEC
    length: int = 17
    decimals: int = 3
    description: str = ""
    unit_infoobject: Optional[str] = None  # Unit InfoObject (e.g., 0UNIT)


@dataclass
class BExElement:
    """Represents an element from G_T_ELTDIR (element directory).

    Example XML:
        <item>
            <ELTUID>00O2TN3NK6BZ1GCXKQ3RXQKQY</ELTUID>
            <DEFTP>VAR</DEFTP>
            <COMPID>ZSAPLOM_REP_XS</COMPID>
            <IOBJNM>0PLANT</IOBJNM>
            <1KYFNM></1KYFNM>
        </item>
    """

    element_uid: str  # ELTUID
    element_type: BExElementType  # DEFTP
    component_id: str  # COMPID
    infoobject: Optional[str] = None  # IOBJNM
    key_figure_name: Optional[str] = None  # 1KYFNM
    description: str = ""


@dataclass
class BExQueryMetadata:
    """Metadata from G_S_RKB1D section.

    Example XML:
        <G_S_RKB1D>
            <COMPID>ZSAPLOM_REP_XS</COMPID>
            <INFOCUBE>ZSAPLOM</INFOCUBE>
            <READMODE>H</READMODE>
            <APPLNM>ZSAPLOM_REP_XS</APPLNM>
        </G_S_RKB1D>
    """

    query_id: str  # COMPID
    infocube: str  # INFOCUBE
    read_mode: ReadMode = ReadMode.H  # READMODE
    application_name: str = ""  # APPLNM
    description: str = ""  # Description from texts
    query_type: QueryType = QueryType.STANDARD


@dataclass
class BExQuery:
    """Root model representing a complete BEx Query.

    This is the main IR (Intermediate Representation) produced by the parser
    and consumed by the CV renderer.
    """

    metadata: BExQueryMetadata
    elements: Dict[str, BExElement] = field(default_factory=dict)  # ELTUID -> element
    variables: List[BExVariable] = field(default_factory=list)
    selections: List[BExSelection] = field(default_factory=list)
    ranges: Dict[str, List[BExRange]] = field(default_factory=dict)  # ELTUID -> ranges
    key_figures: List[BExKeyFigure] = field(default_factory=list)

    # Additional metadata
    source_file: Optional[str] = None
    parse_warnings: List[str] = field(default_factory=list)

    def get_dimensions(self) -> List[BExSelection]:
        """Get all dimension selections (not filters)."""
        return [s for s in self.selections if not s.is_filter]

    def get_filters(self) -> List[BExSelection]:
        """Get all filter selections."""
        return [s for s in self.selections if s.is_filter]

    def get_input_variables(self) -> List[BExVariable]:
        """Get all input variables (user prompts)."""
        return [v for v in self.variables if v.is_input]

    def get_mandatory_variables(self) -> List[BExVariable]:
        """Get all mandatory input variables."""
        return [v for v in self.variables if v.is_input and v.is_mandatory]

    def get_key_figure_infoobjects(self) -> List[str]:
        """Get list of InfoObjects used as key figures."""
        return [kf.infoobject for kf in self.key_figures]

    def get_dimension_infoobjects(self) -> List[str]:
        """Get list of InfoObjects used as dimensions."""
        return list(set(s.infoobject for s in self.selections if not s.is_filter))
