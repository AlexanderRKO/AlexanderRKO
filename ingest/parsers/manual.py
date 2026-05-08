"""Manual override loader.

Each month folder may contain a `manual.yml` (or `.yaml`) holding values
that can't be parsed automatically (MW reimbursement total, agency rev share,
notes, etc.) or overrides for parsed fields.

The manual file always wins against parsed values — it's the user's source
of truth for reconciliation context.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)


def load_manual(month_dir: Path) -> dict[str, Any]:
    for name in ("manual.yml", "manual.yaml"):
        path = month_dir / name
        if path.exists():
            with path.open() as f:
                data = yaml.safe_load(f) or {}
            log.info("loaded manual overrides from %s", path.name)
            return data
    log.debug("no manual.yml in %s", month_dir)
    return {}
