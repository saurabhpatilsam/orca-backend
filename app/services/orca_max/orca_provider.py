import json
import threading
import time
from datetime import datetime
from typing import Dict, Callable
from app.services.orca_max.helpers.enums import ENVIRONMENT
from app.services.orca_max.helpers.orca_helper import read_file_cleaned
from app.services.orca_supabase.orca_supabase import stream_ticks_keyset
from app.utils.logging_setup import logger


class RedisPriceProvider:
    """Enhanced RedisPriceProvider with both streaming and direct price fetching"""

    def __init__(self, redis_client, environment, start_time, end_time, price_file: str = None):
        self.redis_client = redis_client
        self.environment = environment  # "prod" or "dev"
        self.price_file = price_file

        self.price_callbacks: Dict[str, Callable[[float], None]] = {}
        self.active_streams: Dict[str, bool] = {}

        # Cache latest prices for direct access
        self.latest_prices: Dict[str, float] = {}
        self.price_lock = threading.Lock()

        self.start_time = start_time
        self.end_time = end_time

    def get_price(self, instrument: str) -> float:
        """Get current/cached price for instrument"""
        with self.price_lock:
            if instrument in self.latest_prices:
                return self.latest_prices[instrument]

        if self.environment == ENVIRONMENT.PROD.value:
            return self._fetch_price_from_redis(instrument)
        elif self.environment == ENVIRONMENT.DEV.value or self.environment == ENVIRONMENT.DEV_SB.value:
            # In dev, just return cached price (or 0 if not started yet)
            return self.latest_prices.get(instrument, 0.0)

    def _fetch_price_from_redis(self, instrument: str) -> float:
        """Fetch price directly from Redis (one-time fetch)"""
        try:
            redis_pubsub = self.redis_client.pubsub()
            QUARTER_PERIOD = "Z5"  # TODO: automate year/quarter
            channel_name = f"TRADOVATE_{instrument}{QUARTER_PERIOD}_PRICE"
            logger.info("Fetching price for %s", channel_name)
            redis_pubsub.subscribe(channel_name)

            message = redis_pubsub.get_message(timeout=2)
            if message and message["type"] == "message":
                _data = json.loads(message["data"])
                price = float(_data["LAST"])
                with self.price_lock:
                    self.latest_prices[instrument] = price
                redis_pubsub.close()
                return price

            redis_pubsub.close()
            return 0.0
        except Exception as e:
            logger.error(f"Failed to fetch price for {instrument}: {e}")
            return 0.0

    def subscribe_price_stream(
        self, instrument: str, callback: Callable[[float], None]
    ):
        """Subscribe to price stream for instrument"""
        logger.info(f"Subscribing to price stream for {instrument} in {self.environment} mode")
        self.price_callbacks[instrument] = callback

        if instrument not in self.active_streams:
            self.active_streams[instrument] = True

            if self.environment == ENVIRONMENT.PROD.value:
                target = self._price_stream_worker
                args = (instrument,)
            #
            # for testing locally
            elif self.environment == ENVIRONMENT.DEV.value:
                if not self.price_file:
                    raise ValueError("price_file must be provided in dev environment.")
                target = self._file_stream_worker
                args = (instrument, self.price_file)

            elif self.environment == ENVIRONMENT.DEV_SB.value:
                target = self._supabase_stream_worker
                args = (instrument, self.start_time, self.end_time)
            else:
                raise ValueError(f"Unknown environment: {self.environment}")

            threading.Thread(
                target=target,
                args=args,
                daemon=True,
                name=f"PriceStream-{instrument}",
            ).start()

    def _price_stream_worker(self, instrument: str):
        """Worker thread for price streaming (prod/Redis)"""
        redis_pubsub = self.redis_client.pubsub()
        QUARTER_PERIOD = "Z5"  # TODO: automate year/quarter
        instrument_name = instrument.split(" ")[0]
        channel_name = f"TRADOVATE_{instrument_name}{QUARTER_PERIOD}_PRICE"
        redis_pubsub.subscribe(channel_name)
        logger.info(f"Started price stream worker for {channel_name}")

        try:
            while self.active_streams.get(instrument, False):
                message = redis_pubsub.get_message(timeout=1)
                if message and message["type"] == "message":
                    try:
                        _data = json.loads(message["data"])
                        price = float(_data["LAST"])
                        with self.price_lock:
                            self.latest_prices[instrument] = price
                        if instrument in self.price_callbacks:
                            self.price_callbacks[instrument](price)
                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        logger.error(f"Error parsing price data: {e}")
        except Exception as e:
            logger.error(f"Error in price stream worker for {instrument}: {e}")
        finally:
            redis_pubsub.close()
            logger.info(f"Price stream worker stopped for {instrument}")

    def _file_stream_worker(self, instrument: str, price_file: str):
        """Simulate price stream from a file (dev environment)."""
        logger.info(f"Simulating price stream for {instrument} - Reading prices ...")
        data, _ = read_file_cleaned(price_file + ".txt", rows=-1, cached=False)
        logger.info(f"Read {len(data)} rows from {price_file}.txt")
        for row in data:
            if not self.active_streams.get(instrument, False):
                break
            last_price = float(row[0])  # assuming last column is price
            with self.price_lock:
                self.latest_prices[instrument] = last_price
            if instrument in self.price_callbacks:
                self.price_callbacks[instrument](last_price)
            time.sleep(0.2)  # simulate tick delay
        logger.info(f"File stream worker finished for {instrument}")

    def _supabase_stream_worker(self, instrument: str, start_time: datetime, end_time:datetime):
        """Simulate price stream from a file (dev environment)."""
        logger.info(f"Simulating price stream for {instrument} Supabase - Reading prices ...")

        table_name = f"ticks_{instrument.lower()}"
        count =0
        for tick in stream_ticks_keyset(table_name, start_time, end_time):
            last_price = float(tick['last'])
            count+=1
            with self.price_lock:
                self.latest_prices[instrument] = last_price

            if instrument in self.price_callbacks:
                self.price_callbacks[instrument](last_price)
            # time.sleep(0.005)  # simulate tick delay
            # print(count)


    def stop_stream(self, instrument: str):
        """Stop price stream for instrument"""
        self.active_streams[instrument] = False
        if instrument in self.price_callbacks:
            del self.price_callbacks[instrument]
