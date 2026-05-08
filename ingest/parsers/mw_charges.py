"""Parse Marshall White platform charges CSV.

Extracts the per-office breakdown for the MW_OFFICES entry. Each row maps to:
    office:        agency name (Armadale, Hawthorn, ...)
    invoiceNo:     platform invoice reference (if present)
    properties:    unarchived property count
    jobFeesExGst:  charge amount ex GST. If only inc-GST present, divide by 1.1.

Returns a list of office dicts plus the invoicedTotal sum.
"""
from __future__ import annotations

import csv
import logging
import re
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def _to_float(s: str) -> float:
    s = (s or "").strip().replace("$", "").replace(",", "")
    if not s or s in {"-", "—"}:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _to_int(s: str) -> int | None:
    s = (s or "").strip().replace(",", "")
    if not s or s in {"-", "—"}:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def _detect_columns(headers: list[str]) -> dict[str, int]:
    cols: dict[str, int] = {}
    for i, h in enumerate(headers):
        low = (h or "").lower()
        if "office" not in cols and re.search(r"office|agency|name", low):
            cols["office"] = i
        if "invoice" not in cols and re.search(r"invoice|inv\s*no|inv\s*#", low):
            cols["invoice"] = i
        if "props" not in cols and re.search(r"propert|\bpum\b|unarchiv", low):
            cols["props"] = i
        if "ex_gst" not in cols and re.search(r"ex\s*gst|net\s*amount", low):
            cols["ex_gst"] = i
        elif "inc_gst" not in cols and re.search(r"inc\s*gst|gross|total", low):
            cols["inc_gst"] = i
    return cols


def parse_mw_charges(csv_path: Path) -> dict[str, Any]:
    if not csv_path.exists():
        return {}

    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = [row for row in reader if any(cell.strip() for cell in row)]

    if not rows:
        return {}

    headers = rows[0]
    cols = _detect_columns(headers)
    if "office" not in cols:
        log.warning("MW charges CSV: couldn't find office column from %s", headers)
        return {}

    offices: list[dict[str, Any]] = []
    for row in rows[1:]:
        if cols["office"] >= len(row):
            continue
        name = row[cols["office"]].strip()
        if not name:
            continue

        if "ex_gst" in cols and cols["ex_gst"] < len(row):
            fee = _to_float(row[cols["ex_gst"]])
        elif "inc_gst" in cols and cols["inc_gst"] < len(row):
            fee = round(_to_float(row[cols["inc_gst"]]) / 1.1, 2)
        else:
            fee = 0.0

        offices.append({
            "office":       name,
            "invoiceNo":    row[cols["invoice"]].strip() if "invoice" in cols and cols["invoice"] < len(row) and row[cols["invoice"]].strip() else None,
            "properties":   _to_int(row[cols["props"]]) if "props" in cols and cols["props"] < len(row) else None,
            "jobFeesExGst": fee,
        })

    invoiced_total = round(sum(o["jobFeesExGst"] for o in offices), 2)
    log.info("MW charges CSV parsed: %d offices, total $%.2f ex GST", len(offices), invoiced_total)
    return {"offices": offices, "invoicedTotal": invoiced_total}
