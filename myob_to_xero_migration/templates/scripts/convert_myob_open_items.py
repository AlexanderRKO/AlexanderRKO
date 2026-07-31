#!/usr/bin/env python3
"""Convert a MYOB open-items report into a Xero import + reconciliation gate.

Handles both sides of the ledger from the same MYOB report family:

  * Receivables Reconciliation [Detail]  -> Xero Sales Invoices import
  * Payables Reconciliation [Detail]     -> Xero Bills import
  * Aged Receivables / Aged Payables [Detail] also parse (same shape)

The whole point of this script is the RECONCILIATION GATE. MYOB prints an
"Out of Balance Amount" on the reconciliation reports: the difference
between the subledger and the general-ledger control account. If that is
not zero, the client file is not fit to convert and no amount of clever
CSV wrangling will fix it. This script refuses (exit code 2) rather than
producing a tidy-looking file that will not tie out in Xero.

It also reconciles its OWN output back to the report's Grand Total, so
"the import equals the report equals the GL" is proven, not assumed.

Usage
-----
    python convert_myob_open_items.py \\
        --report "Receivables Reconciliation [Detail].txt" \\
        --side AR \\
        --out ./client_name/ \\
        --account-code 200 \\
        [--terms-report "Aged Receivables [Detail].txt"] \\
        [--default-terms 14] \\
        [--force]

Notes
-----
* --terms-report is optional. No MYOB open-items report carries an explicit
  due date, so due dates are derived from customer payment terms, which only
  the *Aged* reports print. Without it every due date falls back to
  --default-terms days after the invoice date.
* Credit notes (negative balances) are written to a SEPARATE file. Xero's
  invoice/bill import rejects negative amounts; they must go through the
  Credit Notes import instead.
* Amounts are the BALANCE STILL OWING, not the original invoice value, so
  part-paid invoices convert correctly.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

# Xero's Sales Invoice and Bills import templates share this column set.
XERO_COLS = [
    "*ContactName", "EmailAddress", "POAddressLine1", "POAddressLine2",
    "POAddressLine3", "POAddressLine4", "POCity", "PORegion", "POPostalCode",
    "POCountry", "*InvoiceNumber", "Reference", "*InvoiceDate", "*DueDate",
    "InventoryItemCode", "*Description", "*Quantity", "*UnitAmount", "Discount",
    "*AccountCode", "*TaxType", "TrackingName1", "TrackingOption1",
    "TrackingName2", "TrackingOption2", "Currency", "BrandingTheme",
]

# MYOB tax code -> Xero tax type. Australian GST codes; review against the
# client's own tax-code list before relying on it, since MYOB files can carry
# custom codes. Anything not in this map is reported rather than guessed.
TAX_MAP_AR = {
    "GST": "GST on Income",
    "FRE": "GST Free Income",
    "EXP": "GST Free Exports",
    "INP": "Input Taxed",
    "ITS": "Input Taxed",
    "N-T": "BAS Excluded",
    "NT": "BAS Excluded",
    "GNR": "BAS Excluded",
}
TAX_MAP_AP = {
    "GST": "GST on Expenses",
    "CAP": "GST on Capital",
    "FRE": "GST Free Expenses",
    "INP": "Input Taxed",
    "ITS": "Input Taxed",
    "N-T": "BAS Excluded",
    "NT": "BAS Excluded",
    "GNR": "BAS Excluded",
}

DATE_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
TERMS_RE = re.compile(r"^\d+%.*Net", re.IGNORECASE)
ASOF_RE = re.compile(r"As\s+of\s+(\d{1,2}/\d{1,2}/\d{4})", re.IGNORECASE)
OOB_RE = re.compile(r"Out of Balance Amount", re.IGNORECASE)
CONTROL_RE = re.compile(r"(Receivables|Payables) Account", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# small helpers                                                               #
# --------------------------------------------------------------------------- #

def money(s) -> float:
    """Parse MYOB currency: $1,234.56 / "-$1,164.58" / (123.45) / blank."""
    s = str(s or "").replace("$", "").replace(",", "").strip().strip('"')
    if not s:
        return 0.0
    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]
    try:
        v = float(s)
    except ValueError:
        return 0.0
    return -v if neg else v


def parse_date(s: str) -> date:
    d, m, y = (int(x) for x in s.split("/"))
    return date(y, m, d)


def last_day(y: int, m: int) -> int:
    return 31 if m == 12 else (date(y, m + 1, 1) - timedelta(days=1)).day


def clean_name(raw: str, row: list[str]) -> str:
    """Customer/supplier name line.

    Names containing a comma are CSV-quoted by MYOB ("Adamantidis, Michael").
    Use the parsed field when the row split cleanly, else strip the quotes.
    """
    if len(row) == 1:
        return row[0].strip()
    return raw.strip().strip('"')


def due_from_terms(inv: date, terms: str | None, default_days: int) -> tuple[date, str]:
    """Derive a due date from a MYOB payment-terms string.

    Returns (due_date, quality) where quality records how much we trust it:
    'terms' (read from the file), 'eom-assumed' (end-of-month terms, which
    need an interpretation), or 'default' (no terms captured).
    """
    t = terms or ""
    if not t:
        return inv + timedelta(days=default_days), "default"
    if re.search(r"after EOM", t, re.IGNORECASE):
        m = re.search(r"Net\s+(\d+)", t, re.IGNORECASE)
        nm = inv.month % 12 + 1
        ny = inv.year + (1 if inv.month == 12 else 0)
        if m:
            return date(ny, nm, min(int(m.group(1)), last_day(ny, nm))), "eom-assumed"
        return date(inv.year, inv.month, last_day(inv.year, inv.month)), "eom-assumed"
    m = re.search(r"Net\s+(\d+)", t, re.IGNORECASE)
    if m:
        return inv + timedelta(days=int(m.group(1))), "terms"
    return inv + timedelta(days=default_days), "default"


# --------------------------------------------------------------------------- #
# report parsing                                                              #
# --------------------------------------------------------------------------- #

def find_header(lines: list[str]) -> tuple[int, int]:
    """Locate the column header row and the index of the 'Total Due' column.

    The column position differs between report types:
        Aged:  ID No.,Date,Total Due,0 - 30,...            -> index 2
        Recon: ID No.,Date,Orig. Curr.,Total Due,Current,...-> index 3
    so we read it from the header rather than hard-coding it.
    """
    for i, ln in enumerate(lines):
        if not ln.startswith("ID No."):
            continue
        cols = [c.strip().lower() for c in next(csv.reader([ln]))]
        for j, c in enumerate(cols):
            if "total due" in c:
                return i, j
        return i, 2  # header found but unlabelled column; fall back
    raise SystemExit("ERROR: could not find the 'ID No.,Date,...' header row. "
                     "Is this a MYOB Receivables/Payables [Detail] export?")


def report_metadata(lines: list[str]) -> dict:
    """Pull as-at date, GL control total and out-of-balance from the report."""
    meta: dict = {"as_of": None, "control": None, "out_of_balance": None,
                  "title": None}
    for ln in lines[:8]:
        if "Reconciliation" in ln or "Aged" in ln or "Receivables" in ln or "Payables" in ln:
            if meta["title"] is None and not ln.startswith("Created:"):
                meta["title"] = ln.split(",")[0].strip()
        m = ASOF_RE.search(ln)
        if m:
            meta["as_of"] = parse_date(m.group(1))
    # Footer values can appear in any trailing column.
    for ln in lines[-15:]:
        row = next(csv.reader([ln])) if ln.strip() else []
        vals = [c for c in row if c.strip()]
        if not vals:
            continue
        if CONTROL_RE.search(ln) and len(vals) >= 2:
            meta["control"] = money(vals[-1])
        if OOB_RE.search(ln) and len(vals) >= 2:
            meta["out_of_balance"] = money(vals[-1])
    return meta


def parse_open_items(path: Path, default_days: int,
                     terms_map: dict[str, str] | None = None) -> tuple[list[dict], float | None, dict]:
    """Parse a MYOB open-items [Detail] report into flat records."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    hdr_i, amt_i = find_header(lines)
    meta = report_metadata(lines)
    terms_map = terms_map or {}

    records: list[dict] = []
    name: str | None = None
    expect_name = True
    grand: float | None = None

    for raw in lines[hdr_i + 1:]:
        row = next(csv.reader([raw])) if raw.strip() else []
        if not any(c.strip() for c in row):
            continue
        f0 = row[0].strip() if row else ""
        f1 = row[1].strip() if len(row) > 1 else ""

        if "Grand Total" in f1 or "Grand Total" in f0:
            # Grand total sits in the same column as the line amounts.
            grand = money(row[amt_i]) if len(row) > amt_i else None
            break
        if f0 == "" and f1.startswith("Total:"):
            expect_name = True          # customer subtotal -> next name follows
            continue
        if f0 and DATE_RE.match(f1 or ""):
            inv = parse_date(f1)
            terms = terms_map.get((name or "").strip())
            due, quality = due_from_terms(inv, terms, default_days)
            records.append({
                "name": (name or "UNKNOWN").strip(),
                "id": f0,
                "inv": inv,
                "due": due,
                "quality": quality,
                "terms": terms,
                "amt": money(row[amt_i]) if len(row) > amt_i else 0.0,
            })
            continue
        if expect_name:
            name = clean_name(raw, row)
            expect_name = False
        # anything else (card ID, phone, terms line) is ignored here

    return records, grand, meta


