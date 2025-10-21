import os
import random
import string
import threading
from datetime import datetime
from enum import Enum
from typing import Callable, Optional, List

import pytz

from app.services.orca_max.helpers.enums import TeamWay, PointType, TradingPosition
from app.services.orca_max.helpers.settings import PointsDistance
from app.services.orca_max.schemas import Order
from app.services.orca_redis.client import get_redis_client
from app.utils.decorators.timing.time import time_it

from app.utils.logging_setup import logger


path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GRAPH_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "graph")
BAR_DATA_DIR = os.path.join(GRAPH_DIR, "bar_data")
OUTPUT_DIR = os.path.join(GRAPH_DIR, "output")


# Pre-defined trading positions mapping
TRADING_POSITION_MAP = {
    (PointType.UP, TeamWay.BreakThrough): TradingPosition.Long,
    (PointType.UP, TeamWay.Reverse): TradingPosition.Short,
    (PointType.DOWN, TeamWay.BreakThrough): TradingPosition.Short,
    (PointType.DOWN, TeamWay.Reverse): TradingPosition.Long,
}


# Get trading position based on PointType and TeamWay
def get_trading_position(point_type: PointType, team_way: TeamWay) -> TradingPosition:
    try:
        return TRADING_POSITION_MAP[(point_type, team_way)]
    except KeyError:
        raise ValueError(
            f"Invalid combination of PointType: {point_type} and TeamWay: {team_way}"
        )


def generate_unique_id(length=6) -> str:
    # Combine lowercase letters and digits
    characters = string.ascii_lowercase + string.digits
    # Generate a random 6-character string
    unique_text = "".join(random.choices(characters, k=length))
    return unique_text.upper()


Orca_ID = "ORCA"


class ACCOUNT(Enum):
    # RUN_HIBERNATION = run_hibernation
    APEX_136189 = "APEX_136189"
    APEX_266668 = "APEX_266668"
    APEX_272045 = "APEX_272045"
    APEX_265995 = "APEX_265995"


ACCOUNT_PASS = {
    "APEX_136189": "AG@2s#6$03M1",  # Amer
    "APEX_272045": "AFz222v#65Fe",  # Arjun
    "APEX_266668": "A3qF#R4s@7P@",  # Manish
    "APEX_265995": "A3r3$f$$@CH1",  # Manish
}


def get_account_token(account_id_ta) -> str:
    return get_redis_client().get(account_id_ta)


# Utility function for threading
def _run_in_thread(target_func: Callable, name: str, daemon=True):
    thread = threading.Thread(target=target_func, name=name, daemon=daemon)
    thread.start()
    logger.debug(f"Thread {name} started")
    return thread


def create_abc_config(abc_value: str, point_position: str):
    """
    Generate ABC configuration dictionary based on AB value.

    Args:
        ab_value: The main AB value (e.g., 15)

    Returns:
        Dictionary with ABC configuration
    """

    ab, bc, order_point, orders_distance = map(int, abc_value.split("_"))

    return PointsDistance(
        ab=ab,
        bc=bc,
        order_point=order_point,
        orders_number=1,
        orders_distance=orders_distance,
        min_distance_short_long=5,
        point_position=point_position,
    )

@time_it
def read_file_cleaned(file_name: str, rows=1000, cached=False):
    # if cached:
    #     sanitized_data_list, data_all_list = read_pickles(file_name, path)
    #     if sanitized_data_list:
    #         logger.info("Getting Caching data")
    #
    #         return sanitized_data_list, data_all_list
    #     logger.info("Caching data was not found")

    logger.info(f"reading text file {file_name}")
    sanitized_data_list, data_all_list = [], []

    with open(f"{path}/price_files/{file_name}", "r") as file:
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
    # logger.info("Data has been saved in pickle")

    return sanitized_data_list, data_all_list



def get_price_time(time_string):
    time_string = " ".join(time_string.split(" ")[:-1])
    datetime_obj = datetime.strptime(time_string, "%Y%m%d %H%M%S")

    # Set timezone to the current timezone
    local_timezone = pytz.timezone("Europe/London")  # e.g., 'America/New_York'
    aware_datetime_obj = local_timezone.localize(datetime_obj)

    # Convert back to naive datetime
    naive_datetime_obj = aware_datetime_obj.replace(tzinfo=None)

    return naive_datetime_obj


VERSION="0.1.1"
def banner():
    RED = "\33[91m"
    BLUE = "\33[94m"
    GREEN = "\033[32m"
    YELLOW = "\033[93m"
    PURPLE = '\033[0;35m'
    CYAN = "\033[36m"
    END = "\033[0m"
    banner_test= f"""                                                                         
     {RED} 
  ______   .______        ______     ___         .___  ___.      ___      ___   ___ 
 /  __  \  |   _  \      /      |   /   \        |   \/   |     /   \     \  \ /  / 
|  |  |  | |  |_)  |    |  ,----'  /  ^  \       |  \  /  |    /  ^  \     \  V  /  
|  |  |  | |      /     |  |      /  /_\  \      |  |\/|  |   /  /_\  \     >   <   
|  `--'  | |  |\  \----.|  `----./  _____  \     |  |  |  |  /  _____  \   /  .  \  
 \______/  | _| `._____| \______/__/     \__\    |__|  |__| /__/     \__\ /__/ \__\ 
                                                                                    
    """
    print(banner_test)

def banner2():
    RED = "\33[91m"
    BLUE = "\33[94m"
    GREEN = "\033[32m"
    YELLOW = "\033[93m"
    PURPLE = '\033[0;35m'
    CYAN = "\033[36m"
    END = "\033[0m"
    banner_test= f"""                                                                         
     {RED}                                                                                      
  .g8""8q.                                 `7MMM.     ,MMF'                    
.dP'    `YM.                                 MMMb    dPMM                      
dM'      `MM `7Mb,od8 ,p6"bo   ,6"Yb.        M YM   ,M MM   ,6"Yb.  `7M'   `MF'
MM        MM   MM' "'6M'  OO  8)   MM        M  Mb  M' MM  8)   MM    `VA ,V'  
MM.      ,MP   MM    8M        ,pm9MM        M  YM.P'  MM   ,pm9MM      XMX    
`Mb.    ,dP'   MM    YM.    , 8M   MM        M  `YM'   MM  8M   MM    ,V' VA.  
  `"bmmd"'   .JMML.   YMbmd'  `Moo9^Yo.    .JML. `'  .JMML.`Moo9^Yo..AM.   .MA.
  
  {BLUE} Version {VERSION}                                    By OrcaVenturers Ltd                                                                                                                             
"""
    print(banner_test)




def find_order_with_price_diff(orders: List[Order], price: float, diff_value: float) -> Optional[Order]:
    """
    Find the first order whose price differs from the given price by at least diff_value.

    :param orders: List of Order objects.
    :param price: The reference price to compare against.
    :param diff_value: The minimum difference threshold.
    :return: The first matching Order, or None if no such order exists.
    """
    for order in orders:
        if abs(order.price - price) >= diff_value:
            return order
    return None



#
# SUPABASE_URL=https://YOUR_PROJECT.supabase.co
# SUPABASE_KEY=YOUR_ANON_OR_SERVICE_ROLE_KEY


if __name__ == '__main__':
    banner()

