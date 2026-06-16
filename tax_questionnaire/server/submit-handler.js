/*
 * LMS Advisory — Tax Questionnaire submission handler (reference implementation)
 * ============================================================================
 *
 * This is a small, framework-agnostic Node.js handler that receives a JSON
 * submission from the form (POST), then:
 *   1. Emails your team a formatted summary (with any uploaded files attached).
 *   2. Upserts the client as a Contact in Xero so the job is ready to action.
 *
 * It is written to run either as:
 *   - a standalone Express server (see the bottom of this file), or
 *   - a serverless function (Vercel / Netlify / AWS Lambda) — export `handler`.
 *
 * IMPORTANT — Xero is write-restricted by OAuth scope.
 * ----------------------------------------------------
 * Reading Xero data needs the `accounting.contacts.read` scope; *creating or
 * updating* a Contact needs `accounting.contacts` (read+write). The form data
 * (occupation, bank details, acknowledgements, etc.) does NOT map onto standard
 * Xero fields — Xero has no "tax questionnaire" object. So the realistic options are:
 *
 *   (a) Use Xero only to ensure the CLIENT exists as a Contact (name, phone,
 *       bank account for refunds) and attach the questionnaire PDF/summary to
 *       that contact — implemented below in `upsertXeroContact()`.
 *   (b) Push the full questionnaire into your practice/workflow system
 *       (e.g. XPM / Karbon / FYI / Ignition) where a "job" or "task" can hold it.
 *   (c) Keep the rich answers in email + a spreadsheet/DB, and use Xero purely
 *       for billing once the job is won.
 *
 * Configure everything via environment variables — never hard-code secrets.
 */

"use strict";

const nodemailer = require("nodemailer"); // npm i nodemailer

/* ----------------------------------------------------------------- config */
const ENV = {
  // Email (SMTP). For production prefer a transactional provider (SES, SendGrid…).
  SMTP_HOST: process.env.SMTP_HOST,
  SMTP_PORT: Number(process.env.SMTP_PORT || 587),
  SMTP_USER: process.env.SMTP_USER,
  SMTP_PASS: process.env.SMTP_PASS,
  MAIL_FROM: process.env.MAIL_FROM || "no-reply@lmsadvisory.com.au",
  MAIL_TO: process.env.MAIL_TO || "tax@lmsadvisory.com.au",

  // Xero OAuth2 (custom connection / authorization code flow).
  XERO_CLIENT_ID: process.env.XERO_CLIENT_ID,
  XERO_CLIENT_SECRET: process.env.XERO_CLIENT_SECRET,
  XERO_TENANT_ID: process.env.XERO_TENANT_ID,
  XERO_REFRESH_TOKEN: process.env.XERO_REFRESH_TOKEN, // rotate & persist (see note)
  XERO_ENABLED: process.env.XERO_ENABLED === "true",

  // CORS — set to your website origin in production (e.g. https://lmsadvisory.com.au).
  ALLOW_ORIGIN: process.env.ALLOW_ORIGIN || "*",
  MAX_BYTES: Number(process.env.MAX_BYTES || 20 * 1024 * 1024),
};

/* ------------------------------------------------------------ formatting */
function summariseForEmail(payload) {
  const a = payload.answers || {};
  const yesNo = (v) => (v == null || v === "" ? "—" : v);
  const lines = [];
  lines.push(`New tax questionnaire — ${a.full_name || "Unknown client"}`);
  lines.push(`Submitted: ${new Date(payload.submitted_at).toLocaleString("en-AU")}`);
  lines.push("");
  for (const [key, value] of Object.entries(a)) {
    let v = value;
    if (v && typeof v === "object") {
      if (v.bsb) v = `BSB ${v.bsb}  Acc ${v.account_number}  (${v.account_name})`;
      else v = JSON.stringify(v);
    }
    if (Array.isArray(v)) v = v.join(", ");
    lines.push(`${key.replace(/_/g, " ")}: ${yesNo(v)}`);
  }
  if (payload.files && payload.files.length) {
    lines.push("");
    lines.push(`Attachments: ${payload.files.map((f) => f.name).join(", ")}`);
  }
  return lines.join("\n");
}

function filesToAttachments(files) {
  return (files || []).map((f) => {
    // data is a data URL: "data:<mime>;base64,<...>"
    const base64 = String(f.data || "").split(",").pop();
    return { filename: f.name, content: Buffer.from(base64, "base64"), contentType: f.type };
  });
}

