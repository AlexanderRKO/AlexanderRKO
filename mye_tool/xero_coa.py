"""Map a MYOB .MYE chart of accounts to a Xero (Australia) chart-of-accounts
import CSV.

A .MYE only stores each account's *code* and *name* - it does not carry the
account **Type** or **Tax Code** that Xero's importer requires (hence the
"first row does not contain the mandatory fields - Code, Name, Type, Tax
Code" error when importing a bare code/name file).

This module infers a Xero account ``Type`` for each account, primarily from
the account *name* (which is independent of the MYOB numbering scheme) with
the account *code* range as a fallback. Every ``Tax Code`` defaults to
``BAS Excluded`` so the file imports cleanly the first time; GST treatment is
then set per account inside Xero afterwards.

Xero account ``Type`` values used here are Xero's import codes:
    CURRENT, FIXED, INVENTORY, NONCURRENT, PREPAYMENT, CURRLIAB, TERMLIAB,
    EQUITY, REVENUE, SALES, OTHERINCOME, DIRECTCOSTS, EXPENSE, OVERHEADS,
    DEPRECIATN, OTHEREXPENSE.

Bank accounts are deliberately mapped to ``CURRENT`` (current asset) rather
than ``BANK``: Xero's chart-of-accounts CSV import rejects ``BANK`` accounts
unless a bank account number is supplied, which a .MYE does not contain.
Convert them to the Bank type inside Xero after import (that screen is also
where the BSB/account number is entered).
"""

from __future__ import annotations

import csv
import re
from typing import Dict, List, Optional, Tuple

from .core import Account, MyeFile

# 3-digit code ranges per Xero type, following the standard AU numbering
# that the existing KMB/RKO charts use (revenue 2xx, direct costs 3xx,
# expenses 4xx-5xx, assets 6xx-7xx, liabilities 8xx-9xx, equity 92x-99x).
# Used by the optional renumber step to assign clean 3-digit codes.
CODE_RANGES: Dict[str, Tuple[int, int]] = {
    "REVENUE": (200, 259),
    "SALES": (200, 259),
    "OTHERINCOME": (260, 299),
    "DIRECTCOSTS": (300, 399),
    "EXPENSE": (400, 579),
    "OVERHEADS": (400, 579),
    "DEPRECIATN": (580, 589),
    "OTHEREXPENSE": (590, 599),
    "CURRENT": (600, 679),
    "PREPAYMENT": (680, 689),
    "INVENTORY": (690, 699),
    "FIXED": (700, 749),
    "NONCURRENT": (760, 799),
    "CURRLIAB": (800, 879),
    "TERMLIAB": (900, 919),
    "EQUITY": (920, 999),
}

XERO_COA_HEADER = [
    "*Code",
    "*Name",
    "*Type",
    "*Tax Code",
    "Description",
    "Dashboard",
    "Expense Claims",
    "Enable Payments",
]

DEFAULT_TAX_CODE = "BAS Excluded"

