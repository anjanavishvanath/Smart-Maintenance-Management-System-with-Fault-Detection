"""Centralised logging configuration for the PreSense backend.

Both the Flask API and the standalone MQTT ingestor call `configure_logging()`
exactly once on import. We log to stdout so docker / journald / k8s capture it,
with ISO timestamps and the originating module name.

The level is read from the LOG_LEVEL env var (default INFO). Set LOG_LEVEL=DEBUG
in development for verbose output.
"""
from __future__ import annotations

import logging
import os
import sys

_CONFIGURED = False


def configure_logging() -> None:
    """Idempotent root-logger setup. Safe to call multiple times."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    ))

    root = logging.getLogger()
    # Replace any pre-existing handlers (e.g. flask's default) so we get a
    # single, consistent format across both processes.
    root.handlers = [handler]
    root.setLevel(level)

    # Tame the chattier libraries.
    logging.getLogger("paho").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    _CONFIGURED = True
