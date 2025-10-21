import csv
from decimal import Decimal
from datetime import datetime

import os
import pickle


import pandas as pd
import pytz

from app.services.orca_max.schemas import ExitStrategy
from app.services.orca_max_backtesting.config import GENERATE_CSV, HIBERNATION_MODE, MAX_CONSECUTIVE_REACH, VERSION, \
    EXIT_STRATEGIES_COMPENSATION, PointsDistance
# from django.utils import timezone

from app.utils.decorators.timing.time import time_it
#
# from orcaven.algorithm.abc_validator.config import (
#     VERSION,
#     GENERATE_CSV,
#     HIBERNATION_MODE,
#     EXIT_STRATEGIES_COMPENSATION,
#     MAX_CONSECUTIVE_REACH,
# )
# from orcaven.clients.logger.logger import config_logging
# from orcaven.decorators.timing.time import time_it

from app.utils.logging_setup import logger

CURRENT_PATH = f"{os.path.dirname(os.path.abspath(__file__))}"

path = f"{os.path.dirname(os.path.abspath(__file__))}"

GRAPH_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "graph")
BAR_DATA_DIR = os.path.join(GRAPH_DIR, "bar_data")
OUTPUT_DIR = os.path.join(GRAPH_DIR, "output")


def dump_csv(
    down_dict: list,
    up_dict: list,
    points_distance_bc: str,
    data_name: str,
    folder_path,
) -> tuple[str, str]:

    if GENERATE_CSV:
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        write_csv(
            down_dict,
            f"{folder_path}/down_{data_name}_abc{points_distance_bc}_{timestamp}",
        )
        write_csv(
            up_dict,
            f"{folder_path}/up_{data_name}_abc{points_distance_bc}_{timestamp}",
        )
        logger.info("ABC Points (down/up) file generated")


def create_folder(symbol: str, data_name, team_way):
    version = 1

    base_path = os.path.join(
        symbol,
        team_way.value,
        "Hibernation" if HIBERNATION_MODE else "Normal",
        data_name,
    )

    while True:
        folder_name = f"{base_path}_v{version}"
        folder_path = os.path.join(OUTPUT_DIR, folder_name)
        try:
            os.makedirs(folder_path)
            break
        except FileExistsError:
            # Increment version number if folder already exists
            version += 1

    full_folder_path = os.path.join(folder_path, "trades")
    os.makedirs(full_folder_path)

    return folder_path


def get_price_time(time_string):
    time_string = " ".join(time_string.split(" ")[:-1])
    datetime_obj = datetime.strptime(time_string, "%Y%m%d %H%M%S")

    # Set timezone to the current timezone
    local_timezone = pytz.timezone("Europe/London")  # e.g., 'America/New_York'
    aware_datetime_obj = local_timezone.localize(datetime_obj)

    # Convert back to naive datetime
    naive_datetime_obj = aware_datetime_obj.replace(tzinfo=None)

    return naive_datetime_obj


def get_price_time2(time_string):
    time_string = " ".join(time_string.split(" ")[:-1])
    datetime_obj = datetime.strptime(time_string, "%Y%m%d %H%M%S")
    aware_datetime_obj = timezone.make_aware(
        datetime_obj, timezone.get_current_timezone()
    )
    naive_datetime_obj = aware_datetime_obj.replace(tzinfo=None)
    return naive_datetime_obj


@time_it
def read_file(file_name: str, rows=1000):
    logger.info(f"reading file {file_name}")
    data_list = []
    with open(f"{path}/files/{file_name}", "r") as file:
        for i, line in enumerate(file):
            parts = line.split(";")
            last_price = float(parts[2])
            last_price_datetime = get_price_time(parts[0])
            data_list.append((last_price, last_price_datetime))

            if rows != -1 and i == rows:
                break

    logger.info("finished reading file")
    return data_list


