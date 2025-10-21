import requests
import redis
from typing import Dict, Any, Optional, List
from urllib.parse import urlencode
from loguru import logger
import warnings
from urllib3.exceptions import InsecureRequestWarning

from app.services.orca_max.helpers.enums import TeamWay
from app.services.orca_max.schemas import (
    BrokerResponseSchema,
    AccountState,
    Order,
    Positions, AccountConfig,
)

# Suppress SSL warnings for demo API
warnings.filterwarnings("ignore", category=InsecureRequestWarning)


def get_token_from_redis(redis_client, key_name):
    """
    Retrieves the string value (token) from Redis for a given key.
    This function assumes the key type and value will always be a string.

    Args:
        redis_client (redis.Redis): The connected Redis client.
        key_name (str): The name of the Redis key to retrieve.

    Returns:
        str: The string value of the key if it exists, otherwise None.
    """
    if not redis_client:
        logger.error("Redis client is not available. Cannot retrieve token.")
        return None

    try:
        value = redis_client.get(key_name)

        if value is not None:
            logger.debug(f"Successfully retrieved token for key '{key_name}'.")
            return value
        else:
            logger.debug(f"Key '{key_name}' does not exist or has no value.")
            return None

    except redis.exceptions.RedisError as e:
        logger.error(f"Redis error while retrieving token for key '{key_name}': {e}")
        return None


