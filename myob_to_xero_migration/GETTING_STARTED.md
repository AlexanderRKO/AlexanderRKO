# Getting Started

A practical walk-through for your first MYOB Online → Xero migration
using this toolkit. Plan for ~20 minutes of setup, then the migration
itself runs through five phases over 1–3 weeks depending on the file.

If you only read one other thing, read **`PRIVACY.md`** before you
touch payroll data.

> 📄 **Prefer a visual / printable version?** Run
> `python migration.py guide -o getting_started_visual.pdf` to
> generate a styled 7-page A4 PDF of this guide with a cover diagram,
> coloured callouts, and a one-page cheat sheet. Hand it to new team
> members on day one.

> 🖱 **Don't use a terminal?** Double-click the launcher and skip
> sections 3 and 5 below — the dashboard does everything from the
> browser:
>
> - macOS: `Start Migration Dashboard.command`
> - Windows: `Start Migration Dashboard.bat`
> - Linux: `start_dashboard.sh`
>
> The first run takes ~30 seconds (it creates a virtual environment
> and installs dependencies). After that the dashboard opens in your
> default browser at `http://localhost:8501` whenever you double-click
> the launcher. From there you can: create a new engagement, tick
> artefacts as you complete them, drag-and-drop files into the right
> folders, validate Stage-02 CSVs, run the trial-balance acceptance
> gate, add exceptions, and download all three PDF deliverables.

## 1. What this toolkit is

A folder-based project framework that takes a client's MYOB Online
company file and produces a verified Xero organisation. It enforces a
four-stage pipeline (raw exports → cleansed Xero CSVs → locked source-
of-truth reports → post-upload verification) with privacy guardrails
and an automated trial-balance acceptance gate at the end.

You get:

- A structured folder for every export, cleansed file, and report.
- A CLI (`python migration.py`) for status, scaffolding, validation,
  and the acceptance gate.
- A browser dashboard (`streamlit run dashboard.py`) for the same data.
- A one-page printable PDF for client updates.
- A GitHub Actions workflow that runs the status command on every push.

## 2. Before you start

### Accounts & access

- [ ] Active MYOB Online access to the client's company file
      (Administrator or accountant role).
- [ ] Xero subscription created (or confirmed the existing org to
      convert into).
- [ ] Client written authorisation to perform the migration.
- [ ] Firm-managed encrypted storage location (SharePoint / OneDrive
      / equivalent) ready to host the per-client copy of this toolkit.
- [ ] MFA enabled on MYOB, Xero, email, and the storage account for
      every team member.

### Local environment

- [ ] Python 3.10 or newer (`python --version`).
- [ ] Git (`git --version`).
- [ ] Optional but recommended: a virtual environment.

```bash
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r myob_to_xero_migration/requirements.txt   # for dashboard + PDF
```

The core CLI works with **no** dependencies installed; `requirements.txt`
covers only the optional visual layer (Streamlit dashboard, PDF report).

## 3. First-time setup (≈ 5 minutes)

```bash
cd myob_to_xero_migration

# 1. Fill in the engagement parameters.
python migration.py init \
    --client "Acme Pty Ltd" \
    --abn "12 345 678 901" \
    --conversion-date 2026-07-01 \
    --myob-product "AccountRight Live" \
    --xero-org-target new \
    --gst "Y, quarterly" \
    --payroll "Y, STP Phase 2" \
    --inventory "Y" \
    --lead "J. Smith"

# 2. Confirm it took.
python migration.py status
```

`init` rewrites the engagement-parameter cells in `INDEX.md` and
`PLAN.md`. Use `--dry-run` first if you want to preview the diff.

Then open these three files in your editor and read them once,
top-to-bottom:

1. **`PLAN.md`** — the five phases, the export map, the upload order,
   and the known Xero limitations to brief the client on **before**
   anything else.
2. **`PRIVACY.md`** — the Privacy Act / TFN Rule controls. Tick its
   §8 pre-pull sign-off checklist before pulling any payroll data.
3. **`INDEX.md`** — the live status tracker you'll update as the
   migration progresses.

## 4. Running the migration end-to-end

Five phases, mapped to the four numbered folders.

### Phase A — Discovery & scoping

