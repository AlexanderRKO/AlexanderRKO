"""Project-relative paths."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_JSON = REPO_ROOT / "dashboard" / "src" / "data.json"
INBOX = REPO_ROOT / "inbox"
ARCHIVE = REPO_ROOT / "inbox" / "_archive"
TEMPLATE = REPO_ROOT / "inbox" / "_template"

MONTH_DIR_RE = r"^\d{4}-\d{2}$"  # e.g. 2026-04
