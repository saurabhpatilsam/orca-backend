import os
import redis
from loguru import logger
from dotenv import load_dotenv

load_dotenv()


def get_redis_client():
    """
    Establishes a connection to Azure Cache for Redis and returns the client object.
    """

    REDIS_HOST = os.getenv("REDIS_HOST")
    REDIS_PORT = os.getenv("REDIS_PORT", "6380")
    REDIS_PRIMARY_ACCESS_KEY = os.getenv("REDIS_PRIMARY_ACCESS_KEY")

    if not all([REDIS_HOST, REDIS_PORT, REDIS_PRIMARY_ACCESS_KEY]):
        logger.error(
            "Missing one or more Redis environment variables. Check your .env file."
        )
        return None

    try:
        r = redis.Redis(
            host=REDIS_HOST,
            port=int(REDIS_PORT),
            password=REDIS_PRIMARY_ACCESS_KEY,
            decode_responses=True,
            ssl=True,
            ssl_cert_reqs=None,  # Disable SSL certificate verification for Azure Cache
        )

        r.ping()
        logger.debug(
            f"Connected to Azure Cache for Redis at {REDIS_HOST}:{REDIS_PORT} successfully!"
        )
        return r
    except redis.exceptions.ConnectionError as e:
        logger.error(f"Failed to connect to Azure Cache for Redis: {e}")
        return None
    except ValueError as e:
        logger.error(f"Invalid Redis port number in environment variables: {e}")
        return None


if __name__ == "__main__":
    get_redis_client()
