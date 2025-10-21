from typing import Protocol, Callable


class PriceProvider(Protocol):
    """Protocol for price data providers"""

    def get_price(self, instrument: str) -> float: ...
    def subscribe_price_stream(
        self, instrument: str, callback: Callable[[float], None]
    ): ...


class OrderExecutor(Protocol):
    """Protocol for order execution"""

    def place_order(
        self, account_token: str, account_id: str, **order_params
    ) -> str: ...
    def get_balance(self, account_id: str) -> float: ...
    def cancel_order(self, order_id: str) -> bool: ...
