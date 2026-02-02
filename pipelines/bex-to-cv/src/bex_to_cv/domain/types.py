"""BEx domain types and enumerations."""

from enum import Enum


class BExElementType(str, Enum):
    """Type of BEx element from G_T_ELTDIR."""

    VAR = "VAR"       # Variable
    SEL = "SEL"       # Selection (dimension/characteristic)
    STR = "STR"       # Structure
    CKF = "CKF"       # Calculated Key Figure
    RKF = "RKF"       # Restricted Key Figure
    KYF = "KYF"       # Key Figure (measure)
    FML = "FML"       # Formula
    AXS = "AXS"       # Axis
    CHA = "CHA"       # Characteristic
    HIE = "HIE"       # Hierarchy
    UNKNOWN = "UNKNOWN"


class SelectionType(str, Enum):
    """Selection type for variables (VPARSEL in G_T_GLOBV)."""

    SINGLE = "S"      # Single value
    MULTIPLE = "M"    # Multiple values / range
    INTERVAL = "I"    # Interval selection
    COMPLEX = "C"     # Complex selection


class RangeOperator(str, Enum):
    """Range operator for filter conditions (OPT in G_T_RANGE)."""

    EQ = "EQ"         # Equal
    NE = "NE"         # Not equal
    LT = "LT"         # Less than
    LE = "LE"         # Less than or equal
    GT = "GT"         # Greater than
    GE = "GE"         # Greater than or equal
    BT = "BT"         # Between
    NB = "NB"         # Not between
    CP = "CP"         # Contains pattern
    NP = "NP"         # Not contains pattern


class RangeSign(str, Enum):
    """Range sign for include/exclude (SIGN in G_T_RANGE)."""

    INCLUDE = "I"
    EXCLUDE = "E"


class AggregationType(str, Enum):
    """Aggregation type for key figures."""

    SUM = "SUM"
    AVG = "AVG"
    MIN = "MIN"
    MAX = "MAX"
    COUNT = "CNT"
    FIRST = "FIR"
    LAST = "LAS"
    NONE = "NON"


class DataType(str, Enum):
    """Data types for InfoObjects and key figures."""

    CHAR = "CHAR"           # Character
    NUMC = "NUMC"           # Numeric character
    DATS = "DATS"           # Date (YYYYMMDD)
    TIMS = "TIMS"           # Time (HHMMSS)
    DEC = "DEC"             # Packed number (decimal)
    CURR = "CURR"           # Currency field
    QUAN = "QUAN"           # Quantity field
    UNIT = "UNIT"           # Unit of measure
    CUKY = "CUKY"           # Currency key
    INT1 = "INT1"           # 1-byte integer
    INT2 = "INT2"           # 2-byte integer
    INT4 = "INT4"           # 4-byte integer
    FLTP = "FLTP"           # Floating point
    STRING = "STRING"       # String
    UNKNOWN = "UNKNOWN"


class ReadMode(str, Enum):
    """Query read mode from G_S_RKB1D."""

    A = "A"  # Query result set read directly from InfoProvider (H = fast)
    H = "H"  # Read aggregates from OLAP engine (optimized)
    X = "X"  # Query result set read via InfoProvider cache


class QueryType(str, Enum):
    """Type of BEx query."""

    STANDARD = "STANDARD"
    REUSABLE = "REUSABLE"
    INFOPROVIDER = "INFOPROVIDER"
