from typing import Tuple

import pandas as pd
from app.services.orca_max_backtesting.abc_tester import ABCStrategyTester
from app.services.orca_max_backtesting.config import PointsDistance
from app.services.orca_max_backtesting.helper import get_exit_strategies, create_abc_config, get_abc_points, read_file_cleaned, \
    OUTPUT_DIR, export_dict_to_csv, create_exit_strategy
from app.services.orca_max_backtesting.orca_enums import TeamWay, Contract
from app.services.orca_max_backtesting.plot.periods_data_processor import PeriodsDataProcessor
from app.utils.decorators.parallel import Parallel
from app.utils.decorators.timing.time import time_it

from app.utils.logging_setup import logger


def run(
    symbol: str,
    data: list,
    data_name: str,
    way,
    all_combinations=False,
    points_key="15_7_5",
) -> None:
    logger.info("Running ABC finder and validator")

    strategies = get_exit_strategies(all_combinations)

    conf = create_abc_config[points_key]
    points_distance = PointsDistance(
        conf["ab"],
        conf["bc"],
        conf["order_point"],
        1,
        20,
        min_distance_short_long=5,
    )

    @Parallel.processes(
        iterable=strategies.keys(),
        processes=8,
    )
    def run_bc_distance(exit_strategy_key: str):
        abc_points, output_folder_path = get_abc_points(
            points_distance, symbol, data_name, exit_strategy_key, points_key, data, way
        )

        abc_strategy = ABCStrategyTester(
            symbol,
            data,
            strategies[exit_strategy_key],
            exit_strategy_key,
            way,
            abc_points=abc_points,
            output_folder_path=output_folder_path,
            config=conf,
        )

        return abc_strategy.analyse()

    data = run_bc_distance()
    data_result_keys = []
    for _data, order_points_completed_dict in data:
        data_result_keys.append(_data)

    path = f"{OUTPUT_DIR}/{symbol}/{way.value}/ALL_{data_name}__result.csv"
    export_dict_to_csv(data_result_keys, path)


def split_data_daily(data: list) -> list:
    data_list = []
    for i in range(0, len(data), 2880):
        data_list.append(data[i : i + 2880])
    return data_list


@time_it
def run_single(
    symbol: str, data: list, data_name: str, way, exit_strategy_key, points_key: str
)-> Tuple[dict, dict]:
    logger.info("Running ABC finder and validator")

    conf = create_abc_config(points_key)
    points_distance = PointsDistance(
        conf["ab"],
        conf["bc"],
        conf["order_point"],
        1,
        20,
        min_distance_short_long=5,
    )

    # check if ABC points have been genersted before for  points_distance and file name
    # if so, load the points and skip the ABCFinder
    # if not, run the ABCFinder and save the points
    # points_distance, symbol, data_name, exit_strategy_key, data, way
    abc_points, output_folder_path = get_abc_points(
        points_distance, symbol, data_name, exit_strategy_key, points_key, data, way
    )

    exit_strategy = create_exit_strategy(exit_strategy_key)
    # examine the points
    abc_strategy = ABCStrategyTester(
        symbol,
        data,
        exit_strategy,
        exit_strategy_key,
        way,
        abc_points=abc_points,
        output_folder_path=output_folder_path,
        config=conf,
    )

    data, order_points_completed_dict = abc_strategy.analyse()


    return data, order_points_completed_dict

    # extract_trades(order_points_completed_dict, output_folder_path, symbol)

    # Converting to JSON string


def extract_trades(order_points_completed_dict, output_folder_path, symbol):
    for key, value in order_points_completed_dict.items():
        data_plot = []
        for d in value:
            try:
                if (
                    d.get("Triggered", "") == "" or d.get("Result") == "NotTriggered"
                ):  # means it not Triggered
                    continue

                data_plot.append(
                    [
                        d["Triggered"],
                        d["Closed"],
                        d["Result"],
                        d["Order_point"],
                        d["ClosedPrice"],
                        d["B_time"],
                    ]
                )
            except Exception as e:
                print(e)
        df = pd.DataFrame(
            data_plot,
            columns=[
                "Triggered",
                "Closed",
                "Result",
                "Order_point",
                "ClosedPrice",
                "B_time",
            ],
        )
        df.to_csv(f"{output_folder_path}/trades/{symbol}_{key.value}.csv", index=False)


def key_func(item):
    daily_data = True
    way = TeamWay.Reverse
    # file_name = "NQ15-16 09-24.Last_timed2"
    file_name = "1_ES 1Jan_10Mar_24.Last"
    # file_name = "NQ Mar-24.Last"
    # file_name = "NQ 22-23-08--09-24.Last"
    # file_name = "NQ Mar-24.Last"
    # file_name = "NQ Mar-24.Last"

    data, all_data = read_file_cleaned(file_name + ".txt", rows=-1)
    # plot_data2(data) pickle.dump(data, open(f"files/data_50K{file_name}.pickle", "wb")) data = pickle.load(open(
    # f"files/data_50K{file_name}.pickle", "rb")) file_name = 'data_NQ_07777' data = pickle.load(open(
    # "files/data_NQ_07.pickle", "rb")) data = pickle.load(open(
    # "/Users/amerjod/Desktop/OrcaVentrures/orcaven/testing_folder/graphs/tick_data_cleaned.pickle",
    # "rb")) run_single(data, data_name=file_name + "2", way=way, exit_strategy_key="20_7")
    # run(data, way=way, data_name=file_name + "-v2")
    exit_strategy_key = "20_7"

    run_single(
        data, data_name=file_name + "-v2", way=way, exit_strategy_key=exit_strategy_key
    )


