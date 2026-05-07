import logging
import os
import platform
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


APP_NAME = "SennheiserIEMControl"

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_MAX_BYTES = 5_000_000
_BACKUP_COUNT = 2


def log_dir() -> Path:
    """Return platform-appropriate log directory."""
    home = Path.home()
    system = platform.system()
    if system == "Darwin":
        return home / "Library" / "Logs" / APP_NAME
    if system == "Windows":
        base = os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local"))
        return Path(base) / APP_NAME / "Logs"
    return home / ".local" / "share" / APP_NAME


def setup_logging(level: int = logging.INFO):
    """Configure root logger with RotatingFileHandler + stderr handler.

    Idempotent: calling multiple times does not duplicate handlers.
    """
    root = logging.getLogger()
    if getattr(root, "_iem_configured", False):
        return

    directory = log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    log_file = directory / "app.log"

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(logging.Formatter(_LOG_FORMAT))

    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)
    root._iem_configured = True


def collected_log_paths() -> list[Path]:
    """Return existing log files (current + rotated) in order, newest first."""
    directory = log_dir()
    paths = []
    main = directory / "app.log"
    if main.exists():
        paths.append(main)
    for i in range(1, _BACKUP_COUNT + 1):
        p = directory / f"app.log.{i}"
        if p.exists():
            paths.append(p)
    return paths