def read_file_list(file_name: str, rows=1000):
    logger.info(f"reading file {file_name}")
    lines = []
    with open(f"{path}/files/{file_name}", "r") as file:
        for i, line in enumerate(file):
            # Remove any leading/trailing whitespace and add the line to the list
            lines.append(line.strip())

            if rows != -1 and i == rows:
                break

    logger.info("finished reading file")
    return lines


def get_overlapping_orders(orders: list) -> list:
    overlapping_orders_list = []
    # Compare Closed time of each order with Triggered time of subsequent orders
    for current_index_i, current_order in enumerate(orders):
        # If the trade is a WON then no need to factor it, only loss trades
        if current_order["Result"] == "Filled":
            continue

        current_closed = current_order["Closed"]
        overlapping_info = {"order": (current_index_i, current_order), "overlaps": []}

        for current_index_j in range(current_index_i + 1, len(orders)):
            next_order = orders[current_index_j]

            next_triggered = next_order["Triggered"]

            # If next order's Triggered time falls before or within the current order's Closed time
            if next_triggered <= current_closed:
                # Add overlapping order to the 'overlaps' list
                overlapping_info["overlaps"].append((current_index_j, next_order))

        # Only add orders that have overlaps
        if overlapping_info["overlaps"]:
            overlapping_orders_list.append(overlapping_info)

    return overlapping_orders_list


def read_pickles(file_name, path):
    file_path_1 = os.path.join(path, "pickle_files/source", f"{file_name}.pickle")
    file_path_2 = os.path.join(path, "pickle_files/source", f"all_{file_name}.pickle")
    if os.path.exists(file_path_1) and os.path.exists(file_path_2):
        # If both files exist, load and return the content
        with open(file_path_1, "rb") as file1, open(file_path_2, "rb") as file2:
            data_list = pickle.load(file1)
            data_all_list = pickle.load(file2)
        logger.info("Files have been loaded form pickle")
        return data_list, data_all_list
    else:
        logger.info(f"One or both files are missing: {file_path_1}, {file_path_2}")
        return [], []


def read_abc_pickles(file_name, points_key):

    file_path_1 = os.path.join(
        CURRENT_PATH, "pickle_files/abc", f"down_{points_key}_{file_name}.pickle"
    )
    file_path_2 = os.path.join(
        CURRENT_PATH, "pickle_files/abc", f"up_{points_key}_{file_name}.pickle"
    )

    if os.path.exists(file_path_1) and os.path.exists(file_path_2):
        # If both files exist, load and return the content
        with open(file_path_1, "rb") as file1, open(file_path_2, "rb") as file2:
            down_abc_points = pickle.load(file1)
            up_abc_points = pickle.load(file2)
        logger.info("ABC points have been loaded form pickle")
        return down_abc_points, up_abc_points
    else:
        logger.info(f"One or both files are missing: {file_path_1}, {file_path_2}")
        return [], []


@time_it
def read_file_cleaned(file_name: str, rows=1000, cached=True):
    if cached:
        sanitized_data_list, data_all_list = read_pickles(file_name, path)
        if sanitized_data_list:
            logger.info("Getting Caching data")

            return sanitized_data_list, data_all_list
        logger.info("Caching data was not found")

    logger.info(f"reading text file {file_name}")
    sanitized_data_list, data_all_list = [], []

    with open(f"{path}/files/{file_name}", "r") as file:
        previous_row, previous_row_all = None, None
        index = 0
        for i, line in enumerate(file):
            line = line.strip()
            if previous_row_all != line:
                data_all_list.append(line)
                previous_row_all = line

            parts = line.split(";")
            last_price = float(parts[2])
            last_price_datetime = get_price_time(parts[0])

            if previous_row != (last_price, last_price_datetime):
                sanitized_data_list.append((last_price, last_price_datetime, index))
                previous_row = (last_price, last_price_datetime)
                index += 1

            if rows != -1 and i == rows:
                break

    logger.info("finished reading text file")

    # to save the data in pickle, so we don't need to read the file again
    # pickle.dump(
    #     sanitized_data_list,
    #     open(f"{path}/pickle_files/source/{file_name}.pickle", "wb"),
    # )
    # pickle.dump(
    #     data_all_list, open(f"{path}/pickle_files/source/all_{file_name}.pickle", "wb")
    # )
    logger.info("Data has been saved in pickle")

    return sanitized_data_list, data_all_list

