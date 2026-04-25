import sys
from pathlib import Path

from loguru import logger

from config.settings import settings


def setup_logger():
    logger.remove()

    # Console output
    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:<8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    )

    # File output
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(exist_ok=True)

    logger.add(
        log_dir / "trader_{time:YYYY-MM-DD}.log",
        level=settings.LOG_LEVEL,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{function} - {message}",
        rotation="1 day",
        retention="30 days",
    )

    return logger


setup_logger()
