import uuid
from dataclasses import dataclass

from pydantic import BaseModel, Field, RootModel
from datetime import datetime
from typing import Optional, List, Dict, Any, Union

from app.services.orca_max.helpers.enums import PointType, OrderStatus, FuturesContracts, OrderSides, TeamWay


class BrokerResponseSchema(BaseModel):
    s: str
    d: Union[List, Dict] = Field(default_factory=list)
    errmsg: Optional[str] = None


# Pydantic Models for API Responses
class OrderDuration(BaseModel):
    """Order duration model."""
    type: str



class AccountState(BaseModel):
    """Account state model."""

    balance: float
    unrealizedPl: float
    equity: float
    amData: List[List[List[str]]]


class AccountsState(RootModel[Dict[str, AccountState]]):
    pass


class PositionsResponse(BaseModel):
    """Positions API response model."""

    s: str
    d: List[Dict[str, Any]] = Field(default_factory=list)
    errmsg: Optional[str] = None


class Positions(BaseModel):
    id: str
    instrument: FuturesContracts
    qty: int
    side: OrderSides
    avgPrice: float
    unrealizedPl: float


@dataclass
class ExitStrategy:
    tp: float  # Take Profit
    sl: float  # Stop Loss


@dataclass
class ABCPoints:
    a_point: float
    b_point: float
    c_point: float
    order_point: float
    tp: float
    sl: float
    point_type: PointType
    timestamp: datetime


@dataclass
class AccountConfig:
    tv_id: str  # TradingView account ID
    ta_id: str  # Tradovate account ID (for display/logging)

    def __str__(self):
        return f"TV:{self.tv_id} TA:{self.ta_id}"



@dataclass
class Order:
    instrument: str
    position: str
    order_type: str
    price: float
    quantity: int
    stop_loss: float
    take_profit: float
    timestamp: datetime
    order_dict_all: dict
    id_orca: str = None
    id: str = None
    account_config: AccountConfig= None
    status: OrderStatus = OrderStatus.INACTIVE
    way: TeamWay = None

    def __post_init__(self):
        if not self.id_orca:
            self.id_orca = str(uuid.uuid4())