Talk to the client. Confirm scope, conversion date, GST cycle,
payroll status, and which historical years they need in Xero (versus
keeping only as locked Stage-03 PDFs).

Update the `Authorised migration team` table in `INDEX.md` with the
people who'll touch payroll data and confirm each has MFA on, has
signed the confidentiality undertaking, and has acknowledged
`PRIVACY.md`.

### Phase B — Extract (→ `01_exports_from_myob/`)

**Pre-export gate**: walk through
`templates/checklists/myob_file_readiness.md` inside the MYOB file.
This is non-negotiable — a dirty source file makes everything
downstream unreliable.

Then pull every export listed in `PLAN.md §2` into its matching
sub-folder. Naming convention: `<entity>_<scope>_<YYYYMMDD>.<ext>`.
Tick each row in `INDEX.md §01` as files land.

⚠ **MYOB Business has no CSV export.** If the client is on MYOB
Business (cloud, not AccountRight), you have to copy from each list
screen — chart of accounts, contacts, items. **Do not paste into
Excel as an intermediate step.** Excel auto-converts MYOB codes
like `1-9000` into the date `January 9000` and silently rewrites
them as date serials (in testing this corrupted 157 of 340 codes
in one paste). Instead:

1. Double-click the dashboard launcher.
2. Open the **Paste from MYOB Business** page.
3. Copy from the MYOB Business screen (`Ctrl+A` → `Ctrl+C`).
4. Paste **directly into the textarea** — the dashboard reads the
   clipboard as plain text, so no auto-conversion happens.
5. Click **Parse**, review in the editor, **Save to project**.

The parser handles the MYOB Business "Select row N" clipboard format
natively. If the dashboard flags any codes as date-corrupted, you've
gone through Excel somewhere along the way — re-paste from MYOB
Business directly.

Payroll exports (`04_employees/`, `12_payroll_history/`) need
`PRIVACY.md §8` complete first.

### Phase C — Transform & cleanse (→ `02_cleansed_for_xero/`)

Copy each template from `templates/xero_csv_templates/` into the
matching sub-folder, then populate from the Stage-01 raw exports.

The chart of accounts is the foundation — start there:

```bash
# Work the CoA mapping sheet first
$EDITOR 02_cleansed_for_xero/01_chart_of_accounts/coa_mapping_template.csv

# Then populate the upload file and validate
python migration.py validate \
    02_cleansed_for_xero/01_chart_of_accounts/xero_chart_of_accounts.csv \
    templates/xero_csv_templates/xero_chart_of_accounts_template.csv
```

Repeat per entity. Validator must exit 0 before a file leaves Stage 02.

### Phase D — Reporting & sign-off (→ `03_finalized_reports/`)

Lock the conversion-date Balance Sheet, P&L YTD, Trial Balance, Aged
Receivables, Aged Payables, the last lodged BAS, and Payroll Activity
YTD as PDFs in the matching sub-folders.

**The client signs these off**. Store the signed approval in
`05_sign_off_documents/`. Do not start Phase E without it.

### Phase E — Load & verify (→ `04_xero_post_upload_checks/`)

Upload to Xero in the order in `PLAN.md §3` (settings → CoA → tax →
contacts → items → employees → conversion balances → AR → AP → bank
→ payroll opening → fixed assets → repeating).

After each upload, run the Xero Trial Balance and feed it into the
acceptance gate:

```bash
python migration.py check \
    --myob 03_finalized_reports/01_pre_conversion_snapshots/trial_balance_<date>.csv \
    --xero 04_xero_post_upload_checks/01_account_by_account_checklists/tb_xero_<date>.csv \
    --tolerance 1.00
```

- Exit 0 → all variances ≤ tolerance. Proceed to per-contact and
  bank reconciliations.
- Exit 1 → at least one breach. Investigate and re-upload, or log
  in `05_exception_log/exceptions.csv`.

Track clearing/suspense accounts in
`03_balance_reconciliations/clearing_accounts_tracker.csv`. None may
remain non-zero at sign-off.

Roll the per-account checks, exception resolutions, and gate results
into `06_final_sign_off/action_checklist_template.md` and deliver
that to the client as the consolidated summary.

## 5. The four ways to see status

Same data, picked by audience and friction:

