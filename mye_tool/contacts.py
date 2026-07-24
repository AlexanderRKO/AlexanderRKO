"""Best-effort recovery of party (contact) names from a .MYE general ledger.

A .MYE does NOT contain a contacts table - only the chart of accounts and
journal lines. It is therefore impossible to export real contact records
(emails, addresses, ABNs) from it; the authoritative source for those is a
direct Contacts export from Xero/MYOB.

What can be recovered is the set of party names that appear in journal-line
*memos* (e.g. "Payment: Flooring FX Pty Ltd"). This module extracts those
into a de-duplicated list, with the transaction count and total value posted
against each, so it can be used as a cross-check or a migration starting
point. It is heuristic and will miss any party whose memo did not name them.
"""

from __future__ import annotations

import csv
import re
from decimal import Decimal
from typing import Dict, List

from .core import MyeFile

# Leading verbs/labels MYOB/Xero prepend to a party name in a memo.
_PREFIX = re.compile(
    r"^(payment|reversed|deposit|refund|sale|purchase|receipt|pay|bill|"
    r"invoice|transfer|paid|rec'd|received|eft|bpay)\s*[:;\-]?\s*",
    re.IGNORECASE,
)
# Trailing reference noise sometimes appended after the name.
_SUFFIX = re.compile(r"\s*[-#]\s*[A-Z0-9\-/]{2,}\s*$")


def clean_party(memo: str) -> str:
    """Strip common prefixes/suffixes to get at the party name."""
    name = memo.strip()
    # peel prefixes repeatedly (e.g. "Reversed: Payment: X")
    while True:
        stripped = _PREFIX.sub("", name)
        if stripped == name:
            break
        name = stripped
    name = _SUFFIX.sub("", name)
    return name.strip()


def extract_contacts(mye: MyeFile) -> List[dict]:
    """Return recovered parties as dicts with name, transaction count and
    total absolute value, sorted by descending value."""
    counts: Dict[str, int] = {}
    totals: Dict[str, Decimal] = {}
    first_seen: Dict[str, str] = {}
    order: List[str] = []
    for entry in mye.entries:
        memo = entry.lines[0].memo if entry.lines else ""
        name = clean_party(memo)
        if not name or len(name) < 2:
            continue
        key = name.lower()
        if key not in counts:
            counts[key] = 0
            totals[key] = Decimal("0")
            first_seen[key] = name
            order.append(key)
        counts[key] += 1
        # value of the entry = sum of the debits (== sum of credits)
        totals[key] += sum((l.debit for l in entry.lines), Decimal("0"))
    rows = [
        {
            "name": first_seen[k],
            "transactions": counts[k],
            "total_value": totals[k],
        }
        for k in order
    ]
    rows.sort(key=lambda r: r["total_value"], reverse=True)
    return rows


def export_contacts_csv(mye: MyeFile, path: str) -> str:
    """Write the recovered party list to CSV.

    Columns match the start of Xero's contact import template so it can be
    fleshed out there, plus transaction count / value for context. Note this
    is derived from journal memos, NOT a real contacts export - see the
    module docstring.
    """
    rows = extract_contacts(mye)
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(
            ["*ContactName", "AccountNumber", "transactions_in_period", "total_value"]
        )
        for r in rows:
            w.writerow([r["name"], "", r["transactions"], f"{r['total_value']:.2f}"])
    return path
