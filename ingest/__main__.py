"""CLI entry point: `python -m ingest <command>`."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .ingest import ingest_month, ingest_all
from .watcher import watch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m ingest",
        description="Ingest monthly reports into the revenue dashboard.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ingest = sub.add_parser("ingest", help="Parse one month folder into data.json")
    p_ingest.add_argument("month_dir", type=Path, help="Path to inbox/YYYY-MM directory")
    p_ingest.add_argument("--dry-run", action="store_true", help="Parse and print, don't write")

    p_all = sub.add_parser("all", help="Ingest every YYYY-MM folder under inbox/")
    p_all.add_argument("--inbox", type=Path, default=Path("inbox"))
    p_all.add_argument("--dry-run", action="store_true")

    p_watch = sub.add_parser("watch", help="Run the folder watcher daemon")
    p_watch.add_argument("--inbox", type=Path, default=Path("inbox"))

    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.cmd == "ingest":
        return 0 if ingest_month(args.month_dir, dry_run=args.dry_run) else 1
    if args.cmd == "all":
        return 0 if ingest_all(args.inbox, dry_run=args.dry_run) else 1
    if args.cmd == "watch":
        watch(args.inbox)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
