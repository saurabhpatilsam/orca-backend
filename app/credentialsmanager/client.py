import json
import requests
import redis
import os
from loguru import logger
from dotenv import load_dotenv
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
import httpx
from datetime import datetime
from enum import Enum
from time import sleep
import time

from app.services.orca_redis.client import get_redis_client


class AlertType(Enum):
    Pass = "Pass"
    Fail = "Fail"

# Define the Time-To-Live (TTL) for the tokens in seconds (1 hour)
TTL_SECONDS = 60 * 60

# We will use a global client, as redis-py's Redis client is thread-safe
REDIS_CLIENT = None


def discord_alert(type: AlertType, message: str) -> None:
    ribbon = 9498256 if type == AlertType.Pass else 16711680
    embed = {
        "title": f"`Credentials Manager`",
        "description": message,
        "color": ribbon,
        "footer": {
            "text": "Alert: " + datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    }
    payload = {"embeds": [embed]}
    response = httpx.post("https://discord.com/api/webhooks/1402811131613020312/sNRHWlMzQM3KQ3Z4522g07AFfOEdCS36i-SleW4NEKByVX0oxWSHxeHSSAXOMl8C_nx-", json=payload)

def get_access_token(username, password):
    """
    Performs an API call to get an access token using the provided credentials.
    """
    url = "https://tv-demo.tradovateapi.com/authorize?locale=en"
    encoded_username = urllib.parse.quote(username)
    encoded_password = urllib.parse.quote(password)
    payload = f'locale=en&login={encoded_username}&password={encoded_password}'
    
    headers = {
        'Host': 'tv-demo.tradovateapi.com',
        'Connection': 'keep-alive',
        'sec-ch-ua-platform': '"macOS"',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'sec-ch-ua': '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'Origin': 'https://www.tradingview.com',
        'Sec-Fetch-Site': 'cross-site',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Dest': 'empty',
        'Referer': 'https://www.tradingview.com/',
        'Accept-Language': 'en-US,en;q=0.9',
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        response.raise_for_status()
        data = response.json()
        if data.get("s") == "ok":
            access_token = data.get("d", {}).get("access_token")
            if access_token:
                logger.debug(f"Successfully obtained access token for user: {username}")
                return access_token
            else:
                logger.error(f"Access token not found in the response for user: {username}")
        else:
            logger.error(f"API call failed for user: {username}. Response: {data}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error during API call for user {username}: {e}")
        discord_alert(type=AlertType.Fail, message=f"Error fetching API token for tradovate account: {username}")
    except json.JSONDecodeError:
        logger.error(f"Failed to parse JSON response for user: {username}. Response text: {response.text}")
    
    return None

def update_redis_tokens(redis_client, username, access_token):
    """
    Retrieves the list of keys from the username's list and updates
    each key's value with the new access token string, setting a TTL of 5 hours.
    """
    if not redis_client:
        logger.error("Redis client is not available. Cannot proceed with updates.")
        discord_alert(type=AlertType.Fail, message=f"Redis client is not available. Cannot proceed with updates")
        return

    try:
        keys_to_update = redis_client.lrange(username, 0, -1)
        
        if not keys_to_update:
            logger.error(f"No keys found in Redis for user: {username}. Keys should already exist in the database.")
            discord_alert(type=AlertType.Fail, message=f"No keys found in Redis for user `{username}` - Keys should already exist in the database")
            return
        
        logger.debug(f"Found keys to update for {username}: {keys_to_update}")

        for key in keys_to_update:
            try:
                key_type = redis_client.type(key)
                
                if key_type in ['string', 'none']:
                    redis_client.setex(key, TTL_SECONDS, access_token)
                    redis_client.setex(f"auth:{username}", TTL_SECONDS, access_token)
                    logger.debug(f"Successfully set/updated key '{key}' with token and TTL of {TTL_SECONDS}s.")
                elif key_type == 'hash':
                    redis_client.hset(key, 'access_token', access_token)
                    redis_client.expire(key, TTL_SECONDS)
                    logger.debug(f"Successfully updated hash key '{key}' with token and TTL of {TTL_SECONDS}s.")
                else:
                    logger.warning(f"Key '{key}' has an unsupported data type '{key_type}'. Skipping update.")
            except redis.exceptions.RedisError as e:
                logger.error(f"Redis error while updating key '{key}' for user '{username}': {e}")
                

    except redis.exceptions.RedisError as e:
        logger.error(f"Redis error while processing user key '{username}': {e}")
        discord_alert(type=AlertType.Fail, message=f"Redis error while processing user key `{username}`")

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

def process_account(creds, redis_client):
    """Worker function to process a single account's token refresh."""
    username = creds.get('username')
    password = creds.get('password')
    
    if not username or not password:
        logger.warning(f"Skipping a credentials entry due to missing username or password: {creds}")
        return

    access_token = get_access_token(username, password)
    if access_token:
        update_redis_tokens(redis_client, username, access_token)
    else:
        logger.error(f"Could not get access token for user {username}. Skipping Redis update for this user.")
        discord_alert(type=AlertType.Fail, message=f"Could not get access token for `{username}` - Skipping Redis update for this user")


def token_refresher(credentials_list):
    redis_client = get_redis_client()
    if not redis_client:
        return

    # Use a ThreadPoolExecutor to run tasks in parallel
    # The number of workers should be tuned based on system resources and API rate limits.
    # A value between 5-10 is a good starting point.
    max_workers = 10 
    logger.info(f"Starting token refresh for {len(credentials_list)} accounts using {max_workers} threads.")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_account, creds, redis_client): creds for creds in credentials_list}
        
        for future in as_completed(futures):
            creds = futures[future]
            print(creds)
            try:
                # Retrieve the result to catch any exceptions raised in the thread
                future.result()
            except Exception as exc:
                logger.error(f"An exception occurred while processing account {creds.get('username')}: {exc}")

def main():
    """
    Main function to orchestrate the entire process using a thread pool.
    """
    try:
        with open('credentials.json', 'r') as f:
            credentials_list = json.load(f)
        
    except FileNotFoundError:
        logger.error("The file 'credentials.json' was not found.")
        return
    except json.JSONDecodeError:
        logger.error("Error decoding JSON from 'credentials.json'. Please check the file's format.")
        return

    token_refresher(credentials_list)
    logger.debug("All token refresh tasks have been completed.")
    discord_alert(type=AlertType.Pass, message=f"All token refresh tasks have been completed")


if __name__ == "__main__":
    main()