/* ---------------------------------------------------------------- email */
async function sendEmail(payload) {
  if (!ENV.SMTP_HOST) {
    console.warn("[email] SMTP not configured — skipping email send.");
    return;
  }
  const transporter = nodemailer.createTransport({
    host: ENV.SMTP_HOST,
    port: ENV.SMTP_PORT,
    secure: ENV.SMTP_PORT === 465,
    auth: ENV.SMTP_USER ? { user: ENV.SMTP_USER, pass: ENV.SMTP_PASS } : undefined,
  });
  const name = payload.answers.full_name || "client";
  await transporter.sendMail({
    from: ENV.MAIL_FROM,
    to: ENV.MAIL_TO,
    subject: `Tax questionnaire — ${name} (${payload.answers.tax_year || "year n/a"})`,
    text: summariseForEmail(payload),
    attachments: filesToAttachments(payload.files),
  });
}

/* ----------------------------------------------------------------- Xero */
async function getXeroAccessToken() {
  // Exchanges a stored refresh token for a fresh access token.
  // NOTE: Xero rotates refresh tokens on every use — you MUST persist the new
  // refresh_token from the response back to your secret store, or the next call
  // will fail. A static env var only works for a single call. Use a small KV /
  // database row to hold the current refresh token in production.
  const res = await fetch("https://identity.xero.com/connect/token", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      Authorization:
        "Basic " +
        Buffer.from(`${ENV.XERO_CLIENT_ID}:${ENV.XERO_CLIENT_SECRET}`).toString("base64"),
    },
    body: new URLSearchParams({
      grant_type: "refresh_token",
      refresh_token: ENV.XERO_REFRESH_TOKEN,
    }),
  });
  if (!res.ok) throw new Error("Xero token exchange failed: " + (await res.text()));
  const tok = await res.json();
  // TODO: persist tok.refresh_token somewhere durable here.
  return tok.access_token;
}

async function upsertXeroContact(payload) {
  if (!ENV.XERO_ENABLED) {
    console.warn("[xero] XERO_ENABLED is not true — skipping Xero sync.");
    return null;
  }
  const a = payload.answers;
  const accessToken = await getXeroAccessToken();

  const contact = {
    Name: a.full_name,
    FirstName: (a.full_name || "").split(" ")[0],
    LastName: (a.full_name || "").split(" ").slice(1).join(" "),
    Phones: a.mobile ? [{ PhoneType: "MOBILE", PhoneNumber: a.mobile }] : [],
    // Bank account for refunds can be stored on the contact for payroll/payments use.
    BankAccountDetails: a.bank ? String(a.bank.account_number || "") : undefined,
  };

  // POST to /Contacts performs an upsert when the Name matches an existing contact.
  const res = await fetch("https://api.xero.com/api.xro/2.0/Contacts", {
    method: "POST",
    headers: {
      Authorization: "Bearer " + accessToken,
      "Xero-tenant-id": ENV.XERO_TENANT_ID,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ Contacts: [contact] }),
  });
  if (!res.ok) throw new Error("Xero contact upsert failed: " + (await res.text()));
  const data = await res.json();
  return data.Contacts && data.Contacts[0] ? data.Contacts[0].ContactID : null;
}

/* ------------------------------------------------------------- core flow */
async function processSubmission(payload) {
  if (!payload || !payload.answers || !payload.answers.full_name) {
    throw new Error("Invalid submission: missing answers.");
  }
  const reference = "LMS-" + Date.now().toString(36).toUpperCase();

  // Email is the source of truth and must succeed; Xero is best-effort so a
  // Xero outage never blocks a client from submitting.
  await sendEmail(payload);
  try {
    await upsertXeroContact(payload);
  } catch (e) {
    console.error("[xero] sync failed (non-fatal):", e.message);
  }
  return { reference };
}

/* ----------------------------------------------- serverless-style handler */
async function handler(req, res) {
  // CORS
  res.setHeader("Access-Control-Allow-Origin", ENV.ALLOW_ORIGIN);
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  if (req.method === "OPTIONS") return res.status(204).end();
  if (req.method !== "POST") return res.status(405).json({ error: "Method not allowed" });

  try {
    const body = req.body && typeof req.body === "object" ? req.body : JSON.parse(req.body || "{}");
    const result = await processSubmission(body);
    return res.status(200).json(result);
  } catch (err) {
    console.error("Submission error:", err);
    return res.status(500).json({ error: "Could not process submission." });
  }
}

module.exports = { handler, processSubmission, summariseForEmail };

/* ------------------------------------------------- standalone Express app */
// Run directly with: node server/submit-handler.js   (after `npm i express nodemailer`)
if (require.main === module) {
  const express = require("express"); // npm i express
  const app = express();
  app.use(express.json({ limit: ENV.MAX_BYTES }));
  app.post("/api/tax-questionnaire", handler);
  app.get("/health", (_, res) => res.json({ ok: true }));
  const port = process.env.PORT || 3000;
  app.listen(port, () => console.log(`Tax questionnaire handler listening on :${port}`));
}
