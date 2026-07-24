/*
 * LMS Advisory — Tax Questionnaire configuration
 * ----------------------------------------------
 * Edit these settings to point the form at your backend and brand it.
 */

const FORM_CONFIG = {
  // Where submissions are POSTed (JSON). See server/submit-handler.js for a
  // reference implementation that emails your team and updates Xero.
  // Leave as "" to run in DEMO mode: the form validates and shows the payload
  // on screen without sending anything anywhere.
  submitEndpoint: "",

  // Branding shown in the form header.
  brandName: "LMS Advisory",
  brandTagline: "New Client Questionnaire — Tax Preparation",

  // Maximum total size of uploaded files (MB). Keep modest for email/JSON.
  maxUploadMb: 15,

  // Require a privacy/consent tick before the client can submit.
  requireConsent: true,
  privacyPolicyUrl: "https://www.lmsadvisory.com.au/privacy-policy/",

  // Optional Cloudflare Turnstile (free, privacy-friendly CAPTCHA). Leave blank
  // to rely on the built-in honeypot + timing trap only. If you paste a site key
  // here, also add this once to index.html's <head>:
  //   <script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
  // and verify the token server-side (see server/submit-handler.js).
  turnstileSiteKey: "",

  // Key used to autosave progress in the browser (localStorage).
  storageKey: "lms_tax_questionnaire_v1",
};

if (typeof module !== "undefined") module.exports = FORM_CONFIG;