@time_it
def read_bytes_cleaned(data_bytes: bytes, rows=1000):


    decoded_data = data_bytes.decode("utf-8")
    lines = decoded_data.strip().split("\n")
    logger.info(f"Processing uploaded bytes data: {len(lines)} lines")

    sanitized_data_list, data_all_list = [], []

    previous_row, previous_row_all = None, None
    index = 0

    for i, line in enumerate(lines):
        line = line.strip()
        if previous_row_all != line:
            data_all_list.append(line)
            previous_row_all = line

        parts = line.split(";")
        try:
            last_price = float(parts[2])
        except (IndexError, ValueError) as e:
            logger.warning(f"Skipping invalid line [{i}]: {line}")
            continue

        try:
            last_price_datetime = get_price_time(parts[0])
        except Exception as e:
            logger.warning(f"Failed to parse time on line [{i}]: {line}")
            continue

        if previous_row != (last_price, last_price_datetime):
            sanitized_data_list.append((last_price, last_price_datetime, index))
            previous_row = (last_price, last_price_datetime)
            index += 1

        if rows != -1 and i == rows:
            break

    logger.info("Finished processing bytes data")

    return sanitized_data_list, data_all_list


@time_it
def read_file_cleaned_new(file_name: str, rows=1000, cached=True):
    file_path = f"{path}/files/{file_name}"
    pickle_path = f"{path}/pickle_files/source/{file_name}.pickle"
    pickle_all_path = f"{path}/pickle_files/source/all_{file_name}.pickle"

    if cached:
        data_list, data_all_list = read_pickles(file_name, path)
        if data_list:
            logger.info("Using cached data")
            return data_list, data_all_list
        logger.info("fCache not found, reading file.. {file_path}")

    data_list, data_all_list = [], []

    previous_row, previous_row_all = None, None

    with open(file_path, "r") as file:
        for index, line in enumerate(file):
            if rows != -1 and index >= rows:
                break

            line = line.strip()

            # Store unique lines for data_all_list
            if line != previous_row_all:
                data_all_list.append(line)
                previous_row_all = line

            # Parse line details
            parts = line.split(";")
            last_price = float(parts[2])
            last_price_datetime = get_price_time(parts[0])
            current_row = (last_price, last_price_datetime)

            # Store unique price and datetime entries
            if current_row != previous_row:
                data_list.append((*current_row, index))
                previous_row = current_row

    logger.info(f"Finished reading file: {file_path}")

    # Save data to pickle files
    with open(pickle_path, "wb") as pf, open(pickle_all_path, "wb") as paf:
        pickle.dump(data_list, pf)
        pickle.dump(data_all_list, paf)
    logger.info("Data cached to pickle files")

    return data_list, data_all_list


#
HOURS_AVOID = [
    ("14:20", "14:45"),
    ("13:20", "13:45"),
]


def time_in_range(start_time, end_time, current_time):
    start = datetime.strptime(start_time, "%H:%M")
    end = datetime.strptime(end_time, "%H:%M")
    current = datetime.strptime(current_time, "%H:%M")

    return start <= current <= end


def in_restricted_trading_hours(time) -> bool:
    """
    Check if the current time is in any of the restricted trading hours.

    Returns:
        bool: True if the current time is within restricted trading hours, False otherwise.
    """
    current_time = time.strftime("%H:%M")
    for start, end in HOURS_AVOID:
        if time_in_range(start, end, current_time):
            return True
    return False


