import time

from app.services.orca_max.abc import ABCFinder
from .helpers.enums import TeamWay, PointType
from .helpers.settings import PointsDistance
from .schemas import *
from app.services.orca_max.orca_protocol import PriceProvider
from app.services.orca_max.order_manager import *

from app.utils.logging_setup import logger


class OrcaMax:
    """Main algorithm orchestrator - the 'Max' algorithm"""

    def __init__(
        self,
        price_provider: PriceProvider,
        pattern_processor: ABCPatternProcessor,
        instrument_name: str,
        point_type: PointType,
        team_way: TeamWay,
        points_distance: PointsDistance,
        exit_strategy: ExitStrategy,
        quantity: int = 1,
    ):

        self.price_provider = price_provider
        self.instrument_name = instrument_name
        self.quantity = quantity
        self.pattern_processor=pattern_processor

        self.abc_finder = ABCFinder(
            price_provider=price_provider,
            points_distance=points_distance,
            point_type=point_type,
            team_way=team_way,
            exit_strategy=exit_strategy,
            instrument_name=instrument_name,
            quantity=quantity,
        )

        # for found order
        self.abc_finder.add_pattern_callback(self.pattern_processor.handle_abc_pattern)

        # Control flags
        self.stop_event = threading.Event()

        logger.info(f"OrcaMax initialized for {instrument_name}")

    def run(self):
        """Start the algorithm"""
        logger.info("Starting OrcaMax algorithm...")

        self.pattern_processor.start_processing()
        self.abc_finder.start_processing()

        # Keep running until stopped
        try:
            while not self.stop_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutdown initiated...")
        finally:
            self.stop()



    def stop(self):
        """Stop the algorithm"""
        self.stop_event.set()
        self.pattern_processor.stop()

        logger.info("OrcaMax stopped")
