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
from typing import List, Tuple

from .core import Account, MyeFile

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


def build_rows(mye: MyeFile):
    """Yield (import_row, confident) for each account."""
    for account in mye.accounts:
        xtype, confident = infer_xero_type(account)
        row = [
            account.code,
            account.name,
            xtype,
            DEFAULT_TAX_CODE,
            "",  # Description
            "",  # Dashboard
            "",  # Expense Claims
            "",  # Enable Payments
        ]
        yield row, confident


def export_xero_coa(mye: MyeFile, path: str) -> str:
    """Write a Xero (AU) chart-of-accounts import CSV (the clean import file)."""
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(XERO_COA_HEADER)
        for row, _confident in build_rows(mye):
            w.writerow(row)
    return path


def export_xero_coa_review(mye: MyeFile, path: str) -> str:
    """Write a companion review CSV with an extra column flagging accounts
    whose Type was guessed by fallback (so it can be checked before import)."""
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["Code", "Name", "Inferred Type", "Tax Code", "needs_review"])
        for row, confident in build_rows(mye):
            w.writerow([row[0], row[1], row[2], row[3], "" if confident else "REVIEW"])
    return path
