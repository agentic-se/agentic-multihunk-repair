"""
Small host-side helpers used by the docker-isolated runner.
"""

from datetime import datetime
from pathlib import Path


def ts() -> str:
    """Timestamp suitable for filenames."""
    return datetime.now().strftime("%Y-%m-%d-%H%M%S")


def ensure_dir(p: Path) -> Path:
    """Create the directory if missing; return it."""
    p.mkdir(parents=True, exist_ok=True)
    return p
