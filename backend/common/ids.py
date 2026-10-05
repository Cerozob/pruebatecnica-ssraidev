"""Identificadores y marcas de tiempo."""

import uuid
from datetime import UTC, datetime


def new_id() -> str:
    """UUIDv7: ordenable por fecha de creación (ADR-042)."""
    return str(uuid.uuid7())


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
