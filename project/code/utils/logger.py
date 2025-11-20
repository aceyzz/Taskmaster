import logging
import os
from datetime import datetime

logger = logging.getLogger("taskmaster")


def _get_logs_dir():
    """Return the absolute path to the project's logs/ directory."""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(project_root, "logs")


def _make_log_filename():
    """Generate a timestamped log filename like: logs/taskmaster_YYYY-MM-DD_HH-MM-SS.log"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return os.path.join(_get_logs_dir(), f"taskmaster_{timestamp}.log")


def init_logger(default_level: str = "INFO"):
    """
    Configure the global logger safely:
      - one file handler (DEBUG+)
      - one console handler (WARNING+ only)
      - prevents propagation to root
    """
    if getattr(logger, "_is_configured", False):
        return

    # Clean previous handlers
    for h in logging.root.handlers[:]:
        logging.root.removeHandler(h)
    for h in logger.handlers[:]:
        logger.removeHandler(h)

    # Set log level
    try:
        numeric_level = getattr(logging, default_level.upper())
    except Exception:
        numeric_level = logging.INFO

    logger.setLevel(numeric_level)
    logger.propagate = False

    # Configure file handler
    logs_dir = _get_logs_dir()
    os.makedirs(logs_dir, exist_ok=True)
    log_filename = _make_log_filename()

    file_handler = logging.FileHandler(log_filename, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)

    # Configure console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_formatter = logging.Formatter("\n%(levelname)s - %(message)s")
    console_handler.setFormatter(console_formatter)

    # Attach handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger._is_configured = True
    logger.info("Logger initialized. Log file: %s", log_filename)


# Initialize once on import
init_logger()