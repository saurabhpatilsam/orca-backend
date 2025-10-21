import csv
from datetime import datetime

from app.services.orca_max_backtesting.config import HIBERNATION_MODE
from app.services.orca_max_backtesting.helper import get_overlapping_orders
from app.utils.decorators.timing.time import time_it

# from orcaven.algorithm.abc_validator.config import HIBERNATION_MODE
# from orcaven.algorithm.abc_validator.helper import get_overlapping_orders
# from orcaven.clients.logger.logger import config_logging
# from orcaven.decorators.timing.time import time_it

from app.utils.logging_setup import logger


class TradeAnalyzer:
    def __init__(self, data, max_consecutive_reach, tp, sl, tick_price):
        self.max_consecutive_reach = max_consecutive_reach
        self.tp = tp  # Take Profit
        self.sl = sl  # Stop Loss
        self.sorted_data = self._clean_and_sort_data(data)
        self.hibernation_mode = HIBERNATION_MODE
        self.tick_price = tick_price
        if HIBERNATION_MODE:
            self.calculate_profit = self._calculate_profit_hibernation_time
        else:
            self.calculate_profit = self._calculate_profit_live

    def _clean_and_sort_data(self, data, date_from_file=False):
        """Cleans and sorts data by the 'Closed' column."""
        data_cleaned = [x for x in data if x.get("Closed") and x.get("Closed") != ""]
        # for reading from file
        if date_from_file:
            sorted_data = sorted(
                data_cleaned, key=lambda x: self.convert_to_datetime(x["Closed"])
            )
        else:
            sorted_data = sorted(data_cleaned, key=lambda x: x["Closed"])
        return sorted_data

    @staticmethod
    def convert_to_datetime(_date_string):
        """Converts a string to a datetime object."""
        return datetime.strptime(_date_string, "%Y-%m-%d %H:%M:%S")

    @time_it
    def _calculate_profit_hibernation(self):
        """Calculates profit based on the sorted data and returns as a dictionary."""
        results_dict = {
            consecutive_reach: {
                "win": 0,
                "lost": 0,
                "lost_trade_consecutive_count": 0,
                "max_consecutive_reached": False,
            }
            for consecutive_reach in range(2, self.max_consecutive_reach + 1)
        }

        try:
            for i, order_row in enumerate(self.sorted_data):
                for consecutive_reach in range(2, self.max_consecutive_reach + 1):
                    result = results_dict[consecutive_reach]
                    if order_row["Result"] == "Filled":
                        if result["max_consecutive_reached"]:
                            result["max_consecutive_reached"] = False
                            result["lost_trade_consecutive_count"] = 0
                            continue

                        result["win"] += 1
                        result["lost_trade_consecutive_count"] = 0
                        result["max_consecutive_reached"] = False

                    elif order_row["Result"] == "Lost":
                        result["lost_trade_consecutive_count"] += 1
                        if result["lost_trade_consecutive_count"] >= consecutive_reach:
                            if not result["max_consecutive_reached"]:
                                result["max_consecutive_reached"] = True
                                result["lost"] += 1
                        else:
                            result["lost"] += 1
        except Exception as e:
            logger.error(f"Error in _calculate_profit_hibernation_time: {e}")
            return {}

        # Calculate profits and sort by total
        sorted_profit_results = self.extract_result(results_dict)

        return sorted_profit_results

    def _calculate_profit_hibernation_time(self):
        """Calculates profit based on the sorted data and returns as a dictionary."""
        results_dict = {
            consecutive_reach: {
                "win": 0,
                "lost": 0,
                "lost_trade_consecutive_count": 0,
                "max_consecutive_reached": False,
                "win_overlapped_count": 0,
                "lost_overlapped_count": 0,
                "overlapped_orders_points": 0,
            }
            for consecutive_reach in range(2, self.max_consecutive_reach + 1)
        }

        # we get the overlapping orders
        # and all the order is linked to it
        overlapping_orders_info = get_overlapping_orders(self.sorted_data)

        def get_overlap_index(
            current_order,
        ):
            overlapped_orders_indexes = {"won": [], "lost": []}
            overlapped_orders_price = []
            # get the overlapping orders
            for item in overlapping_orders_info:
                # get the order that is overlapping with the other orders
                order = item["order"][1]
                # check if this order is the same as the current order
                if current_order == order:
                    # mean the order is overlapping
                    # if yes, then get overlapping orders with the current order
                    overlapped_orders = item["overlaps"]
                    for overlapped_order in overlapped_orders:
                        if overlapped_order[1]["Result"] == "Filled":
                            overlapped_orders_indexes["won"].append(overlapped_order[0])
                        elif overlapped_order[1]["Result"] == "Lost":
                            overlapped_orders_indexes["lost"].append(
                                overlapped_order[0]
                            )
                        else:
                            # not triggered yet
                            continue

                        # used to calculate the profit of lost depends on the price difference
                        # if it is positive mean the trade close in profit if negative mean the trade close in loss
                        closing_points = (
                            current_order["ClosedPrice"]
                            - overlapped_order[1]["Order_point"]
                        )
                        overlapped_orders_price.append(closing_points)
                    return overlapped_orders_indexes, overlapped_orders_price

            return [], []

        try:
            for i, order_row in enumerate(self.sorted_data):
                for consecutive_reach in range(2, self.max_consecutive_reach + 1):
                    result = results_dict[consecutive_reach]
                    if order_row["Result"] == "Filled":
                        if result["max_consecutive_reached"]:
                            result["max_consecutive_reached"] = False
                            result["lost_trade_consecutive_count"] = 0
                            continue

                        result["win"] += 1
                        result["lost_trade_consecutive_count"] = 0
                        result["max_consecutive_reached"] = False

                    elif order_row["Result"] == "Lost":
                        result["lost_trade_consecutive_count"] += 1
                        if result["lost_trade_consecutive_count"] >= consecutive_reach:
                            if not result["max_consecutive_reached"]:
                                result["max_consecutive_reached"] = True
                                result["lost"] += 1
                                # This is to calculate the profit of the lost trade for overlapping orders
                                overlapped_orders_indexes, overlapped_orders_price = (
                                    get_overlap_index(order_row)
                                )
                                # for hiberantion mode, exact calculation of the profit/lost
                                if (
                                    overlapped_orders_indexes
                                    and overlapped_orders_price
                                ):
                                    result["win_overlapped_count"] += len(
                                        overlapped_orders_indexes["won"]
                                    )
                                    result["lost_overlapped_count"] += len(
                                        overlapped_orders_indexes["lost"]
                                    )
                                    result["overlapped_orders_points"] += sum(
                                        overlapped_orders_price
                                    )
                        else:
                            result["lost"] += 1

        except Exception as e:
            logger.error(f"Error in _calculate_profit_hibernation: {e}")
            return {}

        # Calculate profits and sort by total
        sorted_profit_results = self.extract_result(results_dict)

        return sorted_profit_results

    @time_it
    def _calculate_profit_live(self):
        """Calculates profit based on the sorted data and returns as a dictionary."""
        results_dict = {
            0: {
                "win": 0,
                "lost": 0,
                "lost_trade_consecutive_count": 0,
                "max_consecutive_reached": False,
            }
        }

        for i, order_row in enumerate(self.sorted_data):
            if order_row["Result"] == "Filled":
                results_dict[0]["win"] += 1
            elif order_row["Result"] == "Lost":
                results_dict[0]["lost"] += 1

        sorted_profit_results = self.extract_result(results_dict)

        return sorted_profit_results

    def extract_result(self, _results):
        profit_results = {}
        tp_profit = self.tp * self.tick_price
        sl_loss = self.sl * self.tick_price
        for consecutive_reach, result in _results.items():
            win = result["win"]
            win_overlapped = result.get("lost_overlapped_count", 0)
            lost = result["lost"]
            lost_overlapped = result.get("win_overlapped_count", 0)

            # won_amount = win * tp_profit
            # lost_amount = lost * sl_loss

            won_amount = (win - win_overlapped) * tp_profit
            lost_amount = (lost - lost_overlapped) * sl_loss

            total = (won_amount - lost_amount) + (
                result.get("overlapped_orders_points", 0) * self.tick_price
            )
            profit_results[consecutive_reach] = {
                "NetProfit": total,
                "Won_trades": win,
                "Lost_trades": lost,
                "Profit": won_amount,
                "Loss": lost_amount,
            }
        # Sort the results by 'total' in descending order
        sorted_profit_results = dict(
            sorted(
                profit_results.items(),
                key=lambda item: item[1]["NetProfit"],
                reverse=True,
            )
        )

        return sorted_profit_results


@time_it
def read_csv(filename):
    """Reads the CSV file and loads data."""
    with open(filename, mode="r", newline="") as csvfile:
        csv_reader = csv.DictReader(csvfile)
        _data = list(csv_reader)
    return _data


if __name__ == "__main__":
    # file_long = '/Users/amerjod/Desktop/OrcaVentrures/orcaven/orcaven/algorithm/abc_validator/NQ15-16 09-24.Last_timed2-v2_v1/Amer_long_20_7_20240815_102601.csv'
    file_long = "/Users/amerjod/Desktop/OrcaVentrures/orcaven/orcaven/algorithm/abc_validator/NQ15-16 09-24.Last_timed2-v2_v1/BreakThrough_long_20_7_20240824_114001.csv"

    data = read_csv(file_long)

    max_consecutive_reach = 3
    tp = 20 * 20  # Example: 20 units with each worth 20
    sl = 7 * 20  # Example: 7 units with each worth 20

    analyzer = TradeAnalyzer(data, max_consecutive_reach, tp, sl)
    results = analyzer.calculate_profit()
    print(results)