# Name keyword -> Xero type, tried in order. The first substring that
# matches the lower-cased account name wins, so more specific phrases
# (e.g. "bank fee", "accumulated depreciation") must precede the broader
# ones ("bank", "depreciation").
NAME_RULES: List[Tuple[str, str]] = [
    # --- expenses that contain an asset/liability-sounding word ---
    ("bank fee", "EXPENSE"),
    ("bank charge", "EXPENSE"),
    ("merchant fee", "EXPENSE"),
    ("interest expense", "EXPENSE"),
    ("interest paid", "EXPENSE"),
    ("doubtful debt", "CURRENT"),  # provision for doubtful debts = contra-asset
    ("accumulated dep", "FIXED"),  # contra-asset, sits with fixed assets
    ("less accumulated", "FIXED"),
    ("income tax", "EXPENSE"),  # before the generic "income" -> REVENUE rule
    # --- income ---
    ("interest income", "OTHERINCOME"),
    ("interest received", "OTHERINCOME"),
    ("dividends paid", "EQUITY"),  # distributions to owners, before "dividend"
    ("dividend paid", "EQUITY"),
    ("dividend", "OTHERINCOME"),
    ("gain on", "OTHERINCOME"),
    ("gain/(loss)", "OTHERINCOME"),
    ("capital gain", "OTHERINCOME"),
    ("distribution received", "OTHERINCOME"),
    ("grant", "OTHERINCOME"),
    ("commission received", "OTHERINCOME"),
    ("rental income", "REVENUE"),
    ("rent received", "REVENUE"),
    ("sales", "REVENUE"),
    ("service income", "REVENUE"),
    ("fee income", "REVENUE"),
    ("fees income", "REVENUE"),
    ("income", "REVENUE"),
    ("revenue", "REVENUE"),
    ("turnover", "REVENUE"),
    # --- cost of goods sold ---
    ("cost of goods", "DIRECTCOSTS"),
    ("cost of sales", "DIRECTCOSTS"),
    ("purchases", "DIRECTCOSTS"),
    ("opening stock", "DIRECTCOSTS"),
    ("closing stock", "DIRECTCOSTS"),
    ("opening wip", "DIRECTCOSTS"),
    ("closing wip", "DIRECTCOSTS"),
    ("freight & delivery", "DIRECTCOSTS"),
    ("subcontractor", "DIRECTCOSTS"),
    # --- depreciation / amortisation (expense) ---
    ("depreciation", "DEPRECIATN"),
    ("amortisation", "DEPRECIATN"),
    ("amortization", "DEPRECIATN"),
    ("impairment", "DEPRECIATN"),
    # --- current assets ---
    ("petty cash", "CURRENT"),
    ("cash on hand", "CURRENT"),
    ("cash at bank", "CURRENT"),
    ("undeposited", "CURRENT"),
    ("accounts receivable", "CURRENT"),
    ("trade debtor", "CURRENT"),
    ("receivable", "CURRENT"),
    ("term deposit", "CURRENT"),
    ("gst", "CURRLIAB"),  # GST control accounts are current liabilities
    # --- bank (mapped to current asset, see module docstring) ---
    ("savings", "CURRENT"),
    ("bank account", "CURRENT"),
    ("bank bill", "CURRENT"),
    ("airwallex", "CURRENT"),
    ("gocardless", "CURRENT"),
    ("paypal", "CURRENT"),
    ("stripe", "CURRENT"),
    ("clearing", "CURRENT"),
    ("westpac", "CURRENT"),
    # --- prepayments / inventory ---
    ("prepay", "PREPAYMENT"),
    ("prepaid", "PREPAYMENT"),
    ("inventory", "INVENTORY"),
    ("stock on hand", "INVENTORY"),
    # --- fixed / non-current assets ---
    ("formation cost", "NONCURRENT"),
    ("borrowing cost", "NONCURRENT"),
    ("goodwill", "NONCURRENT"),
    ("intangible", "NONCURRENT"),
    ("shares in", "NONCURRENT"),
    ("investment", "NONCURRENT"),
    ("motor vehicle", "FIXED"),
    ("plant", "FIXED"),
    ("equipment", "FIXED"),
    ("furniture", "FIXED"),
    ("fixtures", "FIXED"),
    ("buildings", "FIXED"),
    ("land", "FIXED"),
    ("property", "FIXED"),
    ("leasehold", "FIXED"),
    ("at cost", "FIXED"),
    # --- liabilities ---
    ("accounts payable", "CURRLIAB"),
    ("trade creditor", "CURRLIAB"),
    ("payable", "CURRLIAB"),
    ("payg", "CURRLIAB"),
    ("paye", "CURRLIAB"),
    ("superannuation", "CURRLIAB"),
    ("provision", "CURRLIAB"),
    ("accrual", "CURRLIAB"),
    ("accrued", "CURRLIAB"),
    ("credit card", "CURRLIAB"),
    ("hire purchase", "TERMLIAB"),
    ("lease liability", "TERMLIAB"),
    ("borrowings", "TERMLIAB"),
    ("loan -", "TERMLIAB"),
    ("loan(", "TERMLIAB"),
    ("loan (nca)", "TERMLIAB"),
    ("loans to director", "CURRENT"),  # money owed TO the company = asset
    ("loan (ca)", "CURRENT"),
    # --- equity ---
    ("retained earning", "EQUITY"),
    ("current year earning", "EQUITY"),
    ("owner", "EQUITY"),
    ("drawings", "EQUITY"),
    ("capital", "EQUITY"),
    ("shareholder", "EQUITY"),
    ("share capital", "EQUITY"),
    ("member funds", "EQUITY"),
    ("trust capital", "EQUITY"),
    ("units on issue", "EQUITY"),
    ("distribution", "EQUITY"),
    ("reserve", "EQUITY"),
    # --- common operating expenses ---
    ("income tax", "EXPENSE"),
    ("wages", "EXPENSE"),
    ("salaries", "EXPENSE"),
    ("rent", "EXPENSE"),
    ("insurance", "EXPENSE"),
    ("expense", "EXPENSE"),
    ("fees", "EXPENSE"),
    ("fee", "EXPENSE"),
]

