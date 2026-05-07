import logging
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app_log import setup_logging, log_dir


@pytest.fixture(autouse=True)
def clean_root_logger():
    """Reset the root logger between tests to keep them isolated."""
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    saved_flag = getattr(root, "_iem_configured", False)
    root.handlers = []
    if hasattr(root, "_iem_configured"):
        del root._iem_configured
    yield
    for h in list(root.handlers):
        h.close()
        root.removeHandler(h)
    if hasattr(root, "_iem_configured"):
        del root._iem_configured
    root.handlers = saved_handlers
    root.setLevel(saved_level)
    if saved_flag:
        root._iem_configured = saved_flag


def test_log_dir_returns_path():
    p = log_dir()
    assert isinstance(p, Path)


def test_setup_logging_creates_file_and_writes():
    with tempfile.TemporaryDirectory() as tmp:
        with patch("app_log.log_dir", return_value=Path(tmp)):
            setup_logging()
            log = logging.getLogger("test_module")
            log.info("hello world")

            for h in logging.getLogger().handlers:
                h.flush()

            log_file = Path(tmp) / "app.log"
            assert log_file.exists()
            content = log_file.read_text()
            assert "hello world" in content


def test_setup_logging_idempotent():
    with tempfile.TemporaryDirectory() as tmp:
        with patch("app_log.log_dir", return_value=Path(tmp)):
            setup_logging()
            count_after_first = len(logging.getLogger().handlers)
            setup_logging()
            count_after_second = len(logging.getLogger().handlers)
            assert count_after_first >= 2  # RotatingFileHandler + StreamHandler
            assert count_after_first == count_after_second
