# Conversion conformance suite

A set of fixtures that any MYOB → Xero open-items converter must satisfy,
whatever language it is written in. The point is to stop two
implementations of the same conversion drifting apart, which is how a
safety check ends up existing in one place and not the other.

```
python templates/conformance/run_conformance.py
python templates/conformance/run_conformance.py --case 03_mixed_tax -v
python templates/conformance/run_conformance.py --adapter "node dist/convert.js"
```

Exit code is 0 only if every case passes.

## Why the fixtures are synthetic

Real debtor data is client data and never belongs in a repository. These
fixtures reproduce the structural quirks that actually break converters —
without a single real name or amount.

## What each case defends against

| Case | The failure it catches |
| ---- | ---------------------- |
| `01_clean_ar` | Contact names containing a comma (MYOB quotes them, naive parsers keep the quotes or split the name). End-of-month terms resolving to the wrong month. Credit notes routed into the invoice file. |
| `02_out_of_balance` | The big one. The subledger disagrees with the general-ledger control account, and the converter writes files anyway. An out-of-balance file converted is an out-of-balance file you now have to trace inside Xero. |
| `03_mixed_tax` | Assuming one tax type for the whole file. Real clients have GST, FRE, EXP and N-T side by side, and an invoice whose lines carry different codes cannot collapse to a single import line at all. |
| `04_ap_bills` | Mapping payables tax codes to the income side of the Xero tax list. |
| `05_aged_layout` | Hard-coding the `Total Due` column index. It sits in a different position in the Aged and Reconciliation layouts, so parsing must key off the header row. |

## The contract

An implementation conforms if it accepts these flags and writes the JSON
summary below. The runner drives it through a command line and compares
against each case's `expected.json`.

**Flags**

| Flag | Meaning |
| ---- | ------- |
| `--report PATH` | the MYOB Reconciliation or Aged `[Detail]` export |
| `--side AR\|AP` | receivables (sales invoices) or payables (bills) |
| `--out DIR` | where the Xero CSVs are written |
| `--json-summary PATH` | where the summary below is written |
| `--terms-report PATH` | optional; Aged `[Detail]`, read for payment terms |
| `--tax-report PATH` | optional; Sales/Purchases `[Detail]`, read for per-invoice tax codes |
| `--tax-type STR` | fallback Xero tax type when no per-line code is available |
| `--default-terms N` | fallback due-date days when terms are unknown |
| `--force` | write files even though the gate failed |

**Exit codes**

| Code | Meaning |
| ---- | ------- |
| `0` | gate passed, files written |
| `2` | gate failed, nothing written |
| `3` | gate failed but `--force` given, files written and flagged for review |

Code `3` matters when batching across a client book: it separates a clean
conversion from one somebody pushed through.

**JSON summary shape**

```jsonc
{
  "side": "AR",
  "as_of": "2026-06-30",
  "gate": {
    "passes": true,          // all three checks below
    "self_check": true,      // parsed total == the report's own Grand Total
    "gl_balance": true,      // MYOB's "Out of Balance Amount" is zero
    "tax": true,             // tax treatment resolved, mapped and complete
    "out_of_balance": 0.0,
    "grand_total": 4015.00,
    "parsed_total": 4015.00
  },
  "totals": {
    "invoice_count": 4, "invoice_total": 4180.00,
    "credit_count": 1,  "credit_total": -165.00,
    "net_total": 4015.00, "contacts": 3
  },
  "tax": {
    "codes": { "GST": 5 },      // MYOB code -> line count
    "coverage": 5,              // lines with a resolved code
    "unmapped": [],             // MYOB codes with no Xero equivalent
    "mixed_invoices": []        // invoice ids whose lines disagree
  },
  "lines": [                    // sorted by id
    {
      "id": "INV1001",
      "contact": "Alpha Holdings Pty Ltd",
      "amount": 1100.00,        // always positive
      "route": "invoice",       // "invoice" | "credit"
      "invoice_date": "30/06/2026",
      "due_date": "30/07/2026",
      "due_quality": "eom-assumed",  // "terms" | "eom-assumed" | "default"
      "tax_type": "GST on Income"
    }
  ]
}
```

## Rules a conforming implementation must follow

These are the ones that are easy to get wrong and expensive to discover
late:

1. **Amounts are the balance still owing**, never the original invoice
   value. Part-paid invoices otherwise overstate debtors.
2. **Credit notes go to a separate file.** Xero's invoice and bill imports
   reject negative amounts; credits import through their own screen.
   `amount` is reported positive with `route: "credit"`.
3. **The gate refuses by default.** Failing closed is the whole point;
   `--force` exists so the override is deliberate and recorded.
4. **Tax coverage is checked, not assumed.** The tax report is usually
   date-limited while open items can be years old, so partial coverage is
   a failure, not a pass.
5. **Money is decimal, not binary floating point.** Totals are compared to
   the cent against a control account, and accumulated float error across
   a few hundred lines can manufacture an out-of-balance that isn't real.
   In JavaScript that means a decimal library or integer cents — not
   `Number`.
6. **Dates are `dd/mm/yyyy`** throughout, in and out. Australian format.

## Adding a case

Create a directory under `cases/` with a `report.txt` and an
`expected.json`. Optional `terms.txt` and `tax.txt` are referenced from
the `args` block. Only the keys present in `expect` are checked, so a case
can assert as much or as little as it needs.

When a real client file breaks a converter, reduce it to the smallest
synthetic report that reproduces the break and add it here. That way the
bug stays fixed in every implementation, not just the one you patched.
