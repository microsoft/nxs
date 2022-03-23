import logging
from enum import Enum


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
