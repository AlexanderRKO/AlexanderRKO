# 01 — Chart of accounts (CLEANSED for Xero upload)

Two artefacts live here:

1. **`coa_mapping_template.csv`** — the working mapping sheet. One row
   per MYOB account, recording the target Xero code/name/type/tax,
   any merges, and the decision owner. **Do not skip this step** even
   if the client wants a like-for-like CoA — the mapping sheet is the
   audit trail.
2. **`xero_chart_of_accounts.csv`** — the final upload file (copy
   `../../templates/xero_csv_templates/xero_chart_of_accounts_template.csv`
   and populate from the mapping sheet).

## Mapping sheet columns

| Column | Purpose |
| ------ | ------- |
| `myob_account_number` | Original MYOB code (`1-1110` etc.) |
| `myob_account_name` | Original MYOB name |
| `myob_type` | MYOB classification (Bank, Asset, Liability, …) |
| `myob_tax_code` | Default tax code on the MYOB account |
| `xero_account_code` | Target Xero code (3–10 chars, unique) |
| `xero_account_name` | Target Xero name |
| `xero_type` | Xero type per `account_type_mapping.md` |
| `xero_tax_rate` | Xero tax rate name per `tax_code_mapping.md` |
| `xero_dashboard` | Show on Xero dashboard (Yes/No) |
| `xero_expense_claims` | Enable for expense claims (Yes/No) |
| `xero_enable_payments` | Enable payments to account (Yes/No) |
| `decision` | `keep` / `rename` / `merge` / `archive` / `new` |
| `merged_into` | If `decision = merge`, target Xero code |
| `owner` | Initials of person who made the call |
| `notes` | Anything that needs context |

## Validation rules

- Every active MYOB account either maps to a Xero account or is
  marked `archive` with a reason.
- Xero codes are unique across the sheet.
- Every `xero_type` value matches the Xero accepted list.
- Every `xero_tax_rate` value matches the Xero standard rate names.
- Merged accounts must have a `merged_into` target that itself exists
  in the sheet.

Run `../../templates/scripts/validate_xero_csv.py xero_chart_of_accounts.csv ../../templates/xero_csv_templates/xero_chart_of_accounts_template.csv`
before promoting.
