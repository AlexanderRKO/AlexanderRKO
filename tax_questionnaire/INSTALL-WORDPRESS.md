# Adding the Tax Questionnaire to your WordPress site

A step-by-step guide for getting the LMS Advisory questionnaire onto
`lmsadvisory.com.au`. No coding required — you'll upload a folder, then paste a
small snippet into a page. Allow about 30 minutes.

> **Approach:** we host the questionnaire as plain files and show it on your page
> inside an auto-resizing **iframe**. This keeps it completely separate from your
> WordPress theme and plugins, so a theme update or plugin can never break it,
> and it looks identical no matter which page builder you use.

---

## What you'll need

- Access to your website hosting (one of: **cPanel**, or **FTP** details, or your
  web developer who can do the upload).
- Access to **WordPress admin** (wp-admin) as an Administrator or Editor.
- The `tax_questionnaire` folder from this project (the files: `index.html`,
  `app.js`, `schema.js`, `config.js`, `styles.css`, `results.html`,
  `results.js`, and the `server` folder).

---

## Step 1 — Upload the questionnaire files to your hosting

You're putting the files in a folder so they're reachable at
`https://www.lmsadvisory.com.au/tax/`.

### Option A — cPanel File Manager (easiest)

1. Log in to your hosting **cPanel**.
2. Open **File Manager**.
3. Go into the **`public_html`** folder (this is your website's root).
4. Click **+ Folder** and create a folder called **`tax`**.
5. Open the new `tax` folder, click **Upload**, and upload these files:
   - `index.html`, `app.js`, `schema.js`, `config.js`, `styles.css`,
     `results.html`, `results.js`
   - (Optional) the `server` folder — only needed when you wire up email/Xero
     in Step 4. It is **not** served to the public.
6. When done, visit **`https://www.lmsadvisory.com.au/tax/index.html`** in a
   browser. You should see the questionnaire. (It will say it's in "demo mode"
   until Step 4 — that's expected.)

### Option B — FTP (e.g. FileZilla)

1. Connect to your server with your FTP details.
2. Navigate to **`public_html`** (or your site's web root).
3. Create a folder called **`tax`** and upload the same files listed above into it.
4. Test the URL as in Option A, step 6.

> **Tip:** If your hosting blocks `.html` or the folder shows a "403 Forbidden",
> see **Troubleshooting** at the bottom.

---

## Step 2 — Put the form on a WordPress page

1. In **wp-admin**, go to **Pages → Add New** (or edit an existing page such as
   "Tax Return Questionnaire").
2. Give the page a title, e.g. *New Client Tax Questionnaire*.
3. Add a **Custom HTML** block:
   - Click the **+** to add a block, search for **"Custom HTML"**, and select it.
   - *(Using Elementor? Drag in an **HTML** widget. Using Divi? Add a **Code**
     module. WPBakery? A **Raw HTML** element. They all work the same way.)*
4. Paste this snippet into the block exactly as-is:

   ```html
   <iframe id="lms-tax-form"
           src="https://www.lmsadvisory.com.au/tax/index.html"
           title="New Client Tax Questionnaire"
           loading="lazy"
           style="width:100%;border:0;min-height:900px;overflow:hidden"></iframe>
   <script>
     window.addEventListener("message", function (e) {
       if (e.data && e.data.type === "lms-form-height") {
         var f = document.getElementById("lms-tax-form");
         if (f) f.style.height = e.data.height + "px";
       }
     });
   </script>
   ```

5. Click **Preview** to check it. The form should appear and the box should grow
   and shrink as you click through the steps (no inner scrollbar).
6. When happy, **Publish** (or Update) the page.

That's the client-facing form live. 🎉

---

## Step 3 — Keep the staff results page private (important)

`results.html` is the **staff** view — it displays client bank details and
personal info, so it must **not** be public or indexed by Google.

Do at least one of these:

- **Don't link to it publicly.** Staff open it only via the link in the
  notification email (see Step 4).
- **Add it to your robots/noindex.** The page already requests no indexing, but
  you can also block `/tax/results.html` in your SEO plugin or `robots.txt`.
- **Best: put it behind a login.** Ask your developer/host to password-protect
  `results.html` (e.g. cPanel **Directory Privacy**, an `.htpasswd` rule, or move
  it to a staff-only subdomain). Then only your team can open it.

> The client form (`index.html`) is fine to be public. Only `results.html` needs
> protecting.

---

## Step 4 — Make submissions go somewhere (email + Xero)

Until this step, the form runs in **demo mode**: it validates and shows a success
screen but doesn't send anything. To receive submissions by email (and optionally
create the Xero contact), you deploy the small handler included in
`server/submit-handler.js`.

This part needs a developer or your IT person — it's ~30 minutes for them:

1. **Deploy `server/submit-handler.js`** as a small Node service or serverless
   function (Vercel, Netlify Functions, AWS Lambda, or a Node app on your host).
   It exposes one URL, e.g. `https://api.lmsadvisory.com.au/tax-questionnaire`.
2. **Set the environment variables** (documented at the top of that file):
   - Email: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `MAIL_FROM`,
     `MAIL_TO` (where submissions are emailed, e.g. `tax@lmsadvisory.com.au`).
   - `RESULTS_URL` = `https://www.lmsadvisory.com.au/tax/results.html` so the
     email includes a one-click "open in staff copy-paste view" link.
   - (Optional, later) the Xero variables — leave `XERO_ENABLED=false` for now.
3. **Point the form at it.** Edit **`config.js`** in the `tax` folder and set:
   ```js
   submitEndpoint: "https://api.lmsadvisory.com.au/tax-questionnaire",
   ```
   Re-upload `config.js`. Done — submissions now email your team.

> You can go live after Steps 1–2 and add Step 4 whenever the endpoint is ready.
> If you'd rather not host a backend at all, a no-code option is to point
> `submitEndpoint` at a Zapier/Make webhook that emails the team and adds a row to
> a spreadsheet. Ask and we'll provide that variant.

---

## Step 5 — Test it end to end

1. Open the page with the form and fill it in as a test client.
2. Submit. In demo mode you'll see a success screen with a "Staff preview" link;
   once Step 4 is wired, your team inbox gets the email instead.
3. Open `results.html` (or the email link) and confirm the **Xero · Add Contact**
   card shows the details, and clicking a tile copies it (paste into Notepad to
   check).

---

## Updating the questions later

Open **`schema.js`** in the `tax` folder, edit the wording/options, save, and
re-upload that one file. No other changes needed — the form rebuilds itself from
the schema. (Keep each question's `id` the same so older submissions stay
readable.)

---

## Troubleshooting

**The form URL shows "403 Forbidden".**
Your security plugin/firewall (e.g. Wordfence, or Cloudflare) may be blocking the
folder. In Wordfence, allow the `/tax/` path; in cPanel, check the folder isn't
set to "deny". Make sure the files were uploaded as files (not zipped).

**The iframe shows a scrollbar / wrong height.**
Confirm you pasted the `<script>` part of the snippet too — that's what resizes
the box. Some caching/optimisation plugins strip inline scripts; if so, add the
listener via a "Custom HTML" block at the bottom of the page or your theme's
footer code area, or disable JS minification for that page.

**"Mixed content" or the form won't load.**
The `src` must be **https** (it is in the snippet). Ensure your whole site is on
HTTPS.

**The form loads but looks unstyled.**
`styles.css` didn't upload, or is in the wrong place. All seven files must sit
together in the same `/tax/` folder.

**A page builder won't keep the code.**
Use that builder's dedicated HTML/Code/Embed element (not a normal text block),
or use a classic Gutenberg page with a Custom HTML block.

---

## Quick reference

| Thing | Value |
|---|---|
| Upload location | `public_html/tax/` |
| Client form URL | `https://www.lmsadvisory.com.au/tax/index.html` |
| Staff results URL (keep private) | `https://www.lmsadvisory.com.au/tax/results.html` |
| Page snippet | Custom HTML block (see Step 2) |
| Change questions | edit `schema.js`, re-upload |
| Turn on email/Xero | deploy `server/submit-handler.js`, set `submitEndpoint` in `config.js` |

Need a hand with any step? We can provide host-specific instructions (e.g. exactly
where this goes for your particular cPanel or page builder).
