"""Combine parsed sources into a complete Month dict matching data.json schema.

Strategy:
1. Resolve YYYY-MM directory name -> month label (e.g. "Apr-26" / "April 2026").
2. Run each parser on its expected file.
3. Deep-merge in this priority: defaults < parsed < manual.yml.
4. Validate: zaiNet must equal sum of zaiLines (within $0.02 rounding).

Required filenames in each month folder (case-insensitive substring match):
    *zai*invoice*.pdf            -> Zai tax invoice
    *platform*revenue*.csv       -> Platform revenue export
    *agency*performance*.csv     -> Agency performance export
    *mw*charges*.csv             -> MW per-office platform charges export
    manual.yml                   -> Manual overrides (rev share, MW totals, notes)

Anything else in the folder is ignored. The manual.yml file lets you specify
mwRebate, agencyRevShare, MW invoice number, MW paid amount, and any field
the parsers didn't catch.
"""
from __future__ import annotations

import calendar
import logging
import re
from datetime import date
from pathlib import Path
from typing import Any

from .parsers import (
    parse_zai_invoice,
    parse_platform_revenue,
    parse_agency_performance,
    parse_mw_charges,
    load_manual,
)

log = logging.getLogger(__name__)

REQUIRED_REVENUE_KEYS = ("baseSub", "managedPlus", "transaction", "tradie")
ZAI_LINE_KEYS = (
    "payinBpay", "payinRealtime",
    "payoutBpay", "payoutDirect", "payoutEntry", "payoutRealtime",
    "cardVisa", "cardMaster", "cardDebit", "cardAmex",
    "vaActive", "vaSetup",
    "chargebacks", "disputes", "manualMatch",
)


def _find_file(month_dir: Path, *patterns: str) -> Path | None:
    for path in sorted(month_dir.iterdir()):
        if not path.is_file():
            continue
        low = path.name.lower()
        if all(p in low for p in patterns):
            return path
    return None


def _yyyymm_to_labels(name: str) -> tuple[str, str, str] | None:
    m = re.match(r"^(\d{4})-(\d{2})$", name)
    if not m:
        return None
    year, month = int(m.group(1)), int(m.group(2))
    if not 1 <= month <= 12:
        return None
    short = calendar.month_abbr[month]
    short_id = f"{short}-{str(year)[-2:]}"     # e.g. "Apr-26"
    full = f"{calendar.month_name[month]} {year}"
    return short_id, full, short


def _deep_merge(base: dict, overlay: dict) -> dict:
    out = dict(base)
    for k, v in overlay.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _validate(month: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    for k in ("month", "label", "short", "zaiNet", "totalProperties", "totalLeases"):
        if k not in month or month[k] in (None, ""):
            errors.append(f"missing required field: {k}")

    rev = month.get("revenue", {})
    for k in REQUIRED_REVENUE_KEYS:
        if k not in rev:
            errors.append(f"revenue.{k} missing")
        else:
            for sub in ("billed", "completed", "debtors"):
                rev[k].setdefault(sub, 0.0)

    lines = month.get("zaiLines", {})
    for k in ZAI_LINE_KEYS:
        lines.setdefault(k, 0.0)
    line_sum = sum(lines[k] for k in ZAI_LINE_KEYS)
    if "zaiNet" in month:
        diff = abs(line_sum - month["zaiNet"])
        if diff > 0.02:
            errors.append(
                f"zaiNet ${month['zaiNet']:.2f} ≠ sum of zaiLines ${line_sum:.2f} "
                f"(diff ${diff:.2f}). Add the gap to payoutRealtime or fix the source."
            )

    return errors


def build_month(month_dir: Path) -> tuple[dict[str, Any] | None, list[str]]:
    """Build a full Month entry from a YYYY-MM folder. Returns (month, errors)."""
    if not month_dir.is_dir():
        return None, [f"not a directory: {month_dir}"]

    labels = _yyyymm_to_labels(month_dir.name)
    if not labels:
        return None, [f"folder name {month_dir.name!r} must be YYYY-MM"]
    short_id, full_label, short = labels

    # 1. Defaults
    month: dict[str, Any] = {
        "month":          short_id,
        "label":          full_label,
        "short":          short,
        "smsRevenue":     0.0,
        "implFees":       0.0,
        "mwRebate":       0.0,
        "agencyRevShare": 0.0,
        "vaActive":       0,
        "vaSetup":        0,
        "revenue":  {k: {"billed": 0.0, "completed": 0.0, "debtors": 0.0} for k in REQUIRED_REVENUE_KEYS},
        "zaiLines": {k: 0.0 for k in ZAI_LINE_KEYS},
    }

    # 2. Parsers
    zai_pdf = _find_file(month_dir, "zai") or _find_file(month_dir, "tax", "invoice")
    if zai_pdf and zai_pdf.suffix.lower() == ".pdf":
        month = _deep_merge(month, parse_zai_invoice(zai_pdf))
    else:
        log.warning("[%s] no Zai invoice PDF found", short_id)

    platform_csv = _find_file(month_dir, "platform", "revenue")
    if platform_csv:
        month = _deep_merge(month, parse_platform_revenue(platform_csv))
    else:
        log.warning("[%s] no platform revenue CSV found", short_id)

    agency_csv = _find_file(month_dir, "agency", "performance") or _find_file(month_dir, "agency")
    if agency_csv:
        month = _deep_merge(month, parse_agency_performance(agency_csv))
    else:
        log.warning("[%s] no agency performance CSV found", short_id)

    mw_csv = _find_file(month_dir, "mw", "charges") or _find_file(month_dir, "marshall")
    mw_partial = parse_mw_charges(mw_csv) if mw_csv else {}

    # 3. Manual overrides win
    manual = load_manual(month_dir)
    mw_manual = manual.pop("_mw", {}) if isinstance(manual, dict) else {}
    if manual:
        month = _deep_merge(month, manual)

    # If due date wasn't parsed, default to the 10th of the following month.
    if "dueDate" not in month or not month["dueDate"]:
        y, m = int(month_dir.name.split("-")[0]), int(month_dir.name.split("-")[1])
        next_y, next_m = (y + 1, 1) if m == 12 else (y, m + 1)
        d = date(next_y, next_m, 10)
        month["dueDate"] = d.strftime("%-d %B %Y") if hasattr(d, "strftime") else f"10 {calendar.month_name[next_m]} {next_y}"

    # MW office data: parsed offices + manual overrides
    mw_entry: dict[str, Any] = {}
    if mw_partial:
        mw_entry["offices"]       = mw_partial["offices"]
        mw_entry["invoicedTotal"] = mw_partial["invoicedTotal"]
    if mw_manual:
        mw_entry = _deep_merge(mw_entry, mw_manual)
    if mw_entry:
        mw_entry.setdefault("offices", [])
        mw_entry.setdefault("invoicedTotal", round(sum(o.get("jobFeesExGst", 0) for o in mw_entry["offices"]), 2))
        mw_entry.setdefault("dashboardTotal", month.get("mwRebate", 0.0))
        mw_entry.setdefault("mwInvoiceNo", "")
        mw_entry.setdefault("mwPaid", mw_entry["dashboardTotal"])
        mw_entry.setdefault("note", "")

    errors = _validate(month)
    return ({"month": month, "mwOffices": mw_entry}, errors)