| When | Use | Command |
| ---- | --- | ------- |
| Working in the terminal | CLI dashboard | `python migration.py status` |
| Showing a partner or accountant | Browser dashboard | `streamlit run dashboard.py` |
| Emailing the client a snapshot | One-page PDF | `python migration.py report -o status.pdf` |
| Reviewing on GitHub | CI workflow | runs on every push |

The CLI is the fastest. The Streamlit dashboard is the friendliest
for someone non-technical (open `http://localhost:8501`, click
through pages in the sidebar). The PDF is the cleanest deliverable.

## 6. Daily / weekly rhythm

A simple loop that keeps `INDEX.md` truthful:

1. Pull or transform data into the relevant folder.
2. Update the matching `⬜ todo` row in `INDEX.md` to `🟡 in progress`
   or `🟢 done`.
3. Log anything that didn't reconcile in `exceptions.csv` with
   `area` set to whatever was being worked on.
4. Run `python migration.py status` to see the roll-up.
5. At the end of the week, generate the PDF and send to the partner.

## 7. Troubleshooting & common gotchas

| Symptom | Likely cause | Fix |
| ------- | ------------ | --- |
| Chart of accounts shows dates (`1950-01-01`) where codes should be | The CoA was pasted through Excel; Excel turned codes like `1-9000` into dates | Re-copy from MYOB Business and paste **directly** into the dashboard's "Paste from MYOB Business" page (bypass Excel). The dashboard will refuse to silently ship date-corrupted codes |
| MYOB Business won't let you export the chart of accounts / contacts / items | There is no export button on MYOB Business list screens | Use the dashboard's "Paste from MYOB Business" page — `Ctrl+A` `Ctrl+C` from the MYOB screen, paste straight into the textarea, click Parse, Save to project |
| `validate` fails on header mismatch | Saved as Excel-flavoured CSV with semicolons or BOM | Re-save as UTF-8, comma-delimited |
| Xero rejects the CoA upload | Account `Type` value not in Xero's accepted list | Check `templates/checklists/account_type_mapping.md` |
| Xero rejects an invoice import | Contact name not present in Xero | Upload contacts first; check exact name spelling |
| `check` returns FAIL on one account by exactly the GST amount | Conversion-date GST timing difference | Post a clearing journal; record in clearing tracker |
| Payroll opening balance off for one casual | Casual leave balances aren't carried by the Xero importer | Re-enter manually in Xero; note in Action Checklist §4 |
| Streamlit shows "_TBD_" everywhere | `init` not run yet for this client | `python migration.py init --client …` |
| GitHub Actions PDF artefact missing | Workflow trigger path didn't match | Edit a file under `myob_to_xero_migration/` or run manually via `workflow_dispatch` |
| `status` shows "0/6 clearing accounts" but you've cleared them | Status column in `clearing_accounts_tracker.csv` not yet set to `🟢` or `done` | Update the CSV |

## 8. Where to go next

- `PLAN.md` — the full conversion plan with phase diagrams, export
  map, upload order, and known Xero limitations.
- `PRIVACY.md` — controls for handling employee and payroll data
  (Privacy Act 1988, TFN Rule, NDB scheme).
- `INDEX.md` — your live status tracker, kept current as work
  progresses.
- `templates/checklists/myob_file_readiness.md` — the pre-export
  hygiene gate.
- `templates/checklists/tax_code_mapping.md` — MYOB → Xero tax-rate
  mapping.
- Per-folder `README.md` in each of the four numbered folders — the
  rules and validations specific to that stage.

## 9. Cheat sheet

```bash
# Set up a new engagement
python migration.py init --client "<name>" --conversion-date <YYYY-MM-DD> \
    --xero-org-target new --lead "<your name>"

# See progress
python migration.py status

# Validate a cleansed CSV before uploading to Xero
python migration.py validate <cleansed.csv> templates/xero_csv_templates/<template>.csv

# After uploading to Xero, run the trial-balance acceptance gate
python migration.py check --myob <myob_tb.csv> --xero <xero_tb.csv>

# Make a one-page PDF for the client / partner
python migration.py report -o status_report.pdf

# Open the browser dashboard
streamlit run dashboard.py     # http://localhost:8501
```