# Fallback by leading digit of a 5-digit MYOB-native code (1xxxx asset,
# 2xxxx liability, ...). Only used when the name gives no signal.
MYOB_CLASS_BY_FIRST_DIGIT = {
    "1": "CURRENT",
    "2": "CURRLIAB",
    "3": "EQUITY",
    "4": "REVENUE",
    "5": "DIRECTCOSTS",
    "6": "EXPENSE",
    "7": "OVERHEADS",
    "8": "OTHEREXPENSE",
    "9": "OTHERINCOME",
}


# Accounts that Xero creates and manages itself. They already exist in
# every Xero org (including a clean file with the generic chart), are
# locked, and cannot be created via the chart-of-accounts import - trying
# to import them makes the whole import fail. They are excluded from the
# import file (and flagged in the review file) so the import succeeds.
SYSTEM_ACCOUNT_KEYWORDS = [
    "accounts receivable",
    "accounts payable",
    "retained earning",
    "current year earning",
    "rounding",
    "historical adjustment",
    "tracking transfer",
    "unrealised currency",
    "realised currency",
    "unrealized currency",
    "realized currency",
    "bank revaluation",
    "wages payable",
]

# GST control accounts are Xero system accounts too, but "gst" is too
# common a substring to match loosely (e.g. "Non-GST Expenses"), so these
# are matched as whole names / prefixes instead.
SYSTEM_ACCOUNT_EXACT = {
    "gst",
    "gst payable",
    "gst collected",
    "gst paid",
    "gst control",
    "gst (non-registered)",
}


def is_system_account(account: Account) -> bool:
    """True if Xero manages this account itself (so it must not be imported)."""
    name = account.name.strip().lower()
    # A provision/doubtful-debts account is a real, importable contra-asset
    # even though its name contains "accounts receivable".
    if "provision" in name or "doubtful" in name:
        return False
    if name in SYSTEM_ACCOUNT_EXACT:
        return True
    return any(kw in name for kw in SYSTEM_ACCOUNT_KEYWORDS)


def infer_xero_type(account: Account) -> Tuple[str, bool]:
    """Return (xero_type, confident). ``confident`` is False when the type
    came from a fallback rather than a clear name match, so callers can flag
    it for review."""
    name = account.name.strip().lower()
    for keyword, xtype in NAME_RULES:
        if keyword in name:
            return xtype, True
    # Fallback: 5-digit MYOB-native codes carry the class in the first digit.
    code = account.code.strip().lstrip("-")
    digits = "".join(ch for ch in code if ch.isdigit())
    if len(digits) >= 5 and digits[0] in MYOB_CLASS_BY_FIRST_DIGIT:
        return MYOB_CLASS_BY_FIRST_DIGIT[digits[0]], False
    return "EXPENSE", False  # safest catch-all; always a valid Xero type


def assign_3digit_codes(
    mye: MyeFile, exclude_system: bool = True
) -> List[Optional[str]]:
    """Return a new 3-digit code per account (parallel to ``mye.accounts``;
    ``None`` for excluded system accounts).

    Codes that are already a clean, unique 3-digit number are kept as-is so
    accounts that already match Xero's generic chart stay put; every other
    account (5-digit MYOB codes, 4-digit 9900-series, suffixed codes) is
    assigned the next free 3-digit code in its account-type range.
    """
    new_codes: List[Optional[str]] = [None] * len(mye.accounts)
    used = set()

    # Pass 1: keep existing valid, unique 3-digit codes.
    for i, account in enumerate(mye.accounts):
        if exclude_system and is_system_account(account):
            continue
        code = account.code.strip()
        if re.fullmatch(r"\d{3}", code) and code not in used:
            new_codes[i] = code
            used.add(code)

    # Pass 2: allocate fresh codes for the rest, sequentially within range.
    range_ptr: Dict[Tuple[int, int], int] = {}

    def allocate(xtype: str) -> str:
        lo, hi = CODE_RANGES.get(xtype, CODE_RANGES["EXPENSE"])
        c = max(range_ptr.get((lo, hi), lo), lo)
        while c <= hi and f"{c:03d}" in used:
            c += 1
        if c > hi:
            raise ValueError(
                f"Ran out of 3-digit codes for type {xtype} (range {lo}-{hi}). "
                "Too many accounts of this type to fit in 3 digits."
            )
        range_ptr[(lo, hi)] = c + 1
        code = f"{c:03d}"
        used.add(code)
        return code

    for i, account in enumerate(mye.accounts):
        if exclude_system and is_system_account(account):
            continue
        if new_codes[i] is not None:
            continue
        xtype, _ = infer_xero_type(account)
        new_codes[i] = allocate(xtype)

    return new_codes