class TradingViewTradovateBroker:
    """
    Tradovate Trading API wrapper with dynamic Redis token fetching.
    Fetches fresh JWT tokens from Redis for each API call since tokens change frequently.
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        account_name: str,
        accounts_ids: List[str] = [],
        base_url: str = "https://tv-demo.tradovateapi.com",
    ):
        """
        Initialize the trading API client.

        Args:
            redis_client: Redis client for fetching access tokens
            account_name: Trading account name (used as Redis key for token)
            base_url: API base URL (default: demo environment)
        """
        self.redis_client = redis_client
        self.account_name = account_name
        self.base_url = base_url.rstrip("/")

        # Common headers for all requests (Authorization will be set dynamically)
        self.base_headers = {
            "Host": "tv-demo.tradovateapi.com",
            "Connection": "keep-alive",
            "sec-ch-ua-platform": '"macOS"',
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "Origin": "https://www.tradingview.com",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://www.tradingview.com/",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        self.accounts_ids: List = accounts_ids
        if not accounts_ids and self.accounts_ids is not None:
            accounts: List[dict] = self.get_all_accounts()
            for acc in accounts:
                # id == 'tv' = "D17158695"
                # name == 'ta' = "PAAPEX1361890000002"
                self.accounts_ids.append(AccountConfig(tv_id=acc["id"], ta_id=acc["name"]))

    @property
    def token(self) -> str:
        """
        Property that retrieves a fresh JWT token from Redis each time it's accessed.

        Returns:
            str: The latest JWT access token.
        Raises:
            Exception: If token cannot be retrieved from Redis.
        """
        token = get_token_from_redis(self.redis_client, f"tokens:{self.account_name}")
        if not token:
            logger.error(f"Failed to retrieve token for account: {self.account_name}")
            raise Exception(f"No valid token found in Redis for account: {self.account_name}")
        logger.debug(f"Fetched fresh token for account '{self.account_name}'.")
        return token

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> BrokerResponseSchema:
        """
        Make an HTTP request with dynamic token fetching and error handling.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint
            data: Request data (for POST/PUT)
            headers: Additional headers

        Returns:
            Response data as dictionary
        """
        url = f"{self.base_url}{endpoint}"
        request_headers = self.base_headers.copy()
        request_headers["Authorization"] = f"Bearer {self.token}"

        if headers:
            request_headers.update(headers)
        try:
            logger.debug(f"Making {method} request to {url}")

            if data:
                # URL encode the data
                payload = urlencode(data)
                logger.debug(f"Request payload: {payload}")
                response = requests.request(
                    method, url, headers=request_headers, data=payload, verify=False
                )
            else:
                response = requests.request(
                    method, url, headers=request_headers, verify=False
                )

            response.raise_for_status()
            json_response = response.json()
            parsed_response = BrokerResponseSchema(**json_response)
            if parsed_response.s == "error":
                logger.error(f"API error: {parsed_response.errmsg}")
            return parsed_response
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise e

    def _get_account_id_by_name(self) -> str:
        """
        Extracts the account ID from a list of account dictionaries
        based on the provided account name.

        Args:
            accounts_list (list): A list of dictionaries, where each dictionary
                                represents an account.
            account_name (str): The name of the account to search for.

        Returns:
            str or None: The account ID if a match is found, otherwise None.
        """
        print(self.account_name)
        # Iterate through each account dictionary in the list
        for account in self.accounts:
            print(account)
            # Check if the 'name' of the current account matches the target account name
            if account.get("name") == self.account_name:
                account_id = account.get("id")
                logger.success(
                    f"Tradovate account name: {self.account_name} | Account ID: {account_id}"
                )
                return account_id

        # Raise exception and donot proceed if account ID is not found
        raise Exception("Account ID not extracted correctly")

    def place_order(
        self,
        order: Order,
        account_id: str,
    ) -> Optional[str]:
        """
        Place a new order.

        Args:
          Order
        Returns:
            Order ID of primary order / None
        """
        logger.info(
            f"Placing quantity:{order.quantity} order for `{order.instrument}` at `{order.price}`"
        )

        price_type = 'limitPrice'
        order_type = 'limit'
        if order.way == TeamWay.BreakThrough.value:
            price_type = 'stopPrice'
            order_type = 'stop'

        # price_type = 'stopPrice'
        # if order.position == OrderSides.SELL.value:
        #     price_type = 'limitPrice'
        #

        order_data = {
            "instrument": order.instrument,
            "qty": str(order.quantity),
            "side": order.position.lower(),
            'type': order_type,
            f"{price_type}": order.price,
            "stopLoss": str(order.stop_loss),
            "takeProfit": str(order.take_profit),
            "durationType": "Day",
        }

        print(order_data)
        endpoint = f"/accounts/{account_id}/orders?locale=en"
        response: BrokerResponseSchema = self._make_request(
            "POST", endpoint, order_data
        )
        return response.d.get("orderId", None)

    def update_order(
        self,
        order_id: str,
        limit_price: Optional[float] = None,
        qty: Optional[int] = None,
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None,
        current_ask: Optional[float] = None,
        current_bid: Optional[float] = None,
        duration_type: str = "Day",
    ) -> Dict[str, Any]:
        """
        Update an existing order.

        Args:
            order_id: Order ID to update
            limit_price: New limit price
            qty: New quantity
            take_profit: New take profit price
            stop_loss: New stop loss price
            current_ask: Current ask price
            current_bid: Current bid price
            duration_type: Order duration

        Returns:
            Update response data
        """
        logger.info(f"Updating order {order_id}")

        if not order_id:
            return {"error": "Order ID is required"}

        # Prepare update data
        update_data = {"id": order_id, "durationType": duration_type}

        # Add optional parameters
        if limit_price is not None:
            update_data["limitPrice"] = str(limit_price)
        if qty is not None:
            update_data["qty"] = str(qty)
        if take_profit is not None:
            update_data["takeProfit"] = str(take_profit)
        if stop_loss is not None:
            update_data["stopLoss"] = str(stop_loss)
        if current_ask is not None:
            update_data["currentAsk"] = str(current_ask)
        if current_bid is not None:
            update_data["currentBid"] = str(current_bid)

        endpoint = f"/accounts/{self.account_id}/orders/{order_id}?locale=en"
        return self._make_request("PUT", endpoint, update_data)

    def get_price_quotes(self, symbol: str) -> Dict:
        endpoint = f"/quotes?locale=en&symbols={symbol}"
        raw_response = self._make_request("GET", endpoint)
        try:
            return raw_response
        except Exception as e:
            logger.error(f"Failed to parse orders response: {e}")
            return OrderResponse(s="error", d=None, errmsg=str(e))

    def get_order(self, order_id: str, account_id) -> Order:
        """
        Get status of a specific order.

        Args:
            order_id: Order ID to check

        Returns:
            Order status data
        """
        logger.info(f"Getting order details for {order_id}")
        endpoint = f"/accounts/{account_id}/orders/{order_id}?locale=en"
        response: BrokerResponseSchema = self._make_request("GET", endpoint)

        try:
            return Order(**response.d)
        except Exception as e:
            logger.error(f"Failed to parse orders response: {e}")

    def get_orders(self,account_id : str) -> List[Order]:
        """
        Get all orders for the account.

        Args:
            etag: ETag for conditional requests (optional)

        Returns:
            Parsed OrdersResponse with list of Order objects
        """
        logger.info(f"Fetching ALL orders for account {account_id}")
        endpoint = f"/accounts/{account_id}/orders?locale=en"
        response = self._make_request("GET", endpoint)

        # Parse with Pydantic model
        try:
            orders: List[Order] = [Order(**item) for item in response.d]
            return orders
        except Exception as e:
            logger.error(f"Failed to parse orders response: {e}")
            raise Exception

    def cancel_order(self, order_id: str, account_id) -> Dict[str, Any]:
        """
        Cancel an order.

        Args:
            order_id: Order ID to cancel

        Returns:
            Cancellation response data
            If cannot cancel: {'s': 'error', 'errmsg': 'Too late'}
            If successful: {'s': 'ok'}
        """
        logger.info(f"Cancelling order {order_id}")
        endpoint = f"/accounts/{account_id}/orders/{order_id}?locale=en"
        return self._make_request("DELETE", endpoint)

    def get_account_state(self, account_id: str,etag: Optional[str] = None) -> AccountState:
        """
        Get account balance and state information.

        Args:
            etag: ETag for conditional requests (optional)

        Returns:
            Parsed AccountState with account data
        """
        logger.info(f"Fetching account state for account {account_id}")

        headers = {}
        if etag:
            headers["If-None-Match"] = etag

        endpoint = f"/accounts/{account_id}/state?locale=en"
        raw_response: BrokerResponseSchema = self._make_request(
            "GET", endpoint, headers=headers
        )
        # Parse with Pydantic model
        try:
            return AccountState(**raw_response.d)
        except Exception as e:
            logger.error(f"Failed to parse account state response: {e}")

    def get_all_accounts(self) -> List[Dict]:
        """
        Get account balance and state information.

        Args:
            etag: ETag for conditional requests (optional)

        Returns:
            Parsed AccountState with account data
        """
        logger.info('Fetching All Accounts .....')
        headers = {}
        endpoint = f"/accounts?locale=en"
        raw_response: BrokerResponseSchema = self._make_request(
            "GET", endpoint, headers=headers
        )

        result = raw_response.d
        logger.debug(f'Fetched {len(result)} Accounts')
        return raw_response.d

    def get_positions(self,account_id, etag: Optional[str] = None) -> List[Positions]:
        """
        Get all positions in the account.

        Args:
            etag: ETag for conditional requests (optional)

        Returns:
            Parsed PositionsResponse with positions data
        """
        logger.info(f"Fetching positions for account {account_id}")

        headers = {}
        if etag:
            headers["If-None-Match"] = etag

        endpoint = f"/accounts/{account_id}/positions?locale=en"
        raw_response: BrokerResponseSchema = self._make_request(
            "GET", endpoint, headers=headers
        )
        try:
            return [Positions(**item) for item in raw_response.d]
        except Exception as e:
            logger.error(f"Failed to parse positions response: {e}")


if __name__ == "__main__":
    # Example usage with Redis client

    pass
    # from tickr.external.redis.client import get_redis_client
    #
    # redis_client = get_redis_client()
    # account_name = "PAAPEX2659950000004"
    #
    # # Create trading client
    # client = TradingViewTradovateBroker(redis_client, account_name)
    #
    # # Example: Get orders with Pydantic models
    # result = client.get_account_state()
    # print(result)
