import queue
import threading
from datetime import datetime
from typing import Dict, Any

from app.services.orca_max.helpers.enums import OrderStatus, TeamWay
from app.services.orca_max.schemas import Order

from app.utils.logging_setup import logger


class OrderManager():
    """Manages order creation and execution"""

    def __init__(self, broker, way: TeamWay):
        self.broker = broker
        self.all_orders = []
        self.placed_orders = []
        self.stop_event = threading.Event()
        self.pause_placing = False
        self.can_place = True
        self.way = way
        self._lock = threading.Lock()

    def create_order(self, order_dict: Dict[str, Any]) -> Order:
        """Create order from ABC pattern data"""
        order = Order(
            # instrument=order_dict["instrument_name"],
            instrument="MNQZ5",
            price=order_dict["order_point"],
            position=order_dict["position"],
            take_profit=order_dict["tp"],
            stop_loss=order_dict["sl"],
            order_type=order_dict["type"],
            quantity=order_dict.get("quantity", 1),
            timestamp=datetime.now(),
            order_dict_all=order_dict,
            status=OrderStatus.PENDING.value,
            way=self.way
        )

        self.all_orders.append(order)

        return order

    def place_order(self, order: Order) -> bool:
        """Add order to management system"""
        try:
            with self._lock:
                if not self.pause_placing and self.can_place:
                    # Here you would integrate with your broker/exchange API
                    order.status = OrderStatus.CREATED
                    for account in self.broker.accounts_ids:
                        # account_id_tv, account_id_to = account.tv, account
                        logger.info(f'Placing order {order.id_orca} for {order.instrument} for account {account.ta_id}')
                        order_tv_id = self.broker.place_order(order=order, account_id=account.tv_id)
                        print(order_tv_id)
                        break
                    return True
                else:
                    logger.info("Order placement paused")
                    return False
        except Exception as e:
            logger.error(f"Failed to create order: {e}")
            order.status = OrderStatus.REJECTED
            return False

    def get_active_orders(self) -> list:
        """Get all active orders"""
        with self._lock:
            return [
                o
                for o in self.orders
                if o.status in [OrderStatus.PENDING, OrderStatus.CREATED]
            ]


class ABCPatternProcessor:
    """Processes ABC patterns asynchronously using queue"""

    def __init__(self, order_manager: OrderManager, max_queue_size: int = 100):
        self.order_manager = order_manager
        self.pattern_queue = queue.Queue(maxsize=max_queue_size)
        self.processing_thread = None
        self.stop_processing = threading.Event()
        self.stats = {
            "patterns_received": 0,
            "orders_created": 0,
            "processing_errors": 0,
        }

    def start_processing(self):
        """Start processing ABC patterns in background thread"""
        if self.processing_thread and self.processing_thread.is_alive():
            logger.warning("Pattern processor already running")
            return

        self.stop_processing.clear()
        self.processing_thread = threading.Thread(
            target=self._process_patterns_worker,
            daemon=True,
            name="ABCPatternProcessor",
        )
        self.processing_thread.start()
        logger.info("ABC Pattern Processor started")

    def _process_patterns_worker(self):
        """Worker thread that processes patterns from queue"""
        while not self.stop_processing.is_set():
            try:
                # Wait for pattern with timeout to allow clean shutdown
                order_points = self.pattern_queue.get(timeout=1.0)

                # Process the pattern
                success = self._process_single_pattern(order_points)

                # Update stats
                if success:
                    self.stats["orders_created"] += 1

                self.pattern_queue.task_done()

            except queue.Empty:
                continue  # Timeout reached, check stop condition
            except Exception as e:
                logger.error(f"Unexpected error in pattern processor: {e}")
                self.stats["processing_errors"] += 1

    def _process_single_pattern(self, order_points: Dict[str, Any]) -> bool:
        """Process a single ABC pattern"""
        try:
            # Validate pattern data
            if not self._validate_pattern(order_points):
                logger.warning(f"Invalid pattern data: {order_points}")
                return False

            # Create order
            order = self.order_manager.create_order(order_points)

            # Submit order
            success = self.order_manager.place_order(order)

            if success:
                logger.info(
                    f"ABC Pattern processed: {order_points['type']} "
                    f"at {order_points['order_point']} for {order_points['instrument_name']}"
                )

            return success

        except Exception as e:
            logger.error(f"Error processing ABC pattern: {e}")
            self.stats["processing_errors"] += 1
            return False

    def _validate_pattern(self, order_points: Dict[str, Any]) -> bool:
        """Validate ABC pattern data"""
        required_fields = ["order_point", "tp", "sl", "type"]
        return all(field in order_points for field in required_fields)

    def handle_abc_pattern(self, order_points: Dict[str, Any]):
        """Callback method to receive ABC patterns (thread-safe)"""
        try:
            self.stats["patterns_received"] += 1

            # Add to queue (non-blocking with timeout)
            self.pattern_queue.put(order_points, timeout=0.1)

            logger.debug(
                f"ABC pattern queued: {order_points['type']} for {order_points.get('instrument_name')}"
            )

        except queue.Full:
            logger.warning("Pattern queue full, dropping pattern")
        except Exception as e:
            logger.error(f"Error queuing ABC pattern: {e}")

    def stop(self):
        """Stop processing gracefully"""
        logger.info("Stopping ABC Pattern Processor...")
        self.stop_processing.set()

        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=5.0)

        logger.info(f"Pattern Processor stopped. Stats: {self.stats}")

    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        return {
            **self.stats,
            "queue_size": self.pattern_queue.qsize(),
            "is_running": not self.stop_processing.is_set(),
        }
