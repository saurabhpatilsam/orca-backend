import decimal
from datetime import datetime
from typing import Type, List, Dict, Any, Tuple, Callable, Optional

from app.services.orca_max.helpers.enums import OrderSides, PointType, TeamWay, TradingPosition, PointPosition
from app.services.orca_max.helpers.orca_helper import get_trading_position
from app.services.orca_max.orca_protocol import PriceProvider

from app.services.orca_max.helpers.settings import PointsDistance
from app.services.orca_max.schemas import ExitStrategy

from app.utils.logging_setup import logger

LOG = True


class ABCFinder:

    def __init__(
        self,
        price_provider: PriceProvider,
        instrument_name,
        point_type: PointType,
        team_way: TeamWay,
        quantity: int,
        exit_strategy,
        points_distance: PointsDistance,
    ) -> None:

        self.pattern_callbacks: List = []
        self.price_provider = price_provider

        self.instrument_name = instrument_name

        self.point_type = point_type
        self.team_way = team_way
        self.quantity = quantity

        # TODO: make sure to run only one  not both of them
        # self.abc_down if self.point_type == PointType.DOWN else self.abc_up
        if self.point_type == PointType.DOWN:
            logger.info("Running Down points")
        elif self.point_type == PointType.UP:
            logger.info("Running Up points ")
        else:
            raise Exception("Unknown point type {}".format(self.point_type))

        self.abc_processor = ForwardABC(
            points_distance, self.point_type, team_way, exit_strategy
        )

        self.points_distance = points_distance.orders_distance
        self.pattern_callbacks: List[Callable[[Dict[str, Any]], None]] = []

        logger.info(f"ABC Finder initialized for {instrument_name}")
        logger.info(f"ABC Finder initialized with {points_distance}")

    def add_pattern_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Register a callback to be called when ABC pattern is found"""
        self.pattern_callbacks.append(callback)

    def get_current_price(self) -> float:
        """Get current price directly from price provider"""
        price = self.price_provider.get_price(self.instrument_name)
        print("price: {}".format(price))
        return price

    def start_processing(self):
        """Start processing prices via subscription (replaces your old run() method)"""
        logger.info(f"Starting ABC processing for {self.instrument_name}")

        # Subscribe to price stream - this replaces your while loop
        self.price_provider.subscribe_price_stream(
            self.instrument_name,
            self.process_price,  # This method will be called for every new price
        )

    def process_price(self, current_price: float) -> Optional[Dict[str, Any]]:
        """Process a single price update (called automatically by price provider)"""

        result, abc_points = self._process(self.abc_processor, current_price)

        if result:
            logger.info(
                f'{self.point_type.value} point found: Order_point {abc_points["order_point"]}'
            )
            abc_points['instrument_name'] = self.instrument_name

            # Notify all registered callbacks
            for callback in self.pattern_callbacks:
                callback(abc_points)

            return abc_points

        return None

    # APPROACH 3: Manual processing with direct price fetching
    # def check_for_patterns(self) -> Optional[Dict[str, Any]]:
    #     """Manually check for patterns by fetching current price"""
    #     current_price = self.get_current_price()
    #     if current_price > 0:
    #         return self.process_price(current_price)
    #     return None

    def _process(self, abc_processor, price):
        """Your existing _process method - unchanged"""
        result, orders_list, order_point, abc_points = abc_processor.find_order_points(
            price, abc_processor.find_abc
        )

        if result:
            return True, abc_points
        return False, {}


class ForwardABC:
    def __init__(
        self,
        points_distance: Type[PointsDistance],
        point_type: PointType,
        team_way: TeamWay,
        exit_strategy: ExitStrategy,
    ) -> None:

        self.points_distance = points_distance

        self.order_point_change: int = points_distance.order_point

        self.a_point = 0.0
        self.b_point = 0.0
        self.c_point = 0.0

        self.a_point_time = None
        self.b_point_time = None
        self.c_point_time = None

        self.a_point_index = 0
        self.b_point_index = 0
        self.c_point_index = 0
        self.point_type = point_type

        self.TP_points = exit_strategy.tp
        self.SL_points = exit_strategy.sl

        if point_type == PointType.DOWN:
            self.find_b_point = self._find_b_point_down
            self.find_c_point = self._find_c_point_down
            self.find_abc = self._find_abc_down
        else:
            self.find_b_point = self._find_b_point_up
            self.find_c_point = self._find_c_point_up
            self.find_abc = self._find_abc_up

        self.trade_position = get_trading_position(self.point_type, team_way)

    def find_b_point(self) -> bool:
        """This is a placeholder method that will be overridden."""
        raise NotImplementedError(
            "This method should be overridden in the constructor."
        )

    def find_c_point(self) -> bool:
        """This is a placeholder method that will be overridden."""
        raise NotImplementedError(
            "This method should be overridden in the constructor."
        )

    def find_abc(self) -> Tuple[bool, decimal.Decimal, Dict[str, Any]]:
        """This is a placeholder method that will be overridden."""
        raise NotImplementedError(
            "This method should be overridden in the constructor."
        )

    def reset_points(self) -> None:
        logger.debug("Resetting Points ABC")
        self.a_point = self.b_point = self.c_point = 0.0
        self.a_point_time = self.b_point_time = self.c_point_time = None

    def get_point_data(self, order_point) -> dict:

        if self.trade_position == TradingPosition.Long:
            tp = order_point + self.TP_points
            sl = order_point - self.SL_points
        else:
            tp = order_point - self.TP_points
            sl = order_point + self.SL_points
        return {
            "type": self.point_type.value,
            # TODO: change it to be side
            "position": OrderSides.BUY.value if self.trade_position == TradingPosition.Long else OrderSides.SELL.value,
            "bc_distance": self.points_distance.bc,
            "a": self.a_point,
            "b": self.b_point,
            "c": self.c_point,
            "sl": sl,
            "tp": tp,
            "order_point": order_point,
            "a_time": self.a_point_time,
            "b_time": self.b_point_time,
            "c_time": self.c_point_time,
            "a_index": self.a_point_index,
            "c_index": self.c_point_index,
            "b_index": self.b_point_index,

        }

    def find_order_points(self, current_price: decimal, find_abc, index=0):
        # result, order_point, abc_points = self.find_abc(current_price, index)
        result, order_point, abc_points = find_abc(current_price, index)
        if not result:
            return False, [], 0, {}

        orders_list = []

        return True, orders_list, order_point, abc_points

    def _find_abc_down(self, current_price: decimal, index=0):
        if current_price >= self.a_point:
            self.set_a_point(current_price, index)
            return False, 0.0, {}

        if self._find_b_point_down(current_price) and (
            current_price <= self.b_point or self.b_point == 0.0
        ):
            self.set_b_point(current_price, index)
            return False, 0.0, {}

        if self.b_point == 0.0:
            return False, 0.0, {}

        if self.find_c_point(current_price) and (
            current_price <= self.c_point or self.c_point == 0.0
        ):
            self.set_c_point(current_price, index)
            logger.debug(
                f"*** DOWN - FOUND ABC: {self.a_point} - {self.b_point} - {self.c_point}"
            )

            order_point = self.get_order_point()

            abc_points = self.get_point_data(order_point)
            self.reset_points()

            return True, order_point, abc_points

        return False, 0.0, {}

    def get_order_point(self):
        if self.points_distance.point_position == PointPosition.B.value:
            order_point = self.b_point + self.order_point_change
        elif self.points_distance.point_position == PointPosition.C.value:
            order_point = self.c_point + self.order_point_change
        elif self.points_distance.point_position == PointPosition.A.value:
            order_point = self.a_point + self.order_point_change
        return order_point

    def _find_abc_up(self, current_price: decimal, index=0):
        if current_price <= self.a_point or self.a_point == 0.0:
            self.set_a_point(current_price, index)
            return False, 0.0, {}
        if self.find_b_point(current_price) and (
            current_price >= self.b_point or self.b_point == 0.0
        ):
            self.set_b_point(current_price, index)
            return False, 0.0, {}
        if self.b_point == 0.0:
            return False, 0.0, {}
        if self.find_c_point(current_price) and (
            current_price >= self.c_point or self.c_point == 0.0
        ):
            self.set_c_point(current_price, index)
            logger.info(
                f"*** UP - FOUND ABC: {self.a_point} - {self.b_point} - {self.c_point}"
            )
            order_point = self.get_order_point()
            abc_points = self.get_point_data(order_point)
            self.reset_points()
            return True, order_point, abc_points

        return False, 0.0, {}

    def set_a_point(self, current_price: decimal, index: int = -1):
        if current_price < 1:
            return

        if current_price != self.a_point or index != self.a_point_index:
            self.a_point = current_price
            self.a_point_time = datetime.now()
            self.a_point_index = index
            self.b_point = 0.0
            self.b_point_time = None
            logger.info(f"FOUND A: {self.a_point}")

    def set_b_point(self, current_price: decimal, index: int = 0):
        # Only log if the price or index has changed
        if current_price < 1:
            return

        if current_price != self.b_point or index != self.b_point_index:
            self.b_point = current_price
            self.b_point_time = datetime.now()
            self.b_point_index = index
            logger.info(f"FOUND AB: {self.a_point} - {self.b_point}")

    def set_c_point(self, current_price: decimal, index: int = 0):
        if current_price < 1:
            return
        self.c_point = current_price
        self.c_point_time = datetime.now()
        self.c_point_index = index

    def _find_b_point_down(self, current_price: decimal) -> bool:
        return self.a_point - current_price >= self.points_distance.ab

    def _find_b_point_up(self, current_price: decimal) -> bool:
        return current_price - self.a_point >= self.points_distance.ab

    def _find_c_point_down(self, current_price: decimal) -> bool:
        return current_price - self.b_point >= self.points_distance.bc

    def _find_c_point_up(self, current_price: decimal) -> bool:
        return self.b_point - current_price >= self.points_distance.bc
