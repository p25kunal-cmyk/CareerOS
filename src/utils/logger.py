"""Structured logging for CareerOS.

Provides file and console logging with configurable levels.
Never logs secrets or unnecessary personal information.
"""

import logging
import sys
from pathlib import Path

_initialized = False


def setup_logging(level: str = "INFO", log_file: str = "") -> logging.Logger:
    """Configure application-wide logging.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Path to log file. Empty string = console only.

    Returns:
        Root CareerOS logger.
    """
    global _initialized
    logger = logging.getLogger("careeros")

    if _initialized:
        return logger

    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)

    # Console handler — always INFO+ to keep terminal clean
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(
        "%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
        datefmt="%H:%M:%S",
    ))
    logger.addHandler(console)

    # File handler — full detail
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(str(log_path), encoding="utf-8")
        fh.setLevel(log_level)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s │ %(levelname)-8s │ %(name)s.%(funcName)s:%(lineno)d │ %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        logger.addHandler(fh)

    _initialized = True
    logger.info("CareerOS logging initialized (level=%s)", level)
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the careeros namespace.

    Args:
        name: Module or component name (e.g. 'database', 'resume.parser').
    """
    return logging.getLogger(f"careeros.{name}")
