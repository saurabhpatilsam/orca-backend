import pickle
from datetime import datetime

import pandas as pd

from app.services.orca_max_backtesting.config import TICK_PRICES
from app.services.orca_max_backtesting.helper import in_restricted_trading_hours, read_order_points_csv
from app.services.orca_max_backtesting.orca_enums import TradingPosition, OrderStatus, TeamWay
from app.services.orca_max_backtesting.trade_analyzer import TradeAnalyzer
# from orcaven.algorithm.abc_validator.config import TICK_PRICES
#
# from orcaven.algorithm.abc_validator.helper import (
#     read_order_points_csv,
#     in_restricted_trading_hours,
# )
# from orcaven.algorithm.abc_validator.orca_enums import (
#     TradingPosition,
#     OrderStatus,
#     TeamWay,
# )
# from orcaven.algorithm.abc_validator.trade_analyzer import TradeAnalyzer
# from orcaven.clients.logger.logger import config_logging

from app.utils.logging_setup import logger


class ABCValidator:
    """
    This class is responsible for validating the ABC strategy for one type long or short
    """

    def __init__(
        self,
        order_points: list,
        NT_data,
        points_type: TradingPosition,
        exit_strategy,
        team_way,
        symbol,
        output_folder_path,
        config: dict,
    ):
        self.output_folder_path = output_folder_path
        self.order_points = order_points
        self.NT_data = NT_data
        self.symbol = symbol
        self.team_way = team_way

        self.previous_trade_result = 0
        self.previous_won_trade_result = 0
        self.previous_lost_trade_result = 0

        self.won_trade_consecutive_sum = 0
        self.lost_trade_consecutive_sum = 0
        self.won_trade_consecutive_count = 0
        self.lost_trade_consecutive_count = 0

        self.pointType = points_type
        self.max_lost_consecutive_count = exit_strategy["max_lost_consecutive_count"]
        self.config = config

        if points_type == TradingPosition.Long:
            self.validate_func = self._validate_long
            self.result = exit_strategy["Long"]
        else:
            self.validate_func = self._validate_short
            self.result = exit_strategy["Short"]


        self.temp_max_drawdown = 0
        self.max_drawdown_val = 0

        self.TP = self.result["TP"]
        self.SL = self.result["SL"]
        self.result["LOOSING_TRADES"] = 0
        self.result["WINNING_TRADES"] = 0
        self.result["NotTriggered"] = 0

        self.result["StrategyPoints"] = "-".join(
            [
                str(self.config["ab"]),
                str(self.config["bc"]),
                str(self.config["order_point"]),
            ]
        )
        self.tick_price = TICK_PRICES[self.symbol]

    def analyze_results(self):
        self.analyzer = TradeAnalyzer(
            self.order_points,
            self.max_lost_consecutive_count,
            self.TP,
            self.SL,
            self.tick_price,
        )
        return self.analyzer.calculate_profit()

    def validate(self):

        for row in self.order_points:
            self._validate_order(row)

        analyze_results = self.analyze_results()

        self.finalize_results(analyze_results)
        # self._save_results()

        return self.result, self.order_points

    def _validate_order(self, row):
        order_point_triggered = False
        c_i = row["C_index"]
        order_point = row["Order_point"]
        quantity = 1
        for price, time, index in self.NT_data[c_i:]:

            if in_restricted_trading_hours(time):
                continue

            if not order_point_triggered:
                if self._trigger_condition(price, order_point):
                    # logger.info(f"Triggered order point {order_point}, now validate")
                    order_point_triggered = True
                    row["Triggered_index"] = index
                    row["Triggered"] = time
            else:
                _result = self.validate_func(price, order_point)
                if _result:
                    trade_result = self.reg_result(
                        _result, price, quantity, row, time, index
                    )

                    row["TradeResult"] = trade_result
                    row["TradeResult"] = trade_result
                    row["TradeResultAccumulation"] = self.previous_trade_result

                    row["WonTradeConsecutiveSum"] = self.won_trade_consecutive_sum
                    row["WonTradeConsecutive"] = self.won_trade_consecutive_count
                    # row["MaxDrawDown"] = self.max_drawdown_val

                    row["LostTradeConsecutiveSum"] = (
                        self.lost_trade_consecutive_sum * -1
                    )
                    row["LostTradeConsecutive"] = self.lost_trade_consecutive_count
                    return

        row["Triggered"] = time.strftime("%Y-%m-%d %H:%M:%S")
        row["Result"] = OrderStatus.NotTriggered.value
        self.result["NotTriggered"] += 1

    def reg_result(self, _result, price, quantity, row, time, closed_index):
        row["Closed"] = time.strftime("%Y-%m-%d %H:%M:%S")
        # row["TradeSpan"] = time - row["Triggered"]
        row["TradeSpanTime"] = str(time - row["Triggered"])
        row["Triggered"] = row["Triggered"].strftime("%Y-%m-%d %H:%M:%S")
        row["Result"] = _result.value
        row["ClosedPrice"] = price
        row["ClosedPrice"] = price
        row["Closed_index"] = closed_index
        row["Order"] = self.pointType.value
        _trade_result = 0

        if _result == OrderStatus.Filled:
            _, _profit = self.get_trade_result_in_general("WINNING_TRADES", quantity)
            self.previous_trade_result += _profit
            _trade_result = _profit
            self.won_trade_consecutive_count += 1
            self.lost_trade_consecutiv_trade_resulte_count = 0
            # ---
            self.lost_trade_consecutive_count = 0
            self.lost_trade_consecutive_sum = 0
            self.won_trade_consecutive_sum += _trade_result

        else:

            _lost, _ = self.get_trade_result_in_general("LOOSING_TRADES", quantity)
            self.previous_trade_result -= _lost
            _trade_result = _lost * -1
            self.lost_trade_consecutive_count += 1
            self.won_trade_consecutive_count = 0

            self.won_trade_consecutive_sum = 0
            self.lost_trade_consecutive_sum += _trade_result * -1

        return _trade_result

    def _validate_short(self, price, order_point):
        # change this to long
        if price <= order_point - self.TP:
            # logger.info(f"Order point {order_point} lost.")
            self.result["WINNING_TRADES"] += 1
            return OrderStatus.Filled
        elif price >= order_point + self.SL:
            # logger.info(f"Order point {order_point} filled.")
            self.result["LOOSING_TRADES"] += 1
            return OrderStatus.Lost

    def _validate_long(self, price, order_point):
        # Cbnage this to SHORT
        if price >= order_point + self.TP:
            # logger.info(f"Order point {order_point} filled.")
            self.result["WINNING_TRADES"] += 1
            return OrderStatus.Filled
        elif price <= order_point - self.SL:
            # logger.info(f"Order point {order_point} lost.")
            self.result["LOOSING_TRADES"] += 1
            return OrderStatus.Lost

    def _trigger_condition_old(self, price, order_point):
        #  need to be reviewed for both ways
        return (
            price >= order_point
            if self.validate_func == self._validate_long
            else price <= order_point
        )

    def _trigger_condition(self, price, order_point):
        #  need to be reviewed for both ways

        if self.team_way == TeamWay.BreakThrough:
            return (
                price >= order_point
                if self.validate_func == self._validate_long
                else price <= order_point
            )
        else:
            return (
                price <= order_point
                if self.validate_func == self._validate_long
                else price >= order_point
            )

    def _save_results(self):
        # self.calculate_profit()
        # this function will show you all the possible trades
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        df = pd.DataFrame(self.order_points)
        strategy_point = "-".join(
            [
                str(self.config["ab"]),
                str(self.config["bc"]),
                str(self.config["order_point"]),
            ]
        )

        output_file = f"{self.output_folder_path}/{self.team_way.value}_{self.pointType.value}_{strategy_point}_{self.TP}_{self.SL}_{timestamp}.csv"
        df.to_csv(output_file, index=False)
        logger.info(f"Results saved to {output_file}")

    def finalize_results_old(self, analyze_results):
        profit = 0
        lost = 0

        # Log the individual profit and loss
        logger.info(f"Filled: {self.result.get('WINNING_TRADES', 0)}, profit: {profit}")
        logger.info(f"Lost: {self.result.get('LOOSING_TRADES', 0)}, lost: {lost}")
        logger.info(f"NotTriggered: {self.result.get('NotTriggered', 0)}")

        # Calculate and log the net profit
        net_profit = profit - lost
        w_trades = self.result.pop("WINNING_TRADES", 0)
        l_trades = self.result.pop("LOOSING_TRADES", 0)
        not_triggered = self.result.pop("NotTriggered", 0)

        logger.info(f"Net Profit: ${net_profit}")
        # what is C????????  maybe with $
        c = True

        if c:
            self.result["NetProfit"] = "${:,}".format(net_profit)
            self.result["TOTAL_TRADES_W_L"] = l_trades + w_trades
            self.result["WINNING_TRADES"] = w_trades
            self.result["LOOSING_TRADES"] = l_trades
            self.result["Profit"] = "${:,}".format(profit)
            self.result["Loss"] = "$-{:,}".format(lost)
            self.result["NotTriggered"] = not_triggered
            self.result["TotalTrades"] = not_triggered + w_trades + l_trades
            # self.result["Sara"] = self.count_max_consecutive_reach

        else:
            self.result["NetProfit"] = net_profit
            self.result["TOTAL_TRADES_W_L"] = l_trades + w_trades
            self.result["WINNING_TRADES"] = w_trades
            self.result["LOOSING_TRADES"] = l_trades
            self.result["Profit"] = profit
            self.result["Loss"] = lost
            self.result["NotTriggered"] = not_triggered
            self.result["TotalTrades"] = not_triggered + w_trades + l_trades

            # self.result["Sara"] = self.count_max_consecutive_reach

        self.result["_NetProfit"] = net_profit

    def finalize_results(self, analyze_results):
        c = True
        for consecutive_reach, result in analyze_results.items():
            win = result["Won_trades"]
            lost = result["Lost_trades"]
            won_amount = result["Profit"]
            lost_amount = result["Loss"]
            total = result["NetProfit"]
            logger.info(
                f"For max consecutive reach {consecutive_reach}: win = {win}, lost = {lost}  - won: {won_amount} - lost: {lost_amount}:  - total {total}"
            )
            if c:
                result["NetProfit"] = "${:,}".format(total)
                result["Profit"] = "${:,}".format(won_amount)
                result["Loss"] = "${:,}".format(lost_amount)
                result["MaxDrawDown"] = "${:,}".format(self.max_drawdown_val)

        self.result.update(analyze_results)

    def max_drawdown_tracker(self, max_drawdown):
        self.max_drawdown_val = max(self.max_drawdown_val, max(self.lost_trade_consecutive_sum, max_drawdown))

    def get_trade_result_in_general(self, key, value):
        # if it runs without enhancement, it will be removed
        lost, profit = 0, 0

        if self.pointType == TradingPosition.Long:
            if key == "WINNING_TRADES":
                profit = value * (self.TP * self.tick_price)
                self.temp_max_drawdown = 0
            elif key == "LOOSING_TRADES":
                lost = value * (self.SL * self.tick_price)
                self.temp_max_drawdown += lost
                self.max_drawdown_tracker(self.temp_max_drawdown)
        else:
            if key == "WINNING_TRADES":
                profit = value * (self.TP * self.tick_price)
                self.temp_max_drawdown = 0
            elif key == "LOOSING_TRADES":
                lost = value * (self.SL * self.tick_price)
                self.temp_max_drawdown += lost
                self.max_drawdown_tracker(self.temp_max_drawdown)

        return lost, profit


def run_test():
    abc_points_file = "short_data_bc_v3.csv"
    # abc_points_file = "long_data_bc15_2.3.csv"
    NT_points_file = "NQ 09-24_07.Last.txt"  # HUGE file

    order_points = read_order_points_csv(abc_points_file)
    logger.info("order points loaded")
    data = pickle.load(open("files/data_NQ_07_all.pickle", "rb"))
    # data = read_file(NT_points_file, rows=-)
    # get_result_short(order_points, data)
    # get_result_long(order_points, data)


if __name__ == "__main__":
    abc_points_file = "short_data_bc_v3.csv"
    # abc_points_file = "long_data_bc15_2.3.csv"
    NT_points_file = "NQ 09-24_07.Last.txt"  # HUGE file

    order_points = read_order_points_csv(abc_points_file)
    logger.info("order points loaded")
    data = pickle.load(open("files/data_NQ_07_all.pickle", "rb"))
    validator = ABCValidator(order_points, data, points_type=TradingPosition.Short)
    validator.validate()
