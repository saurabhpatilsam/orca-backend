import decimal
from datetime import datetime
from typing import Type, List, Dict, Any, Tuple

from app.services.orca_max_backtesting.config import PointsDistance
from app.services.orca_max_backtesting.helper import in_restricted_trading_hours
from app.services.orca_max_backtesting.orca_enums import PointType
from app.utils.logging_setup import logger


class ABCFinder:
    def __init__(
        self, points_distance: Type[PointsDistance], exit_strategy: str, team_way
    ) -> None:
        self.abc_down = ForwardABC(points_distance, PointType.DOWN, exit_strategy)
        self.abc_up = ForwardABC(points_distance, PointType.UP, exit_strategy)
        logger.info(f"ABC Finder initialized with {points_distance}")

    def _process(
        self, abc_processor, price, time, index
    ) -> Tuple[bool, Dict[str, Any]]:
        result, orders_list, order_point, abc_points = abc_processor.find_order_points(
            price, time, abc_processor.find_abc, index
        )

        if result:
            return True, abc_points
        return False, {}

    def find(self, data) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        down_order_points_list = []
        up_order_points_list = []

        for index, (price, time, i) in enumerate(data):
            if in_restricted_trading_hours(time):
                continue
            down_result, down_abc_points = self._process(
                self.abc_down, price, time, index
            )
            up_result, up_abc_points = self._process(self.abc_up, price, time, index)

            if down_result:
                down_order_points_list.append(down_abc_points)

            if up_result:
                up_order_points_list.append(up_abc_points)

        logger.info(f"Found {len(down_order_points_list)} DOWN points")
        logger.info(f"Found {len(up_order_points_list)} UP points")

        return down_order_points_list, up_order_points_list


class ForwardABC:
    def __init__(
        self,
        points_distance: Type[PointsDistance],
        point_type: PointType,
        exit_strategy: str,
    ) -> None:

        self.points_distance = points_distance
        self.order_point = points_distance.order_point

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
        self.exit_strategy = exit_strategy

        if point_type == PointType.DOWN:
            self.find_b_point = self._find_b_point_down
            self.find_c_point = self._find_c_point_down
            self.find_abc = self._find_abc_down
        else:
            self.find_b_point = self._find_b_point_up
            self.find_c_point = self._find_c_point_up
            self.find_abc = self._find_abc_up

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
        return {
            "Type": self.point_type.value,
            "Exit": self.exit_strategy,
            "BC_Distance": self.points_distance.bc,
            "A": self.a_point,
            "B": self.b_point,
            "C": self.c_point,
            "Order_point": order_point,
            "A_time": self.a_point_time.strftime("%Y-%m-%d %H:%M:%S"),
            "B_time": self.b_point_time.strftime("%Y-%m-%d %H:%M:%S"),
            "C_time": self.c_point_time.strftime("%Y-%m-%d %H:%M:%S"),
            "A_index": self.a_point_index,
            "C_index": self.c_point_index,
            "B_index": self.b_point_index,
        }

    def find_order_points(
        self, current_price: decimal, time: datetime, find_abc, index=0
    ):
        result, order_point, abc_points = find_abc(current_price, time, index)

        if not result:
            return False, [], 0, {}

        orders_list = []

        return True, orders_list, order_point, abc_points

    def _find_abc_down(self, current_price: decimal, time: datetime, index=0):
        if current_price >= self.a_point:
            self.set_a_point(current_price, time, index)
            return False, 0.0, {}

        if self._find_b_point_down(current_price) and (
            current_price <= self.b_point or self.b_point == 0.0
        ):
            self.set_b_point(current_price, time, index)
            return False, 0.0, {}

        if self.b_point == 0.0:
            return False, 0.0, {}

        if self.find_c_point(current_price) and (
            current_price <= self.c_point or self.c_point == 0.0
        ):
            self.set_c_point(current_price, time, index)
            logger.debug(
                f"*** DOWN - FOUND ABC: {self.a_point} - {self.b_point} - {self.c_point}"
            )

            order_point = self.c_point + self.order_point
            abc_points = self.get_point_data(order_point)
            self.reset_points()

            return True, order_point, abc_points

        return False, 0.0, {}

    def _find_abc_up(self, current_price: decimal, time: datetime, index=0):
        if current_price <= self.a_point or self.a_point == 0.0:
            self.set_a_point(current_price, time, index)
            return False, 0.0, {}
        if self.find_b_point(current_price) and (
            current_price >= self.b_point or self.b_point == 0.0
        ):
            self.set_b_point(current_price, time, index)
            return False, 0.0, {}
        if self.b_point == 0.0:
            return False, 0.0, {}
        if self.find_c_point(current_price) and (
            current_price >= self.c_point or self.c_point == 0.0
        ):
            self.set_c_point(current_price, time, index)
            logger.debug(
                f"*** UP - FOUND ABC: {self.a_point} - {self.b_point} - {self.c_point}"
            )
            # should be called order_point
            # order_point = self.b_point - 5
            order_point = self.c_point + self.order_point
            abc_points = self.get_point_data(order_point)
            self.reset_points()
            return True, order_point, abc_points

        return False, 0.0, {}

    def set_a_point(self, current_price: decimal, time: datetime, index: int):
        self.a_point = current_price
        self.a_point_time = time
        self.a_point_index = index
        self.b_point = 0.0
        self.b_point_time = None
        # logger.info(f"FOUND A: {self.a_point}")

    def set_b_point(self, current_price: decimal, time: datetime, index: int):
        self.b_point = current_price
        self.b_point_time = time
        self.b_point_index = index
        # logger.info(f"FOUND AB: {self.a_point} - {self.b_point}")

    def set_c_point(self, current_price: decimal, time: datetime, index: int):
        self.c_point = current_price
        self.c_point_time = time
        self.c_point_index = index

    def _find_b_point_down(self, current_price: decimal) -> bool:
        return self.a_point - current_price >= self.points_distance.ab

    def _find_b_point_up(self, current_price: decimal) -> bool:
        return current_price - self.a_point >= self.points_distance.ab

    def _find_c_point_down(self, current_price: decimal) -> bool:
        return current_price - self.b_point >= self.points_distance.bc

    def _find_c_point_up(self, current_price: decimal) -> bool:
        return self.b_point - current_price >= self.points_distance.bc
