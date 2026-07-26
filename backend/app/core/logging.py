import logging
from logging.handlers import RotatingFileHandler

from app.core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.api_log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    updater_logger = logging.getLogger("oihk.updater")
    if any(getattr(handler, "_oihk_updater", False) for handler in updater_logger.handlers):
        return
    log_directory = settings._default_data_dir() / "logs"
    log_directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_directory / "updater.log",
        maxBytes=1_048_576,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    handler._oihk_updater = True  # type: ignore[attr-defined]
    updater_logger.addHandler(handler)
    updater_logger.setLevel(logging.INFO)
    updater_logger.propagate = False