def build_terms_map(path: Path) -> dict[str, str]:
    """Extract per-contact payment terms from an Aged [Detail] report."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    hdr_i, _ = find_header(lines)
    terms: dict[str, str] = {}
    name: str | None = None
    expect_name = True
    for raw in lines[hdr_i + 1:]:
        row = next(csv.reader([raw])) if raw.strip() else []
        if not any(c.strip() for c in row):
            continue
        f0 = row[0].strip() if row else ""
        f1 = row[1].strip() if len(row) > 1 else ""
        if "Grand Total" in f1:
            break
        if f0 == "" and f1.startswith("Total:"):
            expect_name = True
            continue
        if f0 and DATE_RE.match(f1 or ""):
            continue
        if expect_name:
            name = clean_name(raw, row)
            expect_name = False
            continue
        if TERMS_RE.match(raw.strip()) and name and name not in terms:
            terms[name] = raw.strip()
    return terms


def build_tax_map(path: Path) -> tuple[dict[str, str], set[str]]:
    """Extract per-invoice MYOB tax codes from a Sales/Purchases [Detail] report.

    The Reconciliation and Aged reports carry no tax column, so a file with
    mixed tax treatment cannot be converted correctly from those alone. The
    Sales [Customer Detail] / Purchases [Supplier Detail] report does carry
    it, one row per invoice LINE.

    Returns (invoice_id -> tax code, set of ids whose lines disagree). An
    invoice with more than one tax code across its lines cannot collapse to
    a single import line and is reported rather than silently flattened.
    """
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    hdr_i = tax_i = None
    for i, ln in enumerate(lines):
        if not ln.startswith("ID No."):
            continue
        cols = [c.strip().lower() for c in next(csv.reader([ln]))]
        if "tax" in cols:
            hdr_i, tax_i = i, cols.index("tax")
        break
    if hdr_i is None or tax_i is None:
        return {}, set()

    seen: dict[str, set[str]] = {}
    for raw in lines[hdr_i + 1:]:
        row = next(csv.reader([raw])) if raw.strip() else []
        if len(row) <= tax_i:
            continue
        inv_id, code = row[0].strip(), row[tax_i].strip()
        if not inv_id or not code or inv_id.startswith(","):
            continue
        if DATE_RE.match(inv_id) or inv_id.lower().startswith("total"):
            continue
        seen.setdefault(inv_id, set()).add(code)

    mixed = {k for k, v in seen.items() if len(v) > 1}
    return {k: sorted(v)[0] for k, v in seen.items()}, mixed


# --------------------------------------------------------------------------- #
# output                                                                      #
# --------------------------------------------------------------------------- #

def write_xero_csv(path: Path, rows: list[dict], amount_fn, description: str,
                   account_code: str, tax_fn) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(XERO_COLS)
        for r in rows:
            d = {c: "" for c in XERO_COLS}
            d.update({
                "*ContactName": r["name"],
                "*InvoiceNumber": r["id"],
                "*InvoiceDate": r["inv"].strftime("%d/%m/%Y"),
                "*DueDate": r["due"].strftime("%d/%m/%Y"),
                "*Description": description,
                "*Quantity": "1",
                "*UnitAmount": f"{amount_fn(r):.2f}",
                "*AccountCode": account_code,
                "*TaxType": tax_fn(r),
            })
            w.writerow([d[c] for c in XERO_COLS])


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--report", type=Path, required=True,
                   help="MYOB Receivables/Payables [Detail] export (CSV/TXT)")
    p.add_argument("--side", choices=["AR", "AP"], default="AR",
                   help="AR = sales invoices (default), AP = supplier bills")
    p.add_argument("--out", type=Path, required=True, help="output directory")
    p.add_argument("--terms-report", type=Path, default=None,
                   help="Aged [Detail] report, used only to read payment terms")
    p.add_argument("--tax-report", type=Path, default=None,
                   help="Sales [Customer Detail] / Purchases [Supplier Detail] "
                        "report, read for PER-INVOICE tax codes. Strongly "
                        "recommended: the Reconciliation and Aged reports carry "
                        "no tax column, so without this every line gets "
                        "--tax-type, which is wrong for any client with mixed "
                        "GST treatment.")
    p.add_argument("--account-code", default="200",
                   help="Xero account code for every line (default: %(default)s)")
    p.add_argument("--tax-type", default="GST on Income",
                   help="Xero tax type (default: %(default)s; "
                        "use 'GST on Expenses' for AP)")
    p.add_argument("--default-terms", type=int, default=14,
                   help="fallback due-date days when terms are unknown "
                        "(default: %(default)s)")
    p.add_argument("--force", action="store_true",
                   help="continue even if the reconciliation gate fails")
    p.add_argument("--json-summary", type=Path, default=None,
                   help="also write a machine-readable summary. This is the "
                        "conformance contract: any other implementation of this "
                        "conversion should be able to emit the same shape and be "
                        "checked by templates/conformance/run_conformance.py")
    args = p.parse_args(argv)

    if not args.report.exists():
        print(f"ERROR: report not found: {args.report}", file=sys.stderr)
        return 1

    terms_map = {}
    if args.terms_report and args.terms_report.exists():
        terms_map = build_terms_map(args.terms_report)

    tax_map: dict[str, str] = {}
    mixed_tax: set[str] = set()
    if args.tax_report and args.tax_report.exists():
        tax_map, mixed_tax = build_tax_map(args.tax_report)

    records, grand, meta = parse_open_items(args.report, args.default_terms, terms_map)
    if not records:
        print("ERROR: no open items parsed — wrong report type?", file=sys.stderr)
        return 1

    # Resolve a Xero tax type per line.
    xero_map = TAX_MAP_AR if args.side == "AR" else TAX_MAP_AP
    unmapped: Counter = Counter()
    for r in records:
        code = tax_map.get(r["id"])
        r["myob_tax"] = code
        if code is None:
            r["tax_type"] = args.tax_type      # no per-line data available
        elif code in xero_map:
            r["tax_type"] = xero_map[code]
        else:
            r["tax_type"] = args.tax_type
            unmapped[code] += 1
    codes_seen = Counter(r["myob_tax"] for r in records if r["myob_tax"])

    pos = [r for r in records if r["amt"] > 0]
    neg = [r for r in records if r["amt"] < 0]
    total = sum(r["amt"] for r in records)
    contacts = len({r["name"] for r in records})

    label = "invoices" if args.side == "AR" else "bills"
    as_of = meta["as_of"].strftime("%d/%m/%Y") if meta["as_of"] else "unknown"

    print("=" * 68)
    print(f"  {meta['title'] or args.report.name}")
    print(f"  As at {as_of}   ({args.side})")
    print("=" * 68)
    print(f"  Open {label:<24} {len(pos):>6}   ${sum(r['amt'] for r in pos):>15,.2f}")
    print(f"  Credit notes (negative)      {len(neg):>6}   ${sum(r['amt'] for r in neg):>15,.2f}")
    print(f"  {'Net':<28} {len(records):>6}   ${total:>15,.2f}")
    print(f"  Distinct contacts            {contacts:>6}")
    print("-" * 68)

    # ---- Gate 1: our output vs the report's own Grand Total ----
    ok_self = True
    if grand is not None:
        diff = total - grand
        ok_self = abs(diff) < 0.005
        print(f"  Report Grand Total             ${grand:>15,.2f}")
        print(f"  Difference vs this import      ${diff:>15,.2f}   "
              f"{'PASS' if ok_self else 'FAIL'}")
    else:
        print("  Report Grand Total             (not found — cannot self-check)")

    # ---- Gate 2: MYOB's own subledger-vs-GL out of balance ----
    ok_gl = True
    oob = meta["out_of_balance"]
    if oob is not None:
        ok_gl = abs(oob) < 0.005
        print(f"  MYOB Out of Balance (vs GL)    ${oob:>15,.2f}   "
              f"{'PASS' if ok_gl else 'FAIL'}")
    else:
        print("  MYOB Out of Balance            (not on this report — run the")
        print("                                  Reconciliation [Detail] to check)")

    # ---- Gate 3: tax treatment is known, not assumed ----
    ok_tax = True
    if not tax_map:
        ok_tax = False
        print("-" * 68)
        print("  Tax codes                      NOT VERIFIED")
        print(f"    No --tax-report supplied, so every line was set to")
        print(f"    '{args.tax_type}'. That is only correct if the client's")
        print("    sales are uniformly GST. Supply the Sales [Customer Detail]")
        print("    report to resolve tax codes per invoice.")
    else:
        summary = ", ".join(f"{c}x{n}" for c, n in codes_seen.most_common())
        resolved = sum(1 for r in records if r["myob_tax"])
        print("-" * 68)
        print(f"  Tax codes found                {summary}")
        print(f"  Tax coverage                   {resolved}/{len(records)} lines")
        if resolved < len(records):
            ok_tax = False
            missing = len(records) - resolved
            print(f"  Lines with NO tax code         {missing}   FAIL")
            print("    The tax report does not cover every open item — it is")
            print("    usually date-limited (e.g. 'July 2025 To June 2026') while")
            print("    open items can be far older. Re-run it over a date range")
            print("    wide enough to cover the oldest open item, or those lines")
            print(f"    silently default to '{args.tax_type}'.")
        if len(codes_seen) > 1:
            print("    Mixed GST treatment — resolved per invoice from the tax")
            print("    report. Verify a sample of the non-GST lines.")
        if unmapped:
            ok_tax = False
            print(f"  Unmapped MYOB tax codes        "
                  f"{', '.join(sorted(unmapped))}   FAIL")
            print("    These are not in the MYOB->Xero tax map, so they fell back")
            print(f"    to '{args.tax_type}'. Add them to TAX_MAP before importing.")
        if mixed_tax:
            ok_tax = False
            print(f"  Invoices w/ mixed tax lines    {len(mixed_tax)}   FAIL")
            print("    These carry more than one tax code across their lines and")
            print("    cannot collapse to a single import line: "
                  f"{', '.join(sorted(mixed_tax)[:5])}"
                  f"{' ...' if len(mixed_tax) > 5 else ''}")
    print("=" * 68)

    if args.json_summary:
        summary = {
            "side": args.side,
            "as_of": meta["as_of"].isoformat() if meta["as_of"] else None,
            "gate": {
                "passes": bool(ok_self and ok_gl and ok_tax),
                "self_check": bool(ok_self),
                "gl_balance": bool(ok_gl),
                "tax": bool(ok_tax),
                "out_of_balance": oob,
                "grand_total": grand,
                "parsed_total": round(total, 2),
            },
            "totals": {
                "invoice_count": len(pos),
                "invoice_total": round(sum(r["amt"] for r in pos), 2),
                "credit_count": len(neg),
                "credit_total": round(sum(r["amt"] for r in neg), 2),
                "net_total": round(total, 2),
                "contacts": contacts,
            },
            "tax": {
                "codes": dict(codes_seen),
                "coverage": sum(1 for r in records if r["myob_tax"]),
                "unmapped": sorted(unmapped),
                "mixed_invoices": sorted(mixed_tax),
            },
            "lines": [
                {
                    "id": r["id"],
                    "contact": r["name"],
                    "amount": round(abs(r["amt"]), 2),
                    "route": "credit" if r["amt"] < 0 else "invoice",
                    "invoice_date": r["inv"].strftime("%d/%m/%Y"),
                    "due_date": r["due"].strftime("%d/%m/%Y"),
                    "due_quality": r["quality"],
                    "tax_type": r.get("tax_type"),
                }
                for r in sorted(records, key=lambda r: r["id"])
            ],
        }
        args.json_summary.parent.mkdir(parents=True, exist_ok=True)
        args.json_summary.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    if not (ok_self and ok_gl and ok_tax):
        print()
        print("  RECONCILIATION GATE FAILED.")
        if not ok_gl:
            print(f"  The {args.side} subledger does not agree with the general ledger")
            print("  control account in MYOB. Fix this in MYOB before converting —")
            print("  converting an out-of-balance file moves the problem into Xero")
            print("  where it is much harder to trace.")
        if not ok_self:
            print("  Parsed total does not equal the report's Grand Total, so some")
            print("  lines were not captured. Do not import this file.")
        if not ok_tax:
            print("  Tax treatment is unverified or unmappable. Importing now")
            print("  risks a wrong first Activity Statement out of Xero.")
        if not args.force:
            print("\n  No files written. Re-run with --force to override.")
            return 2
        print("\n  --force given: writing files anyway. Do not import without review.")
        forced = True
    else:
        forced = False

    args.out.mkdir(parents=True, exist_ok=True)
    stem = "open_invoices" if args.side == "AR" else "open_bills"
    conv = meta["as_of"].strftime("%Y%m%d") if meta["as_of"] else "undated"
    desc = f"Balance brought forward from MYOB at conversion {as_of}"

    tax_fn = lambda r: r.get("tax_type") or args.tax_type
    inv_path = args.out / f"xero_{stem}_{conv}.csv"
    write_xero_csv(inv_path, sorted(pos, key=lambda r: (r["name"], r["inv"])),
                   lambda r: r["amt"], desc, args.account_code, tax_fn)

    files = [inv_path]
    if neg:
        cr_path = args.out / f"xero_credit_notes_{stem}_{conv}_REVIEW.csv"
        write_xero_csv(cr_path, sorted(neg, key=lambda r: r["amt"]),
                       lambda r: abs(r["amt"]), desc, args.account_code, tax_fn)
        files.append(cr_path)

    q = Counter(r["quality"] for r in pos)
    cutoff = date(meta["as_of"].year - 2, meta["as_of"].month, meta["as_of"].day) \
        if meta["as_of"] else None
    old = [r for r in pos if cutoff and r["inv"] < cutoff]

    print()
    print("  Written:")
    for f in files:
        print(f"    {f}")
    print()
    print(f"  Due dates: {q.get('terms', 0)} from terms, "
          f"{q.get('eom-assumed', 0)} end-of-month assumed, "
          f"{q.get('default', 0)} defaulted to {args.default_terms} days")
    if neg:
        print(f"  {len(neg)} credit note(s) split out — import via Xero's Credit "
              f"Notes import, not the {label} import.")
    if old:
        print(f"  {len(old)} item(s) older than 2 years — review collectability "
              f"before converting.")
    print(f"  AccountCode is '{args.account_code}' on every line — confirm this "
          f"matches\n    your conversion method before importing.")
    if forced:
        print()
        print("  NOTE: written with --force past a FAILED gate. Exit code 3 marks")
        print("  this run as needing review, so a batch across many client files")
        print("  can tell it apart from a clean conversion.")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
