# LMS Advisory — Interactive Tax Questionnaire

A self-contained, dependency-free replacement for the Paperform "Existing Client
Tax Questionnaire". Drops into any website (plain HTML, React, Squarespace embed,
etc.) and produces submissions that staff can **copy into Xero with single clicks**.

## What's here

| File | Purpose |
|------|---------|
| `index.html` | The client-facing form (the page you embed). |
| `schema.js` | **Every question**, in plain editable form. Non-developers edit this. |
| `config.js` | Endpoint, branding, upload limit. |
| `app.js` | The form engine (wizard, conditional logic, validation, autosave). |
| `styles.css` | Styling (matches the firm's teal/slate look). |
| `results.html` + `results.js` | **Staff view** — one-click copy on every field + a Xero contact card. |
| `server/submit-handler.js` | Reference backend: emails the team + upserts a Xero contact. |

## Key features

- **Multi-step wizard** with progress bar — far less daunting than one long page.
- **Conditional questions** — e.g. "Own a rental property? → Yes" reveals the
  rental-summary question; "Sole trader? → Yes" reveals the ABN field.
- **Validation** — Australian mobile, BSB, account number, ABN, required fields,
  and the four mandatory legal acknowledgements.
- **Autosave** — progress is kept in the browser so clients can finish later.
- **Review step** before submitting.
- **Staff results view** with click-to-copy on every field and a Xero-shaped
  "Add Contact" card (Contact name, First/Last name, Mobile, Account name, BSB,
  Account number, Occupation), plus "Copy full contact block".

## Quick start (preview locally)

Open `index.html` in a browser. With no endpoint configured it runs in **demo
mode**: it validates, then shows a success screen with a link to the staff
results view (`results.html`) populated from your test submission.

## Going live

1. **Host the files** anywhere static (your site, S3, Netlify…). They're just
   HTML/CSS/JS — no build step.
2. **Embed** on your site, either inline:
   ```html
   <iframe src="/tax/index.html" style="width:100%;border:0;min-height:900px"
           title="Tax Questionnaire"></iframe>
   ```
   …or by copying the `<main class="app">` block and the three `<script>` tags
   into an existing page (React: render `index.html`'s body inside a component,
   or load it as a route — the engine is plain DOM and needs no framework).
3. **Wire up submissions**: deploy `server/submit-handler.js` (Express or a
   serverless function) and set `submitEndpoint` in `config.js` to its URL.
4. **Configure the backend** via environment variables (see the top of
   `server/submit-handler.js`): SMTP for email, optional Xero credentials, and
   `RESULTS_URL` (the public URL of `results.html`) so the notification email
   includes a one-click "open in staff view" link.

## How the copy-to-Xero flow works

1. Client submits → backend emails your team a formatted summary **and** a link
   like `results.html?d=<encoded answers>`.
2. Staff open that link → the **Xero · Add Contact** card shows each field as a
   clickable tile. Click a tile to copy that value; paste it into the matching
   box in Xero's New Contact form. "Copy full contact block" copies all the
   contact fields at once.

## Note on Xero

Xero has no "tax questionnaire" object, and contact **creation** requires the
`accounting.contacts` (read+write) OAuth scope. So Xero realistically holds the
*client contact* only (name, phone, refund account). The full Q&A lives in the
email and the results view. The handler's `upsertXeroContact()` is provided as a
working starting point but is **disabled by default** (`XERO_ENABLED=false`) —
turn it on once you've set up a Xero app with write scope and a durable place to
store the rotating refresh token.

## Editing questions

Open `schema.js`. Each question is an object with `id`, `type`, `label`,
optional `help`, `required`, `options`, `validate`, and `showIf` (for
conditional display). Add, remove, reorder, or reword freely. Keep `id` values
stable once live so existing submissions stay readable.

## Future integrations

XPM, FYI Docs and PM Hub can be added later by extending `processSubmission()`
in the handler (push a job/document via their APIs) — the structured `answers`
payload is integration-ready.
