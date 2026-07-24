"""Stage-04 acceptance gate.

Diffs a Trial Balance exported from Xero against the locked MYOB Trial
Balance saved in `03_finalized_reports/01_pre_conversion_snapshots/`.

Inputs are two CSVs with at least these columns (case-insensitive):

    account_code, account_name, debit, credit

The script:
- Aligns on `account_code` (falling back to `account_name` when a code
  is missing on one side).
- Computes per-account variance = (xero_debit - xero_credit) -
  (myob_debit - myob_credit).
- Flags any variance whose absolute value exceeds `--tolerance`
  (default A$1.00).
- Writes a `trial_balance_diff.csv` to the target directory and prints
  a one-line summary.

Exit codes:
    0  → all variances within tolerance (gate PASS)
    1  → at least one variance breaches tolerance (gate FAIL)
    2  → CLI / file error

Usage:
    python post_upload_acceptance_check.py \
        --myob path/to/myob_tb.csv \
        --xero path/to/xero_tb.csv \
        --out  04_xero_post_upload_checks/01_account_by_account_checklists \
        --tolerance 1.00
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path


REQUIRED = ("account_code", "account_name", "debit", "credit")


def _read_tb(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        header = {h.lower().strip(): h for h in (reader.fieldnames or [])}
        missing = [c for c in REQUIRED if c not in header]
        if missing:
            raise ValueError(f"{path}: missing columns {missing}")
        for row in reader:
            code = (row[header["account_code"]] or "").strip()
            name = (row[header["account_name"]] or "").strip()
            key = code or f"name::{name.lower()}"
            debit = _to_decimal(row[header["debit"]])
            credit = _to_decimal(row[header["credit"]])
            rows[key] = {
                "account_code": code,
                "account_name": name,
                "debit": debit,
                "credit": credit,
                "net": debit - credit,
            }
    return rows


def _to_decimal(value: str) -> Decimal:
    if value is None:
        return Decimal("0")
    cleaned = value.replace(",", "").replace("$", "").strip()
    if not cleaned or cleaned in {"-", "—"}:
        return Decimal("0")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return Decimal("0")


def diff(myob: dict[str, dict], xero: dict[str, dict]) -> list[dict]:
    keys = sorted(set(myob) | set(xero))
    out: list[dict] = []
    for key in keys:
        m = myob.get(key)
        x = xero.get(key)
        out.append(
            {
                "account_code": (m or x)["account_code"],
                "account_name": (m or x)["account_name"],
                "myob_net": m["net"] if m else Decimal("0"),
                "xero_net": x["net"] if x else Decimal("0"),
                "variance": (x["net"] if x else Decimal("0"))
                - (m["net"] if m else Decimal("0")),
                "presence": "both"
                if m and x
                else ("myob_only" if m else "xero_only"),
            }
        )
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--myob", type=Path, required=True)
    p.add_argument("--xero", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--tolerance", type=Decimal, default=Decimal("1.00"))
    args = p.parse_args(argv)

    try:
        myob = _read_tb(args.myob)
        xero = _read_tb(args.xero)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    rows = diff(myob, xero)
    args.out.mkdir(parents=True, exist_ok=True)
    out_path = args.out / "trial_balance_diff.csv"
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "account_code",
                "account_name",
                "myob_net",
                "xero_net",
                "variance",
                "presence",
                "status",
                "notes",
            ]
        )
        breaches = 0
        totals = defaultdict(Decimal)
        for r in rows:
            within = abs(r["variance"]) <= args.tolerance
            status = "PASS" if within else "FAIL"
            if not within:
                breaches += 1
            totals[r["presence"]] += abs(r["variance"])
            writer.writerow(
                [
                    r["account_code"],
                    r["account_name"],
                    f"{r['myob_net']:.2f}",
                    f"{r['xero_net']:.2f}",
                    f"{r['variance']:.2f}",
                    r["presence"],
                    status,
                    "",
                ]
            )

    print(f"diff written : {out_path}")
    print(f"accounts     : {len(rows)}")
    print(f"breaches > tolerance ({args.tolerance}): {breaches}")
    if breaches:
        print("RESULT       : FAIL — investigate and resolve before sign-off.")
        return 1
    print("RESULT       : PASS — Stage-04 acceptance gate cleared.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
