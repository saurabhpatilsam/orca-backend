import os
import sys
from loguru import logger
from dotenv import load_dotenv

load_dotenv()
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logger.remove()
logger.add(sys.stderr, level=log_level)
