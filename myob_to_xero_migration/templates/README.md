# Templates & helpers

Reusable assets shared across every client migration.

| Folder | Contents |
| ------ | -------- |
| `xero_csv_templates/` | Header-row-only CSVs matching Xero's import schemas. Copy these into Stage 02 subfolders before populating. |
| `checklists/` | Working checklists: `myob_file_readiness.md` (pre-export gate), `tax_code_mapping.md`, `account_type_mapping.md`, `preflight_checklist.md`. |
| `scripts/` | `validate_xero_csv.py` (Stage-02 header validator) and `post_upload_acceptance_check.py` (Stage-04 automated TB-diff acceptance gate). |

> Header rows in `xero_csv_templates/` reflect Xero's published import
> formats (AU region). If Xero updates a template, refresh the file here
> and bump the change log in `INDEX.md`.
