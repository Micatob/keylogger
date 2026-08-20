import os
import sys
import logging

_LOG_DIR = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "keylogger_logs")
_LOG_FILE = os.path.join(_LOG_DIR, "debug.log")

_logger = None


def get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    _logger = logging.getLogger("keylogger")
    _logger.setLevel(logging.DEBUG)

    if not _logger.handlers:
        try:
            os.makedirs(_LOG_DIR, exist_ok=True)
            fh = logging.FileHandler(_LOG_FILE, mode="a", encoding="utf-8")
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            _logger.addHandler(fh)
        except Exception:
            pass

    return _logger


def log(level: str, msg: str, *args):
    logger = get_logger()
    if level == "debug":
        logger.debug(msg, *args)
    elif level == "info":
        logger.info(msg, *args)
    elif level == "warning":
        logger.warning(msg, *args)
    elif level == "error":
        logger.error(msg, *args)
