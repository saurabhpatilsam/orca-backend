import time
from typing import Dict, Any

from app.services.orca_max.helpers.enums import ENVIRONMENT
from app.services.orca_max.helpers.orca_helper import banner2, create_abc_config
from app.services.orca_max.orca_max import OrcaMax
from app.services.orca_max_backtesting.helper import create_exit_strategy_config
from app.services.orca_redis.client import get_redis_client
from app.services.orca_max.orca_provider import RedisPriceProvider
from app.services.orca_max.order_manager import ABCPatternProcessor, OrderManager
from app.services.tradingview.broker import TradingViewTradovateBroker
from app.services.orca_supabase.orca_supabase import (
    insert_run_config,
    update_run_config_status,
    has_active_duplicate
)
from app.services.orca_supabase.config_utils import extract_strategy_config

from app.utils.logging_setup import logger

MAX_PATTERN_QUEUE_SIZE = 1000


def run_orca_system(run_config: Dict[str, Any]):
    """
    Run the complete Orca trading system.
    Note: Config should already be stored with status 'queued' before calling this.
    """
    try:
        banner2()
        time.sleep(1)
        environment = run_config["environment"]
        # TODO: only when we run it locally
        price_file_name = run_config["price_file"]
        logger.info(f"********************************************************")
        logger.info(f"**************| Running Orca trading {environment} |**************")
        logger.info(f"********************************************************")
        if environment == ENVIRONMENT.DEV and not price_file_name:
            raise EnvironmentError(
                f"No price file for this environment: {environment.value}"
            )

        #
        redis_client = get_redis_client()
        tradovate_broker = TradingViewTradovateBroker(
            redis_client, run_config["main_account"], run_config["accounts_ids"]
        )

        start_time = run_config["start_time"]
        end_time = run_config["end_time"]

        # Create adapters
        # price_provider = RedisPriceProvider(redis_client, environment, price_file_name)
        price_provider = RedisPriceProvider(redis_client, environment, start_time, end_time)
        order_manager = OrderManager(tradovate_broker, way=run_config['way'])

        pattern_processor = ABCPatternProcessor(
            order_manager, max_queue_size=MAX_PATTERN_QUEUE_SIZE
        )

        points_distance = create_abc_config(run_config["point_strategy_key"], run_config["point_position"].value)
        exit_strategy = create_exit_strategy_config(run_config["exit_strategy_key"])

        # Create and configure the system
        orca_max = OrcaMax(
            price_provider=price_provider,
            pattern_processor=pattern_processor,
            instrument_name=run_config["instrument_name"],
            point_type=run_config["point_type"],
            team_way=run_config["way"],
            points_distance=points_distance,
            exit_strategy=exit_strategy,
            quantity=run_config.get("quantity", 1),
        )

        # Run the system
        orca_max.run()
        
        logger.info(f"Orca system completed successfully")
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Error in run_orca_system: {str(e)}")
        raise
