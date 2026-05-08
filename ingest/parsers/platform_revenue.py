"""Parse Platform Revenue CSV.

The CSV from the Managed admin portal has different exact column headers
across exports, so this parser is fuzzy: it locates the four revenue lines
plus SMS and Implementation Fees by keyword match, then reads billed /
completed / debtors columns.

Per DASHBOARD_INSTRUCTIONS.md §6:
    Base Subscription Revenue   -> baseSub
    Managed+ Revenue            -> managedPlus
    Transaction Cost Revenue    -> transaction
    Tradie Job Revenue          -> tradie
    SMS Revenue                 -> smsRevenue (single number)
    Implementation Fees         -> implFees (single number)

Expected CSV columns (case-insensitive substring match):
    line / item / description       -> revenue line label
    billed / total / amount         -> billed
    completed / paid / collected    -> completed
    debtors / outstanding / unpaid  -> debtors
"""
from __future__ import annotations

import csv
import logging
import re
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

LINE_PATTERNS = {
    "baseSub":     [r"\bbase\s*sub", r"managed\s*core"],
    "managedPlus": [r"managed\s*\+", r"managed\s*plus", r"managed\s*pro"],
    "transaction": [r"transaction"],
    "tradie":      [r"tradie"],
}
SMS_PATTERN  = re.compile(r"\bsms\b", re.I)
IMPL_PATTERN = re.compile(r"implementation", re.I)


def _to_float(s: str) -> float:
    s = (s or "").strip().replace("$", "").replace(",", "").replace("(", "-").replace(")", "")
    if not s or s in {"-", "—"}:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _detect_columns(headers: list[str]) -> dict[str, int]:
    cols: dict[str, int] = {}
    for i, h in enumerate(headers):
        low = (h or "").lower()
        if "label" not in cols and re.search(r"line|item|descript|category|revenue", low):
            cols["label"] = i
        if "billed" not in cols and re.search(r"billed|total|amount\b", low):
            cols["billed"] = i
        if "completed" not in cols and re.search(r"complet|paid|collect", low):
            cols["completed"] = i
        if "debtors" not in cols and re.search(r"debtor|outstand|unpaid", low):
            cols["debtors"] = i
    return cols


def _match_line(label: str) -> str | None:
    low = label.lower()
    for key, patterns in LINE_PATTERNS.items():
        if any(re.search(p, low) for p in patterns):
            return key
    return None


def parse_platform_revenue(csv_path: Path) -> dict[str, Any]:
    if not csv_path.exists():
        return {}

    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = [row for row in reader if any(cell.strip() for cell in row)]

    if not rows:
        return {}

    headers = rows[0]
    cols = _detect_columns(headers)
    if "label" not in cols or "billed" not in cols:
        log.warning("Platform CSV: couldn't identify label/billed columns from %s", headers)
        return {}

    out: dict[str, Any] = {"revenue": {}}
    for row in rows[1:]:
        if cols["label"] >= len(row):
            continue
        label = row[cols["label"]]
        billed_str = row[cols["billed"]] if cols["billed"] < len(row) else ""

        if SMS_PATTERN.search(label):
            out["smsRevenue"] = _to_float(billed_str)
            continue
        if IMPL_PATTERN.search(label):
            out["implFees"] = _to_float(billed_str)
            continue

        key = _match_line(label)
        if key:
            out["revenue"][key] = {
                "billed":    _to_float(billed_str),
                "completed": _to_float(row[cols["completed"]]) if cols.get("completed", -1) < len(row) and "completed" in cols else 0.0,
                "debtors":   _to_float(row[cols["debtors"]])   if cols.get("debtors", -1)   < len(row) and "debtors"   in cols else 0.0,
            }

    log.info("Platform CSV parsed: %d revenue lines, sms=%s, impl=%s",
             len(out["revenue"]), out.get("smsRevenue", "—"), out.get("implFees", "—"))
    return out
