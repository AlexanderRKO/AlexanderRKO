# LMS Advisory — Interactive Tax Questionnaire

A self-contained, dependency-free replacement for the Paperform **"New Client
Questionnaire — Tax Preparation"** (the commencement/onboarding step of the
process). Drops into a WordPress page (or any site) via an auto-resizing iframe
and produces submissions that staff can **copy into Xero with single clicks**.

The question set in `schema.js` mirrors the live Paperform (v2026.01.25). The
same engine can host the Existing Client questionnaire too — just swap `schema.js`.

## What's here

| File | Purpose |
|------|---------|
| `index.html` | The client-facing form (the page you embed). |
| `schema.js` | **Every question**, in plain editable form. Non-developers edit this. |
| `config.js` | Endpoint, branding, upload limit. |
| `app.js` | The form engine (wizard, conditional logic, validation, autosave). |
| `styles.css` | Styling — LMS brand (navy/orange, Georgia). |
| `results.html` + `results.js` | **Staff view** — one-click copy on every field + a Xero contact card. |
| `server/submit-handler.js` | Reference backend: emails the team + upserts a Xero contact. |
| `INSTALL-WORDPRESS.md` | Plain-English WordPress setup guide. |
| `LMS-Questionnaire-WordPress-Setup.docx` | The same guide as a branded Word document. |

## Key features

- **Multi-step wizard** with progress bar — far less daunting than one long page.
- **Conditional questions** — e.g. "Own a rental property? → Yes" reveals the
  rental-summary question; "Sole trader? → Yes" reveals the ABN field; any
  "Other" selection reveals a "please specify" box.
- **Validation** — Australian mobile, email, BSB, account number, ABN, required
  fields, and the four mandatory legal acknowledgements. On error, focus jumps to
  the first problem field.
- **Accessibility** — proper `<label for>` associations, `aria-required`,
  `aria-invalid`, `aria-describedby`, and `role="radiogroup"` on choice groups.
- **Autosave** — progress is kept in the browser so clients can finish later.
- **Review step** before submitting.
- **LMS branding** — official navy (`#002555`, PMS 7463) and orange (`#ED8B00`,
  PMS 144C), Georgia typeface, logo mark, and the firm-name footer applied per the
  LMS brand guidelines. Voice/spelling follows the LMS brand-voice skill (AU English).
- **Staff results view** with click-to-copy on every field, a Print/PDF action,
  and a Xero-shaped "Add Contact" card (Contact name, First/Last name, Email,
  Mobile, Date of birth, Postal address, Occupation, Account name, BSB, Account
  number), plus "Copy full contact block".

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

## Embedding in WordPress (recommended approach)

**Recommendation: host the form as static files and embed it with an auto-resizing
iframe in a Custom HTML block.** This isolates the form from your theme's and
plugins' global CSS/JavaScript (WordPress themes have aggressive styles that would
otherwise fight the form's design), needs no plugin, and updates independently of
the site.

Steps:

1. Upload the `tax_questionnaire/` folder to your hosting (via cPanel File Manager
   or FTP), e.g. to `https://www.lmsadvisory.com.au/tax/`. (A subdomain such as
   `forms.lmsadvisory.com.au` also works and keeps it off the main install.)
2. On the page where the form should appear, add a **Custom HTML** block (Gutenberg)
   — or an **HTML widget** in Elementor/Divi/WPBakery — and paste:

   ```html
   <iframe id="lms-tax-form" src="https://www.lmsadvisory.com.au/tax/index.html"
           title="Tax Questionnaire" loading="lazy"
           style="width:100%;border:0;min-height:900px;overflow:hidden"></iframe>
   <script>
     window.addEventListener("message", function (e) {
       if (e.data && e.data.type === "lms-form-height") {
         document.getElementById("lms-tax-form").style.height = e.data.height + "px";
       }
     });
   </script>
   ```

   The form reports its height as clients move through the steps, so the iframe
   grows/shrinks with no inner scrollbar.

3. Keep **`results.html` private** — it's staff-only. Put it behind your client/staff
   login, at an unguessable path, or restrict by IP, and add `noindex`. Don't link
   to it publicly.

Alternatives, if you'd rather not host static files: a small custom plugin exposing
a `[lms_tax_form]` shortcode, or pasting the markup inline — but both invite theme
CSS conflicts and more maintenance, so the iframe is the cleaner choice.

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