def get_abc_points(
    points_distance, symbol, data_name, exit_strategy_key, points_key, data, way
):
    # It can be improved by move out create folder.
    from app.services.orca_max_backtesting.abc import ABCFinder

    # output_folder_path is need to store the abc result csv files later on
    output_folder_path = create_folder(symbol, data_name, team_way=way)

    down_order_points_list, up_order_points_list = read_abc_pickles(
        data_name, points_key
    )
    if not down_order_points_list or not up_order_points_list:
        logger.info("Pickle ABC points not found, generating new ones")
    else:
        return {
            "down_order_points_list": down_order_points_list,
            "up_order_points_list": up_order_points_list,
        }, output_folder_path

    forward_abc = ABCFinder(points_distance, exit_strategy_key, way)
    down_order_points_list, up_order_points_list = forward_abc.find(data)

    logger.info("forward_abc finding Done")

    if False:
        pickle.dump(
            down_order_points_list,
            open(
                f"{CURRENT_PATH}/pickle_files/abc/down_{points_key}_{data_name}.pickle",
                "wb",
            ),
        )
        pickle.dump(
            up_order_points_list,
            open(
                f"{CURRENT_PATH}/pickle_files/abc/up_{points_key}_{data_name}.pickle", "wb"
            ),
        )

        dump_csv(
            down_order_points_list,
            up_order_points_list,
            points_distance.bc,
            data_name,
            folder_path=output_folder_path,
        )

    return {
        "down_order_points_list": down_order_points_list,
        "up_order_points_list": up_order_points_list,
    }, output_folder_path


@time_it
def read_file_cleaned_old(file_name: str, rows=1000):
    logger.info(f"reading file {file_name}")
    data_list = []
    with open(f"{path}/files/{file_name}", "r") as file:
        for i, line in enumerate(file):
            parts = line.split(";")
            last_price = float(parts[1])
            last_price_datetime = get_price_time(parts[0])
            data_list.append((last_price, last_price_datetime))

            if rows != -1 and i == rows:
                break

    logger.info("finished reading file")
    return data_list


@time_it
def read_file_plain(file_name: str):
    logger.info(f"reading file {file_name}")
    with open(f"{path}/files/{file_name}", "r") as file:
        return file.read()


def read_file_dict(file_name: str, rows=1000):
    logger.info(f"reading file {file_name}")
    data_dict = []
    with open(f"{path}/files/{file_name}", "r") as file:
        for i, line in enumerate(file):
            parts = line.split(";")
            bid_price = Decimal(parts[1])
            bid_price_datetime = get_price_time(parts[0])
            data_dict[i] = [bid_price, bid_price_datetime]

            if rows != -1 and i == rows:
                break

    logger.info("finished reading file")
    return data_dict


def read_file_list(file_name: str, rows=1000):
    logger.info(f"reading file {file_name}")
    lines = []
    with open(f"{path}/files/{file_name}", "r") as file:
        for i, line in enumerate(file):
            # Remove any leading/trailing whitespace and add the line to the list
            lines.append(line.strip())

            if rows != -1 and i == rows:
                break

    logger.info("finished reading file")
    return lines


def write_csv(data, file_name):
    df = pd.DataFrame(data)
    df.to_csv(f"{file_name}_{VERSION}.csv", index=False)


def read_order_points_csv(file_name: str):
    df = pd.read_csv(f"{path}/output/{file_name}")
    order_point_info = df.to_dict(orient="records")
    return order_point_info


