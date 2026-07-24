# Standalone edition — one HTML file, no WordPress

The questionnaire doesn't need WordPress (or any framework, or a build step) to
run. This guide turns it into a **single, self-contained `.html` file** you can
host anywhere, share, or open straight off disk.

## The two bundled files

Run the bundler whenever you've changed the questions or styling:

```bash
node build-standalone.js
```

It writes to `standalone/`:

| File | What it is |
|------|------------|
| `lms-new-client-questionnaire.html` | The **client form** — one file, ~60 KB, everything inlined. |
| `lms-questionnaire-results.html` | The **staff results view** (keep this private). |

Each file has the styles, configuration, questions and engine baked in — no
separate `.css`/`.js` to upload, nothing to install. Double-click to open it in a
browser and it just works (in demo mode).

## Where to host it (pick one)

You only need somewhere that serves a static file over HTTPS.

1. **Free static host (simplest).**
   - **Netlify Drop** — drag the `standalone` folder onto <https://app.netlify.com/drop>; you get a URL in seconds.
   - **Cloudflare Pages**, **GitHub Pages**, or **Vercel** — connect this repo (or upload the file) and publish. All free for this.
2. **Your own subdomain.** Put the file on your existing hosting at e.g.
   `https://forms.lmsadvisory.com.au/` or `https://www.lmsadvisory.com.au/tax/`.
   This keeps it on your domain for trust and branding.
3. **Internal / offline use.** Because it's one file, you can email it to a client,
   keep it on a shared drive, or run it from a USB stick. (Submissions still need
   an internet connection — see below.)

Link to the form from your website with a normal button/menu item, or send the
URL directly to clients. No iframe required.

## Making submissions work (still needed, server-optional)

The single file handles everything *except* delivering the answers — that always
needs an endpoint. Set `submitEndpoint` (in `config.js`, then rebuild) to one of:

- **Your own backend** — deploy `server/submit-handler.js` (email + Xero). Best
  control; see `INSTALL-WORDPRESS.md` Step 4.
- **A no-server form service** — for a truly server-free setup, point it at a
  form-to-email service such as **Formspree**, **Basin** or **Formspark**. They
  accept the JSON POST and email your team; some add spam filtering and a
  dashboard. Paste their endpoint URL into `submitEndpoint` and you're done.
- **A Zapier/Make webhook** — emails the team and/or appends to a spreadsheet,
  no code.

With no endpoint set, the form runs in **demo mode**: it validates and shows the
staff-preview link, but doesn't send anything — handy for testing.

## Editing the questions

Two options:

- **Recommended:** edit `schema.js` (and `config.js`/`styles.css` if needed), then
  re-run `node build-standalone.js` to regenerate the single file.
- **Quick one-off:** open the built `.html`, find the `const FORM_SCHEMA = {`
  block, and edit it in place. (You'll lose those edits next time you rebuild from
  source, so prefer the first option for anything lasting.)

## Keep the results file private

`lms-questionnaire-results.html` shows client bank details. Don't host it at a
public, linkable URL — put it behind a login, at an unguessable path, or only open
it locally / from the link in the notification email. It already sets `noindex`.
