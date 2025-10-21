from enum import Enum


class Contract(Enum):
    NQ = "NQ"
    ES = "ES"
    GC = "GC"
    MNQ = "MNQ"
    MES = "MES"
    MGC = "MGC"



class OrderStatus(Enum):
    Lost = "Lost"
    Filled = "Filled"
    NotTriggered = "NotTriggered"



class TradingPosition(Enum):
    Long = "Long"
    Short = "Short"


class PointType(Enum):
    UP = "UP"
    DOWN = "DOWN"


class TeamWay(Enum):
    Reverse = "Reverse"  # Sarab
    BreakThrough = "BreakThrough"  # Amer
