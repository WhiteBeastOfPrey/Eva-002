import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import LOGS_DIR


def init_logging(name: str = "eva_assistant", level: int = logging.INFO) -> logging.Logger:
	LOGS_DIR.mkdir(parents=True, exist_ok=True)
	logger = logging.getLogger(name)
	logger.setLevel(level)

	if not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
		log_path = LOGS_DIR / f"{name}.log"
		file_handler = RotatingFileHandler(str(log_path), maxBytes=2_000_000, backupCount=3, encoding="utf-8")
		file_handler.setFormatter(logging.Formatter(
			"%(asctime)s | %(levelname)s | %(name)s | %(message)s"
		))
		logger.addHandler(file_handler)

	if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler) for h in logger.handlers):
		console = logging.StreamHandler()
		console.setFormatter(logging.Formatter("%(levelname)s | %(message)s"))
		logger.addHandler(console)

	return logger