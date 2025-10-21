import json
from typing import Tuple

# from orcaven.algorithm.abc_validator.abc_validator import ABCValidator
# from orcaven.algorithm.abc_validator.helper import export_dict_to_csv
# from orcaven.algorithm.abc_validator.orca_enums import TeamWay, TradingPosition
#
# from orcaven.clients.logger.logger import config_logging
# from orcaven.decorators.timing.time import time_it
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.services.orca_max_backtesting.abc_validator import ABCValidator
from app.services.orca_max_backtesting.helper import export_dict_to_csv
from app.services.orca_max_backtesting.orca_enums import TeamWay, TradingPosition
from app.utils.decorators.timing.time import time_it
from app.utils.logging_setup import logger


WORKERS = 2


class ABCStrategyTester:
    def __init__(
        self,
        symbol: str,
        data,
        exit_strategy: dict,
        exit_strategy_key: str,
        team_way: TeamWay,
        abc_points: dict,
        output_folder_path: str,
        config: dict,
    ) -> None:
        self.symbol = symbol
        self.team_way = team_way
        self.data = data  # data is a list of tuples
        self.exit_strategy = exit_strategy
        self.exit_strategy_name = exit_strategy_key
        self.down_order_points_list = abc_points["down_order_points_list"]
        self.up_order_points_list = abc_points["up_order_points_list"]
        self.output_folder_path = output_folder_path
        self.config = config

    @time_it
    def analyse(self) -> Tuple[dict, dict]:
        # Here load
        logger.info("Analyse abc started, importing abc points ...")

        results = {
            self.exit_strategy_name: {
                TradingPosition.Long.value: None,
                TradingPosition.Short.value: None,
            }
        }  # To store results from validate calls

        long_list, short_list = self.get_o_points_list()
        logger.info("ABC validation has started ...")

        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            futures = {
                executor.submit(
                    self.validate,
                    long_list,
                    TradingPosition.Long,
                    self.team_way,
                    output_folder_path=self.output_folder_path,
                ): TradingPosition.Long,
                executor.submit(
                    self.validate,
                    short_list,
                    TradingPosition.Short,
                    self.team_way,
                    output_folder_path=self.output_folder_path,
                ): TradingPosition.Short,
            }

            order_points_completed_dict = {}
            for future in as_completed(futures):
                points_type = futures[future]
                try:
                    result, order_points_completed = (
                        future.result()
                    )  # Block until the thread completes and result is available
                    results[self.exit_strategy_name][points_type.value] = result
                    order_points_completed_dict[points_type.value] = order_points_completed
                except Exception as e:
                    logger.error(f"Validation raised an exception: {e}")
                    results[self.exit_strategy_name][points_type.value] = None

        logger.info(f"AbcTaster done")

        self.export_analyzed_results(results, self.output_folder_path)
        logger.info("Analyzed results exported")

        return results, order_points_completed_dict

    def export_analyzed_results(self, results, output_folder_path):
        export_dict_to_csv([results], f"{output_folder_path}/analyzed_result.csv")
        json.dump(
            results,
            open(f"{output_folder_path}/analyzed_result.json", "w"),
            indent=4,
        )

    def get_o_points_list(self):
        if self.team_way == TeamWay.BreakThrough:
            # Reverse the way of Sarab
            long_list = self.up_order_points_list
            short_list = self.down_order_points_list
        else:
            long_list = self.down_order_points_list
            short_list = self.up_order_points_list
        return long_list, short_list

    def validate(
        self, order_points, points_type: TradingPosition, team_way, output_folder_path
    ):
        validator = ABCValidator(
            order_points,
            self.data,
            points_type=points_type,
            exit_strategy=self.exit_strategy,
            team_way=team_way,
            symbol=self.symbol,
            output_folder_path=output_folder_path,
            config=self.config,
        )
        return validator.validate()