def export_dict_to_csv(data, file_name="output.csv"):
    """
    Exports a nested dictionary to a CSV file.

    Parameters:
    - data (dict): The nested dictionary to export.
    - file_name (str): The name of the CSV file to save. Default is 'output.csv'.
    """

    # Prepare to flatten and convert the dictionary to a format suitable for CSV
    flattened_data = []

    for data_row in data:
        # Iterate over each item in the dictionary
        for main_key, sub_dict in data_row.items():
            for strategy, details in sub_dict.items():
                # Extract base-level details for 'Long' or 'Short' keys
                base_details = {
                    k: v for k, v in details.items() if isinstance(v, (int, str))
                }

                # Extract nested trade information
                for trade_key, trade_info in details.items():
                    if isinstance(
                        trade_key, int
                    ):  # This ensures that we're in the nested dictionary (2 or 3)
                        # Create a row with all necessary data
                        row = {
                            "MainKey": main_key,
                            "StrategyPoints": "t",
                            "Strategy": strategy,
                            "TradeLevel": trade_key,
                            **base_details,
                            **trade_info,
                        }
                        flattened_data.append(row)

    # Specify the CSV file header
    csv_header = [
        "MainKey",
        "StrategyPoints",
        "Strategy",
        "TradeLevel",
        "TP",
        "SL",
        "LOOSING_TRADES",
        "WINNING_TRADES",
        "NotTriggered",
        "NetProfit",
        "TotalTrades",
        "Won_trades",
        "Lost_trades",
        "MaxDrawDown",
        "Profit",
        "Loss",
    ]

    # Write to CSV file
    with open(file_name, mode="w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=csv_header)

        # Write header
        writer.writeheader()

        # Write data rows
        writer.writerows(flattened_data)

    logger.info(f"Data successfully exported to {file_name}")


def read_csv_to_dict_list(file_path):
    def convert_value(value):
        """Helper function to convert string values to int, float, or leave as string."""
        if value.isdigit():
            return int(value)  # Convert to integer if all characters are digits
        try:
            return float(value)  # Convert to float if it can be converted
        except ValueError:
            return value  # Return as string if it cannot be converted to int or float

    with open(file_path, mode="r", newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        dict_list = []

        for row in reader:
            converted_row = {key: convert_value(value) for key, value in row.items()}
            dict_list.append(converted_row)

    return dict_list


def get_exit_strategies(all_combinations: bool = False, reverse: bool = False) -> dict:
    if not all_combinations:
        return EXIT_STRATEGIES_MAX

    exit_strategies = {
        f"{i}_{j}": {
            "Long": {"TP": i, "SL": j},
            "Short": {"TP": (j if reverse else i), "SL": (i if reverse else j)},
            "max_lost_consecutive_count": MAX_CONSECUTIVE_REACH,
        }
        for i, j in EXIT_STRATEGIES_COMPENSATION
    }

    return exit_strategies


def create_exit_strategy(key_tp_sl: str, max_consecutive_reach=2):
    """
    Generate single exit strategy dictionary based on TP/SL values.

    Args:
        tp: Take profit value
        sl: Stop loss value
        max_consecutive_reach: Maximum consecutive losses allowed

    Returns:
        Dictionary with single strategy
    """
    tp, sl = map(int, key_tp_sl.split("_"))
    return {
        "Long": {"TP": tp, "SL": sl},
        "Short": {"TP": sl, "SL": tp},
        "max_lost_consecutive_count": max_consecutive_reach,
    }


def create_abc_config(abc_values: str):
    """
    Generate ABC configuration dictionary based on AB value.

    Args:
        ab_value: The main AB value (e.g., 15)

    Returns:
        PointsDistance
    """

    ab, bc, order_point, _ = map(int, abc_values.split("_"))

    points_distance = PointsDistance(
       ab,
       bc,
       order_point,
        # TODO: maybe we need to handle these, but for now No
        1,
        20,
        min_distance_short_long=5,
    )
    return points_distance

def create_exit_strategy_config(point_values: str )->ExitStrategy:
    """
    Generate ABC configuration dictionary based on AB value.

    Args:
        ab_value: The main AB value (e.g., 15)

    Returns:
        Dictionary with ABC configuration
    """

    tp, sl, = map(int, point_values.split("_"))
    return ExitStrategy(tp= tp, sl =sl)


# Example usage