@time_it
def run_single_file():

    CACHED = False
    EXPORT_TICK_DATA = False
    way = TeamWay.BreakThrough
    point_key = "15_7_5"
    exit_strategy_key = "15_15"
    symbol = Contract.NQ.value
    file_name = "NQ 09-25.Last"
    # file_name = "NQ 03-25_30.Last"
    # file_name = "NQ 01-07-2025.Last"
    # file_name = "NQ25_21_01_25.Last"

    if not file_name.startswith(symbol):
        raise ValueError(
            f"Make sure you change the symbol: '{symbol}' and file '{file_name}'"
        )

    data, all_data = read_file_cleaned(file_name + ".txt", rows=-1, cached=CACHED)

    if EXPORT_TICK_DATA:
        export_tick_by_tick(all_data, file_name, symbol)

    result , order_points_completed_dict = run_single(
        symbol,
        data,
        data_name=file_name + "-v2",
        way=way,
        exit_strategy_key=exit_strategy_key,
        points_key=point_key,
    )
    print(result)

def run_multiple_strategies():
    EXPORT_TICK_DATA = True
    # This is for running the all the comb that we have it on the Config file under the "EXIT_STRATEGIES_COMPENSATION"
    ALL_COMBINATIONS = True
    # If the above is False then it will run the "EXIT_STRATEGIES_MAX"
    # If the above is True then it will take the "EXIT_STRATEGIES_COMPENSATION" ( It will take time coz of no of combination )

    way = TeamWay.BreakThrough
    symbol = Contract.NQ.value

    # NQ should be the start of the File name
    # file_name = "NQ-Sep-10-NQ 09-24.Last"
    file_name = "NQ 09-25.Last"
    if symbol not in file_name:
        raise ValueError("Make sure you change the symbol")

    data, all_data = read_file_cleaned(file_name + ".txt", rows=-1)

    if EXPORT_TICK_DATA:
        export_tick_by_tick(all_data, file_name, symbol)

    run(
        symbol,
        data,
        way=way,
        data_name=file_name + "-v2",
        all_combinations=ALL_COMBINATIONS,
        points_key="15",
    )


def run_multiple_files_parallel():
    EXPORT_TICK_DATA = False
    ALL_COMBINATIONS = True
    way = TeamWay.Reverse
    POINT_KEY = 15
    exit_strategy_key = "2_10"
    symbol = Contract.NQ.value

    file_names = [
        "NQ-Sep-10-NQ 09-24.Last",
        "NQ-Sep-11-NQ 09-24.Last",
        # "NQ-Sep-12-NQ 09-24.Last",
        # "NQ-Sep-13-NQ 09-24.Last",
        # "NQ-Sep-14-NQ 09-24.Last",
        # "NQ-Sep-15-NQ 09-24.Last",
        # "NQ-Sep-16-NQ 09-24.Last",
        # "NQ-Sep-17-NQ 09-24.Last",
        # "NQ-Sep-17-NQ 09-24.Last"
    ]

    @Parallel.processes(
        iterable=file_names,
        processes=8,
    )
    def run_files(file_name):
        if symbol not in file_name:
            raise ValueError("Make sure you change the symbol")

        data, all_data = read_file_cleaned(file_name + ".txt", rows=-1)

        if EXPORT_TICK_DATA:
            export_tick_by_tick(all_data, file_name, symbol)

        run_single(
            symbol,
            data,
            data_name=file_name,
            way=way,
            exit_strategy_key=exit_strategy_key,
            points_key=POINT_KEY,
        )

    run_files()


def run_multiple_files_sequential():
    EXPORT_TICK_DATA = False
    ALL_COMBINATIONS = True
    way = TeamWay.BreakThrough

    POINT_KEY = "15_7_5"
    exit_strategy_key = "20_7"
    symbol = Contract.NQ.value

    file_names = [
        "9-NQ 09-24.Last",
        "10-NQ 09-24.Last",
        "11-NQ 09-24.Last",
        "12-NQ 09-24.Last",
        "13-NQ 09-24.Last",
        "16-NQ 09-24.Last",
        "17-NQ 12-24.Last",
        "18-NQ 12-24.Last",
    ]

    for file_name in file_names:
        if symbol not in file_name:
            raise ValueError("Make sure you change the symbol")

        data, all_data = read_file_cleaned(file_name + ".txt", rows=-1)

        if EXPORT_TICK_DATA:
            export_tick_by_tick(all_data, file_name, symbol)

        run_single(
            symbol,
            data,
            data_name=file_name,
            way=way,
            exit_strategy_key=exit_strategy_key,
            points_key=POINT_KEY,
        )


def export_tick_by_tick(all_data, file_name, symbol):
    # TODO: check if the files are already exported, then skip the export
    logger.info("Exporting periodic data to CSV")
    processor = PeriodsDataProcessor(symbol, file_name, all_data)
    processor.process()


if __name__ == "__main__":
    # To run the multiple files at same time with 1 exit strategy.
    # run_multiple_files_parallel()

    # To run the multiple files at same time with 1 exit strategy.slower and don't use it
    # run_multiple_files_sequential()

    # To run the 1 files at same time with 1 exit strategy.
    result =run_single_file()
    print(result)

    # To run the multiple files at same time with 1 exit strategy.
    # run_multiple_strategies()
