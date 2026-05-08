"""Parse Zai tax invoice PDF.

Extracts invoice number, due date, virtual account counts, and the 14 fee lines.
Falls back gracefully on any line it can't match — the manual.yml override
handles edge cases.

Line-item names per DASHBOARD_INSTRUCTIONS.md §3:

    BPAY PAYIN                          -> payinBpay
    REALTIME PAYIN                      -> payinRealtime
    BPAY PAYOUT                         -> payoutBpay
    DIRECT CREDIT                       -> payoutDirect
    DIRECT ENTRY                        -> payoutEntry
    REALTIME PAYOUT                     -> payoutRealtime
    CREDIT CARD - VISA                  -> cardVisa
    CREDIT CARD - MASTER                -> cardMaster
    DIRECT DEBIT                        -> cardDebit
    CREDIT CARD - AMERICAN EXPRESS      -> cardAmex
    VIRTUAL ACCOUNTS ACTIVE             -> vaActive (qty -> vaActive count, $ -> zaiLines.vaActive)
    VIRTUAL ACCOUNTS SETUP              -> vaSetup
    ADDITIONAL FEES - CHARGEBACKS       -> chargebacks
    ADDITIONAL FEES - DISPUTES          -> disputes
    MANUAL PAYMENT MATCHING             -> manualMatch
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Map of lowercased line-item match string -> zaiLines key
LINE_KEYS = {
    "bpay payin":                       "payinBpay",
    "realtime payin":                   "payinRealtime",
    "bpay payout":                      "payoutBpay",
    "direct credit":                    "payoutDirect",
    "direct entry":                     "payoutEntry",
    "realtime payout":                  "payoutRealtime",
    "credit card - visa":               "cardVisa",
    "credit card - master":             "cardMaster",
    "direct debit":                     "cardDebit",
    "credit card - american express":   "cardAmex",
    "virtual accounts active":          "vaActive",
    "virtual accounts setup":           "vaSetup",
    "additional fees - chargebacks":    "chargebacks",
    "additional fees - disputes":       "disputes",
    "manual payment matching":          "manualMatch",
}

AMOUNT_RE = re.compile(r"\$?\s*([\d,]+\.\d{2})")
QTY_RE    = re.compile(r"(?:^|\s)(\d{1,7})(?:\s|$)")


def _extract_text(pdf_path: Path) -> str:
    try:
        import pdfplumber  # type: ignore
    except ImportError:
        log.warning("pdfplumber not installed; skipping Zai PDF parse")
        return ""
    text_parts: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            txt = page.extract_text() or ""
            text_parts.append(txt)
    return "\n".join(text_parts)


def _amount(s: str) -> float | None:
    m = AMOUNT_RE.search(s)
    return float(m.group(1).replace(",", "")) if m else None


def parse_zai_invoice(pdf_path: Path) -> dict[str, Any]:
    """Return partial Month dict with whatever could be extracted."""
    if not pdf_path.exists():
        return {}
    text = _extract_text(pdf_path)
    if not text:
        return {}

    out: dict[str, Any] = {"zaiLines": {}}

    inv_m = re.search(r"(?:Tax\s+Invoice|Invoice)\s*(?:No\.?|Number|#)?\s*[:#]?\s*(\d{3,6})", text, re.I)
    if inv_m:
        out["invoiceNo"] = inv_m.group(1)

    due_m = re.search(r"Due\s+Date[:\s]+(\d{1,2}\s+[A-Za-z]+\s+\d{4})", text, re.I)
    if due_m:
        out["dueDate"] = due_m.group(1)

    # Walk line by line, matching the longest line key first to avoid
    # "direct credit" matching inside "credit card - ..." etc.
    sorted_keys = sorted(LINE_KEYS.keys(), key=len, reverse=True)
    seen: set[str] = set()
    total: float | None = None

    for line in text.splitlines():
        low = line.lower()
        for label in sorted_keys:
            field = LINE_KEYS[label]
            if label in low and field not in seen:
                amt = _amount(line)
                if amt is not None:
                    out["zaiLines"][field] = amt
                    seen.add(field)

                    # VA Active and VA Setup also carry quantity counts.
                    if field in ("vaActive", "vaSetup"):
                        # Strip the matching label, then look for the qty integer.
                        rest = re.sub(re.escape(label), "", line, flags=re.I)
                        rest = AMOUNT_RE.sub("", rest)
                        qty_m = QTY_RE.search(rest)
                        if qty_m:
                            out[field] = int(qty_m.group(1))
                break

        if total is None and re.search(r"\bTotal\s+\(ex\s*GST\)\b|\bSubtotal\b|\bNet\s+Total\b", line, re.I):
            total = _amount(line)

    if total is not None:
        out["zaiNet"] = total
        out["zaiGst"] = round(total * 0.1, 2)
        out["zaiTotal"] = round(total * 1.1, 2)

    log.info("Zai PDF parsed: %d fee lines, invoice=%s, total=%s",
             len(out["zaiLines"]), out.get("invoiceNo", "?"), out.get("zaiNet", "?"))
    return out
