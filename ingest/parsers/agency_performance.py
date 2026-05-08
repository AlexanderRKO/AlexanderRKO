"""Parse Agency Performance CSV.

Aggregates per-agency rows into platform-wide totals:
    agencies          = total row count
    activeAgencies    = rows with active leases > 0
    inactiveAgencies  = agencies - activeAgencies
    totalLeases       = sum of active leases
    totalProperties   = sum of unarchived properties (PUM)

Column detection is fuzzy. Expected substrings (case-insensitive):
    agency / name / office          -> agency name (used to count rows)
    properties / pum / unarchived   -> property count
    leases / active leases          -> active lease count
"""
from __future__ import annotations

import csv
import logging
import re
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def _to_int(s: str) -> int:
    s = (s or "").strip().replace(",", "")
    if not s or s in {"-", "—"}:
        return 0
    try:
        return int(float(s))
    except ValueError:
        return 0


def _detect_columns(headers: list[str]) -> dict[str, int]:
    cols: dict[str, int] = {}
    for i, h in enumerate(headers):
        low = (h or "").lower()
        if "name" not in cols and re.search(r"\bagency\b|\bname\b|\boffice\b", low):
            cols["name"] = i
        if "props" not in cols and re.search(r"propert|\bpum\b|unarchiv", low):
            cols["props"] = i
        if "leases" not in cols and re.search(r"lease", low):
            cols["leases"] = i
    return cols


def parse_agency_performance(csv_path: Path) -> dict[str, Any]:
    if not csv_path.exists():
        return {}

    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = [row for row in reader if any(cell.strip() for cell in row)]

    if not rows:
        return {}

    headers = rows[0]
    cols = _detect_columns(headers)
    if "name" not in cols:
        log.warning("Agency CSV: couldn't identify agency name column from %s", headers)
        return {}

    agencies = 0
    active = 0
    total_leases = 0
    total_props = 0

    for row in rows[1:]:
        if cols["name"] >= len(row) or not row[cols["name"]].strip():
            continue
        agencies += 1
        leases = _to_int(row[cols["leases"]]) if cols.get("leases", -1) < len(row) and "leases" in cols else 0
        props  = _to_int(row[cols["props"]])  if cols.get("props", -1)  < len(row) and "props"  in cols else 0
        total_leases += leases
        total_props += props
        if leases > 0:
            active += 1

    out = {
        "agencies":         agencies,
        "activeAgencies":   active,
        "inactiveAgencies": agencies - active,
        "totalLeases":      total_leases,
        "totalProperties":  total_props,
    }
    log.info("Agency CSV parsed: %d agencies (%d active), %d leases, %d props",
             agencies, active, total_leases, total_props)
    return out
