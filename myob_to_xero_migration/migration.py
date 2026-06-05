#!/usr/bin/env python3
"""migration — convenience CLI for the MYOB → Xero migration toolkit.

Commands:
    status               progress dashboard scanned from INDEX.md and trackers
    init                 fill engagement parameters in INDEX.md and PLAN.md
    validate <csv> <tmpl>  wrap templates/scripts/validate_xero_csv.py
    check                wrap templates/scripts/post_upload_acceptance_check.py

Run from the toolkit root:

    python migration.py status
    python migration.py init --client "Acme Pty Ltd" --conversion-date 2026-07-01
    python migration.py validate 02_cleansed_for_xero/01_chart_of_accounts/xero_chart_of_accounts.csv \\
        templates/xero_csv_templates/xero_chart_of_accounts_template.csv
    python migration.py check --myob 03_finalized_reports/01_pre_conversion_snapshots/tb_myob.csv \\
        --xero 04_xero_post_upload_checks/01_account_by_account_checklists/tb_xero.csv

Exit codes for `check` and `validate` propagate from the underlying
scripts (0 = pass, 1 = fail, 2 = usage error).
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "INDEX.md"
PLAN = ROOT / "PLAN.md"
SCRIPTS = ROOT / "templates" / "scripts"

STATUS_SYMBOLS = {"todo": "⬜", "wip": "🟡", "done": "🟢", "exception": "⚠"}
STATUS_ORDER = ("done", "wip", "exception", "todo")

# ANSI colours, disabled when output isn't a tty.
USE_COLOUR = sys.stdout.isatty()


def c(code: str, text: str) -> str:
    if not USE_COLOUR:
        return text
    return f"\033[{code}m{text}\033[0m"


GREEN = lambda s: c("32", s)
YELLOW = lambda s: c("33", s)
RED = lambda s: c("31", s)
CYAN = lambda s: c("36", s)
BOLD = lambda s: c("1", s)
DIM = lambda s: c("2", s)


# --------------------------------------------------------------------------- #
# status                                                                      #
# --------------------------------------------------------------------------- #


@dataclass
class StageStats:
    name: str
    counts: Counter

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    @property
    def done(self) -> int:
        return self.counts.get("done", 0)

    @property
    def pct(self) -> float:
        return 100.0 * self.done / self.total if self.total else 0.0


STAGE_HEADER_RE = re.compile(r"^## (0[1-4]) — (.+?)\s*$")


def parse_index(text: str) -> list[StageStats]:
    stages: list[StageStats] = []
    current_name: str | None = None
    current_counts: Counter = Counter()

    for line in text.splitlines():
        m = STAGE_HEADER_RE.match(line)
        if m:
            if current_name is not None:
                stages.append(StageStats(current_name, current_counts))
            current_name = f"{m.group(1)} {m.group(2)}"
            current_counts = Counter()
            continue
        if current_name is None or not line.startswith("|"):
            continue
        # Skip header / separator rows.
        if "---" in line or re.search(r"\|\s*#\s*\|", line):
            continue
        for key, sym in STATUS_SYMBOLS.items():
            if sym in line:
                current_counts[key] += 1
                break

    if current_name is not None:
        stages.append(StageStats(current_name, current_counts))
    return stages


def progress_bar(pct: float, width: int = 24) -> str:
    filled = int(round(width * pct / 100))
    bar = "█" * filled + "░" * (width - filled)
    if pct >= 100:
        return GREEN(bar)
    if pct >= 50:
        return YELLOW(bar)
    return RED(bar) if pct > 0 else DIM(bar)


def _read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def cmd_status(_args: argparse.Namespace) -> int:
    if not INDEX.exists():
        print(RED("ERROR"), f"INDEX.md not found at {INDEX}", file=sys.stderr)
        return 2

    stages = parse_index(INDEX.read_text(encoding="utf-8"))

    # Header.
    print()
    print(BOLD(CYAN("MYOB → Xero migration status")))
    print(CYAN("=" * 44))

    # Client header line — best effort, pull a few key fields.
    text = INDEX.read_text(encoding="utf-8")
    for label in ("Client / entity", "Conversion date", "Xero org target"):
        m = re.search(rf"\|\s*{re.escape(label)}\s*\|\s*([^|]+?)\s*\|", text)
        if m:
            value = m.group(1).strip()
            print(f"  {DIM(label + ':'):<32} {value}")
    print()

    # Per-stage progress.
    for stage in stages:
        bar = progress_bar(stage.pct)
        ratio = f"{stage.done}/{stage.total}" if stage.total else "0/0"
        # Trim parentheticals so all stage labels share the same width.
        short = re.sub(r"\s*\(.*\)\s*$", "", stage.name)
        print(f"  Stage {short:<38} {bar} {ratio:>7}  ({stage.pct:5.1f}%)")
    print()

    # Exception / clearing-account / acceptance-gate summary.
    exc = _read_csv_rows(
        ROOT / "04_xero_post_upload_checks/05_exception_log/exceptions.csv"
    )
    open_exc = [r for r in exc if not r.get("resolved_date")]
    clearing = _read_csv_rows(
        ROOT / "04_xero_post_upload_checks/03_balance_reconciliations/clearing_accounts_tracker.csv"
    )
    clearing_done = [r for r in clearing if (r.get("status") or "").strip() in {"🟢", "done"}]
    tb_diff = _read_csv_rows(
        ROOT / "04_xero_post_upload_checks/01_account_by_account_checklists/trial_balance_diff.csv"
    )
    if tb_diff:
        fails = [r for r in tb_diff if (r.get("status") or "").strip() == "FAIL"]
        gate = GREEN("PASS") if not fails else RED(f"FAIL ({len(fails)} breaches)")
    else:
        gate = DIM("not yet run")

    print(BOLD("  Roll-up"))
    print(f"    open exceptions     : {RED(str(len(open_exc))) if open_exc else GREEN('0')}")
    print(
        f"    clearing accts NIL  : {len(clearing_done)}/{len(clearing)}"
        if clearing
        else "    clearing accts NIL  : —"
    )
    print(f"    acceptance gate     : {gate}")
    print()

    # Next-action hint per stage.
    print(BOLD("  Next actions"))
    any_hint = False
    for stage in stages:
        todo = stage.counts.get("todo", 0)
        wip = stage.counts.get("wip", 0)
        if todo or wip:
            any_hint = True
            print(
                f"    • Stage {stage.name.split()[0]}: {wip} in progress, {todo} to start"
            )
    if not any_hint:
        print(f"    {GREEN('• all stages complete — proceed to sign-off')}")
    print()

    return 0


# --------------------------------------------------------------------------- #
# init                                                                        #
# --------------------------------------------------------------------------- #


# Fields we know how to fill via --flags; everything else stays _TBD_.
INIT_FIELDS = {
    "client": ("Client / entity", "Client / entity name"),
    "abn": ("ABN", "ABN"),
    "conversion_date": ("Conversion date", "Conversion date (first day reported in Xero)"),
    "myob_product": (None, "MYOB product (AccountRight Live / Essentials / Business)"),
    "xero_plan": (None, "Xero plan target (Starter / Standard / Premium / Ultimate)"),
    "xero_org_target": ("Xero org target", None),
    "gst": (None, "GST registered (Y/N) and reporting cycle"),
    "payroll": (None, "Payroll in scope (Y/N), STP phase"),
    "inventory": (None, "Inventory tracked (Y/N)"),
    "lead": ("Lead accountant", None),
}


def _replace_table_value(text: str, label: str, value: str) -> str:
    """Replace the second column of a Markdown table row whose first cell == label."""
    pattern = re.compile(
        rf"(\|\s*{re.escape(label)}\s*\|\s*)([^|]+?)(\s*\|)"
    )
    return pattern.sub(rf"\g<1>{value}\3", text, count=1)


def cmd_init(args: argparse.Namespace) -> int:
    if not INDEX.exists() or not PLAN.exists():
        print(RED("ERROR"), "INDEX.md or PLAN.md missing — run from toolkit root.", file=sys.stderr)
        return 2

    index_text = INDEX.read_text(encoding="utf-8")
    plan_text = PLAN.read_text(encoding="utf-8")

    updates: list[tuple[str, str]] = []
    for field, (index_label, plan_label) in INIT_FIELDS.items():
        value = getattr(args, field, None)
        if not value:
            continue
        if index_label:
            new = _replace_table_value(index_text, index_label, value)
            if new != index_text:
                updates.append((f"INDEX.md / {index_label}", value))
                index_text = new
        if plan_label:
            new = _replace_table_value(plan_text, plan_label, value)
            if new != plan_text:
                updates.append((f"PLAN.md / {plan_label}", value))
                plan_text = new

    if not updates:
        print(YELLOW("nothing to update — pass --client / --conversion-date / etc."))
        return 1

    if args.dry_run:
        print(BOLD("dry-run — would update:"))
        for where, value in updates:
            print(f"  {where:<55} → {value}")
        return 0

    INDEX.write_text(index_text, encoding="utf-8")
    PLAN.write_text(plan_text, encoding="utf-8")

    print(BOLD(GREEN("updated:")))
    for where, value in updates:
        print(f"  {where:<55} → {value}")
    print()
    print("Next: run", CYAN("python migration.py status"))
    return 0


# --------------------------------------------------------------------------- #
# validate / check — thin wrappers around the existing scripts                #
# --------------------------------------------------------------------------- #


def cmd_validate(args: argparse.Namespace) -> int:
    return subprocess.call(
        [sys.executable, str(SCRIPTS / "validate_xero_csv.py"), args.csv, args.template]
    )


def cmd_check(args: argparse.Namespace) -> int:
    cmd = [
        sys.executable,
        str(SCRIPTS / "post_upload_acceptance_check.py"),
        "--myob",
        args.myob,
        "--xero",
        args.xero,
        "--out",
        args.out
        or str(ROOT / "04_xero_post_upload_checks" / "01_account_by_account_checklists"),
        "--tolerance",
        str(args.tolerance),
    ]
    return subprocess.call(cmd)


# --------------------------------------------------------------------------- #
# entry point                                                                 #
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="migration", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="progress dashboard").set_defaults(func=cmd_status)

    init = sub.add_parser("init", help="fill engagement parameters")
    init.add_argument("--client")
    init.add_argument("--abn")
    init.add_argument("--conversion-date", dest="conversion_date")
    init.add_argument("--myob-product", dest="myob_product")
    init.add_argument("--xero-plan", dest="xero_plan")
    init.add_argument("--xero-org-target", dest="xero_org_target", choices=["new", "existing"])
    init.add_argument("--gst")
    init.add_argument("--payroll")
    init.add_argument("--inventory")
    init.add_argument("--lead")
    init.add_argument("--dry-run", action="store_true")
    init.set_defaults(func=cmd_init)

    val = sub.add_parser("validate", help="validate a cleansed CSV against a Xero template")
    val.add_argument("csv")
    val.add_argument("template")
    val.set_defaults(func=cmd_validate)

    chk = sub.add_parser("check", help="run the Stage-04 trial-balance acceptance gate")
    chk.add_argument("--myob", required=True)
    chk.add_argument("--xero", required=True)
    chk.add_argument("--out")
    chk.add_argument("--tolerance", default="1.00")
    chk.set_defaults(func=cmd_check)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        # Output was truncated by a downstream pipe (head, less). Exit cleanly.
        try:
            sys.stdout.close()
        except BrokenPipeError:
            pass
        sys.exit(0)
