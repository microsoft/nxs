import logging
from enum import Enum

from configs import NXS_CONFIG


class NxsLogLevel(str, Enum):
    NOTSET = ("NOTSET",)
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


NxsLogLevel2LoggingLevelMap = {
    NxsLogLevel.NOTSET: logging.NOTSET,
    NxsLogLevel.DEBUG: logging.DEBUG,
    NxsLogLevel.INFO: logging.INFO,
    NxsLogLevel.WARNING: logging.WARNING,
    NxsLogLevel.CRITICAL: logging.CRITICAL,
}


def write_log(prefix: str, log: str, level: NxsLogLevel = NxsLogLevel.INFO):
    logging_level = NxsLogLevel2LoggingLevelMap.get(level, logging.INFO)
    logging.log(logging_level, f"{prefix} - {log}")


def setup_logger():
    import os
    import sys

    log_level = NxsLogLevel(
        os.environ.get(NXS_CONFIG.LOG_LEVEL, NxsLogLevel.INFO.value)
    )
    logging.getLogger().setLevel(
        NxsLogLevel2LoggingLevelMap.get(log_level, logging.INFO)
    )
    log_formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)-8s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    screen_handler = logging.StreamHandler(stream=sys.stdout)
    screen_handler.setFormatter(log_formatter)
    for handler in logging.getLogger().handlers:
        logging.getLogger().removeHandler(handler)
    logging.getLogger().addHandler(screen_handler)
