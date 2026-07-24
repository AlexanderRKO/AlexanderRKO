# MYOB → Xero tax code mapping (AU)

Default mapping for an AU GST-registered entity. Confirm with the client
before mass-applying, and override per-transaction where required.

| MYOB tax code | MYOB description | Xero tax rate (name) | Notes |
| ------------- | ---------------- | -------------------- | ----- |
| GST | Goods & Services Tax (10%) | GST on Income / GST on Expenses | Pick based on debit/credit side |
| FRE | GST-Free | GST Free Income / GST Free Expenses | Confirm side |
| ITS | Input Taxed Sales | Input Taxed | |
| INP | Input Taxed Purchases | GST on Expenses (deny if non-deductible) | Confirm with client |
| EXP | Export Sales | GST Free Exports | |
| CAP | Capital Acquisition | GST on Capital | |
| GNR | GST Not Registered | BAS Excluded | |
| N-T | Not Reportable | BAS Excluded | |
| GW | GST on Imported Goods | GST on Imports | Used at customs entry |
| WET | Wine Equalisation Tax | (custom – confirm) | Special-purpose entities only |
| LCT | Luxury Car Tax | (custom – confirm) | Auto dealers only |

## Verification

- After applying, run the Stage-02 validator
  (`../scripts/validate_xero_csv.py`) — it will flag any tax rate the
  importer does not recognise.
- Cross-check the GST control totals: sum of GST-on-Income minus
  GST-on-Expenses for the period should equal the MYOB GST control
  account movement.
