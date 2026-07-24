# Pre-upload preflight checklist

Tick every item before pushing a cleansed file from Stage 02 into Xero.

## File hygiene
- [ ] File name matches `<entity>_<scope>_<YYYYMMDD>.csv`.
- [ ] Encoding is UTF-8, comma-delimited, no BOM issues.
- [ ] Header row matches the Xero template **exactly** (column order
      and asterisks where Xero marks required).
- [ ] No empty trailing rows / hidden columns.

## Data integrity
- [ ] Row count == row count of source export (or with documented
      delta for de-duplication).
- [ ] Control total (sum of relevant amount column) matches source.
- [ ] Dates in `DD/MM/YYYY`.
- [ ] All account codes appear in the uploaded chart of accounts.
- [ ] All tax rates are valid Xero rate names (see
      `tax_code_mapping.md`).
- [ ] All contact names already exist in Xero (or are in the same upload).

## Sign-off
- [ ] Stage-02 column in `INDEX.md` is ticked.
- [ ] Validator log saved to `02_cleansed_for_xero/_validation_logs/`.
- [ ] Reviewer's initials on the row.