def build_rows(mye: MyeFile, renumber: bool = False, exclude_system: bool = True):
    """Yield (account, code, xero_type, confident, is_system) for each
    account. ``code`` is the renumbered 3-digit code when ``renumber`` is
    set, otherwise the account's original code."""
    new_codes = (
        assign_3digit_codes(mye, exclude_system) if renumber else [None] * len(mye.accounts)
    )
    for i, account in enumerate(mye.accounts):
        system = is_system_account(account)
        xtype, confident = infer_xero_type(account)
        code = new_codes[i] if (renumber and new_codes[i] is not None) else account.code
        yield account, code, xtype, confident, system


def _import_row(code: str, name: str, xtype: str) -> list:
    return [
        code,
        name,
        xtype,
        DEFAULT_TAX_CODE,
        "",  # Description
        "",  # Dashboard
        "",  # Expense Claims
        "",  # Enable Payments
    ]


def export_xero_coa(
    mye: MyeFile, path: str, exclude_system: bool = True, renumber: bool = False
) -> str:
    """Write the Xero (AU) chart-of-accounts import CSV.

    Xero-managed system accounts (Accounts Receivable, GST, Retained
    Earnings, ...) are excluded by default because they already exist in
    the target org and cannot be imported. Pass ``exclude_system=False``
    to include them anyway. Pass ``renumber=True`` to assign clean 3-digit
    account codes.
    """
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(XERO_COA_HEADER)
        for account, code, xtype, _confident, system in build_rows(
            mye, renumber, exclude_system
        ):
            if system and exclude_system:
                continue
            w.writerow(_import_row(code, account.name, xtype))
    return path


def export_xero_coa_review(
    mye: MyeFile, path: str, exclude_system: bool = True, renumber: bool = False
) -> str:
    """Write a companion review CSV flagging accounts whose Type was guessed
    (``REVIEW``) and Xero-managed accounts excluded from the import
    (``SYSTEM - excluded``). When ``renumber`` is set it also shows the
    original MYOB code next to the new 3-digit code."""
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        header = ["Code", "Name", "Inferred Type", "Tax Code", "status"]
        if renumber:
            header = ["New Code", "Original Code", "Name", "Inferred Type", "Tax Code", "status"]
        w.writerow(header)
        for account, code, xtype, confident, system in build_rows(
            mye, renumber, exclude_system
        ):
            if system:
                status = "SYSTEM - excluded (Xero manages this account)"
            elif not confident:
                status = "REVIEW - type guessed"
            else:
                status = ""
            if renumber:
                shown = "" if system else code
                w.writerow([shown, account.code, account.name, xtype, DEFAULT_TAX_CODE, status])
            else:
                w.writerow([account.code, account.name, xtype, DEFAULT_TAX_CODE, status])
    return path


def export_code_mapping(
    mye: MyeFile, path: str, exclude_system: bool = True
) -> str:
    """Write the old-code -> new-code mapping (for re-coding balances,
    journals or other data to match the renumbered chart). System accounts
    are listed with a blank new code and a note."""
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["original_code", "new_code", "name", "type", "note"])
        for account, code, xtype, _confident, system in build_rows(
            mye, renumber=True, exclude_system=exclude_system
        ):
            if system and exclude_system:
                w.writerow([account.code, "", account.name, xtype, "system account - not imported"])
            else:
                changed = "" if code == account.code else "renumbered"
                w.writerow([account.code, code, account.name, xtype, changed])
    return path
