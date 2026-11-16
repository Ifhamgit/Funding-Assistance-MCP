"""Application logging (R-24): stderr and optional file, never stdout (stdout is the MCP channel)."""

import logging
import os
import sys


def configure_logging() -> None:
    level = os.environ.get("FUNDING_LOG_LEVEL", "INFO").upper()
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    log_file = os.environ.get("FUNDING_LOG_FILE", "").strip()
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    root = logging.getLogger("funding_mcp")
    root.handlers.clear()
    for handler in handlers:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False
