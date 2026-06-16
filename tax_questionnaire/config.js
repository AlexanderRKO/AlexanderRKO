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
  brandTagline: "Existing Client Tax Questionnaire",

  // Maximum total size of uploaded files (MB). Keep modest for email/JSON.
  maxUploadMb: 15,

  // Key used to autosave progress in the browser (localStorage).
  storageKey: "lms_tax_questionnaire_v1",
};

if (typeof module !== "undefined") module.exports = FORM_CONFIG;
