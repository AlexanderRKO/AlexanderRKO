"""Folder watcher daemon.

Watches inbox/ for any change inside a YYYY-MM subfolder. After a quiet
period (debounce), it re-ingests that folder. The debounce avoids partial
ingests while you're still copying files in.

Run with:
    python -m ingest watch
"""
from __future__ import annotations

import logging
import re
import threading
import time
from pathlib import Path

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError as exc:
    raise SystemExit(
        "The watcher needs the 'watchdog' package: pip install watchdog"
    ) from exc

from .ingest import ingest_month
from .paths import INBOX, MONTH_DIR_RE

log = logging.getLogger(__name__)
DEBOUNCE_SECONDS = 5.0


class _MonthHandler(FileSystemEventHandler):
    def __init__(self, inbox: Path):
        self.inbox = inbox.resolve()
        self._timers: dict[Path, threading.Timer] = {}
        self._lock = threading.Lock()

    def _month_dir_for(self, event_path: str) -> Path | None:
        path = Path(event_path).resolve()
        try:
            rel = path.relative_to(self.inbox)
        except ValueError:
            return None
        if not rel.parts:
            return None
        first = rel.parts[0]
        if not re.match(MONTH_DIR_RE, first):
            return None
        return self.inbox / first

    def _schedule(self, month_dir: Path) -> None:
        with self._lock:
            if month_dir in self._timers:
                self._timers[month_dir].cancel()
            t = threading.Timer(DEBOUNCE_SECONDS, self._run, args=(month_dir,))
            t.daemon = True
            self._timers[month_dir] = t
            t.start()
            log.debug("scheduled re-ingest for %s in %.0fs", month_dir.name, DEBOUNCE_SECONDS)

    def _run(self, month_dir: Path) -> None:
        with self._lock:
            self._timers.pop(month_dir, None)
        if not month_dir.exists():
            return
        log.info("change settled in %s — ingesting", month_dir.name)
        try:
            ingest_month(month_dir)
        except Exception:
            log.exception("ingest failed for %s", month_dir.name)

    def on_any_event(self, event):
        if event.is_directory and event.event_type == "created":
            return
        md = self._month_dir_for(event.src_path)
        if md is not None:
            self._schedule(md)


def watch(inbox: Path = INBOX) -> None:
    inbox = inbox.resolve()
    inbox.mkdir(parents=True, exist_ok=True)
    handler = _MonthHandler(inbox)
    obs = Observer()
    obs.schedule(handler, str(inbox), recursive=True)
    obs.start()
    log.info("watching %s (Ctrl+C to stop)", inbox)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("stopping watcher...")
    finally:
        obs.stop()
        obs.join()
