# Templates & helpers

Reusable assets shared across every client migration.

| Folder | Contents |
| ------ | -------- |
| `xero_csv_templates/` | Header-row-only CSVs matching Xero's import schemas. Copy these into Stage 02 subfolders before populating. |
| `checklists/` | Working checklists (tax-code mapping, account-type mapping, sign-off forms). |
| `scripts/` | Pre-flight validators and small helpers (Python). |

> Header rows in `xero_csv_templates/` reflect Xero's published import
> formats (AU region). If Xero updates a template, refresh the file here
> and bump the change log in `INDEX.md`.
