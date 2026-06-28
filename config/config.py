"""
config.py
---------
Loads settings.json, resolves all paths relative to the project root,
ensures required directories exist, and configures application-wide logging.

This is the single source of truth for configuration. Every other module
imports `CONFIG` (a dict) and `PROJECT_ROOT` (a Path) from here.
"""

import json
import logging
import logging.handlers
from pathlib import Path

# Project root = parent of the config/ folder
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = Path(__file__).resolve().parent / "settings.json"


def load_settings(path: Path = SETTINGS_PATH) -> dict:
    """Load settings.json into a plain dict. Raises a clear error if missing/invalid."""
    if not path.exists():
        raise FileNotFoundError(
            f"settings.json not found at {path}. "
            f"Copy config/settings.json.example or restore the original file."
        )
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"settings.json is not valid JSON: {e}") from e


CONFIG = load_settings()


def resolve_path(relative_path: str) -> Path:
    """Resolve a path from settings.json relative to the project root."""
    p = Path(relative_path)
    if p.is_absolute():
        return p
    return PROJECT_ROOT / p


def ensure_directories() -> None:
    """Create all directories referenced in settings.json if they don't exist."""
    paths_cfg = CONFIG.get("paths", {})
    dirs = [
        resolve_path(paths_cfg.get("data_dir", "data")) / "crypto",
        resolve_path(paths_cfg.get("data_dir", "data")) / "india",
        resolve_path(paths_cfg.get("logs_dir", "logs")),
        resolve_path(paths_cfg.get("reports_dir", "reports")),
        resolve_path(paths_cfg.get("exports_dir", "exports")),
        resolve_path(CONFIG.get("database", {}).get("path", "database/trades.db")).parent,
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def setup_logging(name: str = "rsi_divergence") -> logging.Logger:
    """
    Configure and return a logger that writes to both console and a
    rotating log file (logs/system.log by default).
    """
    ensure_directories()
    log_cfg = CONFIG.get("logging", {})
    log_file = resolve_path(log_cfg.get("file", "logs/system.log"))
    level_name = log_cfg.get("level", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    max_bytes = int(log_cfg.get("max_bytes", 5 * 1024 * 1024))
    backup_count = int(log_cfg.get("backup_count", 5))

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers if setup_logging() is called more than once
    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


# Resolve commonly used paths up front so other modules can just import them
DATA_DIR = resolve_path(CONFIG["paths"]["data_dir"])
LOGS_DIR = resolve_path(CONFIG["paths"]["logs_dir"])
REPORTS_DIR = resolve_path(CONFIG["paths"]["reports_dir"])
EXPORTS_DIR = resolve_path(CONFIG["paths"]["exports_dir"])
DB_PATH = resolve_path(CONFIG["database"]["path"])

ensure_directories()
