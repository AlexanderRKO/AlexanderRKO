"""High-level ingest entry points used by both the CLI and watcher."""
from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path

from .data_writer import load_data, save_data, upsert_month
from .month_builder import build_month
from .paths import ARCHIVE, INBOX, MONTH_DIR_RE

log = logging.getLogger(__name__)


def ingest_month(month_dir: Path, dry_run: bool = False) -> bool:
    """Parse a single YYYY-MM folder and merge it into data.json."""
    month_dir = month_dir.resolve()
    if not month_dir.exists():
        log.error("not found: %s", month_dir)
        return False

    log.info("ingesting %s", month_dir)
    result, errors = build_month(month_dir)
    if result is None:
        for e in errors:
            log.error(e)
        return False

    if errors:
        log.warning("validation issues for %s:", month_dir.name)
        for e in errors:
            log.warning("  - %s", e)

    if dry_run:
        import json
        print(json.dumps(result, indent=2, default=str))
        return not errors

    data = load_data()
    upsert_month(data, result["month"], result["mwOffices"])
    save_data(data)
    log.info("[OK] %s ingested into data.json", result["month"]["month"])
    return not errors


def ingest_all(inbox: Path, dry_run: bool = False) -> bool:
    """Ingest every YYYY-MM folder under inbox/, in chronological order."""
    inbox = inbox.resolve()
    if not inbox.exists():
        log.error("inbox not found: %s", inbox)
        return False

    month_dirs = sorted(
        d for d in inbox.iterdir()
        if d.is_dir() and re.match(MONTH_DIR_RE, d.name)
    )
    if not month_dirs:
        log.info("no YYYY-MM folders under %s", inbox)
        return True

    all_ok = True
    for d in month_dirs:
        if not ingest_month(d, dry_run=dry_run):
            all_ok = False
    return all_ok


def archive_month(month_dir: Path) -> None:
    """Move a successfully-processed month folder into inbox/_archive/."""
    if month_dir.parent.resolve() != INBOX.resolve():
        return  # only archive folders directly under inbox/
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    target = ARCHIVE / month_dir.name
    if target.exists():
        # Avoid clobbering — append a numeric suffix.
        i = 2
        while (ARCHIVE / f"{month_dir.name}_v{i}").exists():
            i += 1
        target = ARCHIVE / f"{month_dir.name}_v{i}"
    shutil.move(str(month_dir), str(target))
    log.info("archived %s -> %s", month_dir.name, target)
