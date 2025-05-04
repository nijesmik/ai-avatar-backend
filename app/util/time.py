import logging
from time import time

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def log_time(start_time: float, name: str):
    if start_time:
        logger.debug(f"⏰ {name} time: {(time() - start_time) * 1000:.2f}ms")
