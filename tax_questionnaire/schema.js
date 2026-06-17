/*
 * LMS Advisory — New Client Questionnaire (Tax Preparation)
 * Mirrors the Paperform "NEW CLIENT QUESTIONNAIRE - TAX PREPARATION" (v2026.01.25).
 * ----------------------------------------------------------------------------
 * Non-developers can safely edit labels, help text, options and ordering here
 * without touching the form engine (app.js).
 *
 * Question types:
 *   text | tel | email | textarea | date | select | radio | yesno |
 *   checkboxes | bank | file | acknowledge
 *
 * showIf conditions (a question only shows/required when matched):
 *   { field: 'id', equals: 'Yes' }
 *   { field: 'id', in: ['A','B'] }
 *   { field: 'id', contains: 'Option text' }   // for checkboxes (array) fields
 */

const FORM_SCHEMA = {
  title: "New Client Questionnaire — Tax Preparation",
  version: "v2026.01.25",
  intro:
    "Welcome to LMS Advisory. Please complete the questions below so we can prepare " +
    "your income tax return. Your progress is saved automatically on this device — " +
    "you can return and finish later.",

  steps: [
    {
      id: "about_you",
      title: "About you",
      subtitle: "So we know who we're acting for and can meet our verification obligations.",
      questions: [
        {
          id: "full_name",
          type: "text",
          label: "What is your full name including any middle names?",
          help:
            "Please ensure this matches your drivers licence or passport. We will need to " +
            "contact you to verify these details as per our AML/CTF obligations.",
          required: true,
          autocomplete: "name",
          placeholder: "e.g. Owen James Smith",
        },
        {
          id: "date_of_birth",
          type: "date",
          label: "What is your Date of Birth?",
          required: true,
          autocomplete: "bday",
        },
        {
          id: "residential_address",
          type: "textarea",
          label: "Please confirm your current residential address to include in the return.",
          help: "We will also treat this as your postal address.",
          required: true,
          autocomplete: "street-address",
          placeholder: "Unit / Street / Suburb / State / Postcode",
        },
        {
          id: "mobile",
          type: "tel",
          label:
            "Confirm Mobile Phone number to access secure documents and complete " +
            "electronic signature verification?",
          help:
            "We use Fusesign for digital signatures. The added layer of SMS authentication " +
            "ensures that your Tax File Number will always be secure to you. Every individual " +
            "return lodged needs its own unique email address and unique mobile phone number.",
          required: true,
          validate: "mobile",
          autocomplete: "tel-national",
          placeholder: "04xx xxx xxx",
        },
        {
          id: "occupation",
          type: "text",
          label: "What would you describe as your Primary Occupation?",
          help:
            "It is important we select the right occupation code in your return, as the ATO " +
            "will benchmark the usual deductions claimed in different industries against your peers.",
          required: true,
          autocomplete: "organization-title",
          placeholder: "e.g. Landscaper",
        },
        {
          id: "signing_email",
          type: "email",
          label: "Preferred email address for electronic signing of documents?",
          help:
            "Every return lodged for each taxpayer needs its own unique email address and " +
            "mobile phone number.",
          required: true,
          validate: "email",
          autocomplete: "email",
          placeholder: "name@example.com",
        },
      ],
    },

    {
      id: "year_refund",
      title: "Tax year & refund",
      subtitle: "The year(s) we're lodging and where any refund should go.",
      questions: [
        {
          id: "tax_year",
          type: "checkboxes",
          label: "What Tax Year are we completing for you?",
          help: "Select all that apply.",
          required: true,
          options: ["2026", "2025", "2024", "2023", "2022", "Multiple Years", "Other"],
        },
        {
          id: "tax_year_other",
          type: "text",
          label: "Which other year(s) should we complete?",
          required: false,
          showIf: { field: "tax_year", contains: "Other" },
        },
        {
          // Free-text in the original form. Captured as structured fields here so
          // staff can copy Account name / BSB / Account number straight into Xero.
          id: "bank",
          type: "bank",
          label:
            "What is your preferred Bank Account for your refund? Please provide even if you " +
            "anticipate your return being payable this year.",
          help: "Please provide Account Name, BSB and Account Number.",
          required: true,
        },
        {
          id: "use_trust_account",
          type: "yesno",
          label:
            "If your return is refundable, do you intend to use the LMS Trust Account service " +
            "to pay your tax return fee from your refund?",
          help:
            "Our fees will be quoted in advance wherever possible. If your return is refundable " +
            "and you wish to use the Trust Account Service, the ATO will pay your refund into our " +
            "Trust Account first. Your agreed fee is then transferred to LMS and the balance " +
            "returned to you. This may delay receipt of your refund by up to 1 week. There is no " +
            "charge for using the Trust Account service. We will send you a Trust Authority " +
            "document to complete with your tax paperwork.",
          required: true,
        },
      ],
    },

    {
      id: "getting_started",
      title: "Getting started",
      subtitle: "A couple of quick questions before we dig in.",
      questions: [
        {
          id: "received_checklist",
          type: "yesno",
          label:
            "Have you received a copy of our Tax Checklist for completion to assist you in " +
            "providing us with the documents we'll need to complete your return?",
          help:
            "Copies can also be downloaded from the LMS website: " +
            "https://www.lmsadvisory.com.au/knowledge/taxpreparation/",
          required: false,
        },
        {
          id: "consultation",
          type: "radio",
          label:
            "Do you require a consultation with an accountant in relation to your tax affairs?",
          help:
            "In-person appointments are not necessary to progress tax return preparation. If you " +
            "are looking to book an in-person advice consultation with one of our accountants, you " +
            "can schedule once your returns are complete. Appointments outside of office hours and " +
            "on Saturdays are available by Zoom only. Please note additional fees may apply for " +
            "consultations.",
          required: true,
          options: ["Yes", "No", "Unsure, I'd like a phone call to discuss"],
        },
      ],
    },

    {
      id: "about_return",
      title: "About your return",
      subtitle: "This helps us tailor our advice to your circumstances.",
      questions: [
        {
          id: "significant_items",
          type: "checkboxes",
          label: "Do any of these significant items apply to you?",
          help: "Multiple answers could apply — this will help guide us in advising you on your tax affairs.",
          required: true,
          options: [
            "I am a sole trader",
            "Bought/Sold a Significant Asset required a Capital Gains Tax calculation (investment property/shares)",
            "Own 1 or more investment properties",
            "Got Married in the financial year",
            "Separated from your spouse in the financial year",
            "Welcomed a new child into the world",
            "Moved House (changed my main residence)",
            "Started a new job / Retired",
            "Started my own business",
            "Commenced new studies / Finalised my studies",
            "Paid out my HECS Debt",
            "Refinanced a home loan or investment loan",
            "Invest or Trade in Crypto",
            "Make additional contributions to super",
            "Unsure",
            "Other",
          ],
        },
        // --- Conditional follow-ups driven by the significant items above ---
        {
          id: "sole_trader_abn",
          type: "text",
          label: "As a sole trader, what is your ABN?",
          required: false,
          validate: "abn",
          placeholder: "11 digits",
          showIf: { field: "significant_items", contains: "I am a sole trader" },
        },
        {
          id: "rental_summary_ready",
          type: "yesno",
          label:
            "Do you have your agent's Annual Rental Summary, loan statements and out-of-pocket " +
            "expenses ready to provide?",
          help: "Our checklist has a detailed rental schedule you can complete.",
          required: false,
          showIf: { field: "significant_items", contains: "Own 1 or more investment properties" },
        },
        {
          id: "crypto_detail",
          type: "textarea",
          label: "Tell us briefly about your crypto activity.",
          help: "Which exchanges you used and roughly how many transactions — we'll follow up for detail.",
          required: false,
          showIf: { field: "significant_items", contains: "Invest or Trade in Crypto" },
        },
        {
          id: "significant_items_other",
          type: "text",
          label: "Please tell us about the other significant item.",
          required: false,
          showIf: { field: "significant_items", contains: "Other" },
        },
        {
          id: "questions_for_us",
          type: "textarea",
          label:
            "Do you have any questions in particular related to this year's return or your tax " +
            "affairs in general?",
          help:
            "Please list your questions separated by a comma, e.g. (1. Can I claim this? 2. What " +
            "are the 2 alternate work-from-home claim methods?). It's OK if you have no questions!",
          required: false,
        },
      ],
    },

    {
      id: "documents_services",
      title: "Documents & services",
      subtitle: "Share anything useful and tell us where else we can help.",
      questions: [
        {
          id: "documents",
          type: "file",
          label: "Would you like to upload any documents linked to the questions above for us to consider?",
          help:
            "You are welcome to upload any documentation referred to in the checklist. We'd also " +
            "love a copy of last year's tax return lodged.",
          required: false,
        },
        {
          id: "last_year_return",
          type: "yesno",
          label: "Do you have a copy of last year's tax return on hand in case we need it?",
          help:
            "Providing last year's return helps us ensure we address all applicable aspects of " +
            "your return. Email us or upload it using the link above.",
          required: true,
        },
        {
          id: "other_services",
          type: "checkboxes",
          label: "Are you interested in any of the other services LMS can provide?",
          help:
            "If you do not require any additional services, please select 'No Thanks'. You may " +
            "select as many services as you need — we'll be in touch!",
          required: true,
          options: [
            "No Thanks",
            "Financial Planning",
            "Budgeting / Cashflow Forecasting",
            "Asset purchase structuring and entity formations",
            "Referral to Mortgage Brokers in our network",
            "Referral to Solicitors",
            "Bookkeeping Services",
            "Self Managed Superannuation Creation and Advice",
            "Wealth Creation Strategies",
            "Property Portfolio Review and Growth Strategies",
            "Starting a new business or side hustle",
            "Other",
          ],
        },
        {
          id: "other_services_other",
          type: "text",
          label: "Which other service are you interested in?",
          required: false,
          showIf: { field: "other_services", contains: "Other" },
        },
      ],
    },

    {
      id: "last_things",
      title: "A few last things",
      subtitle: "Almost done.",
      questions: [
        {
          id: "how_heard",
          type: "radio",
          label: "How did you hear about us?",
          help: "If you were referred to LMS, we would love to thank the person who passed on our details.",
          required: true,
          options: [
            "Referral",
            "LMS Website",
            "LinkedIn",
            "Facebook",
            "Instagram",
            "Saw us in a magazine or online publication",
            "Other",
          ],
        },
        {
          id: "referrer_name",
          type: "text",
          label: "Who can we thank for referring you?",
          required: false,
          showIf: { field: "how_heard", equals: "Referral" },
        },
        {
          id: "how_heard_other",
          type: "text",
          label: "Please tell us how you heard about us.",
          required: false,
          showIf: { field: "how_heard", equals: "Other" },
        },
        {
          id: "google_review",
          type: "yesno",
          label:
            "If we provide you an outstanding service, would you be willing to leave us a Google review?",
          help:
            "Our business grows when our valued customers share their positive experience with us. " +
            "We look forward to working with you!",
          required: false,
        },
        {
          id: "other_entities",
          type: "yesno",
          label: "Do you have any other entities that you would like us to look after?",
          help:
            "You may have associated companies, trusts or an SMSF. We have expertise in all of the " +
            "above and would love to help.",
          required: true,
        },
        {
          id: "other_entities_detail",
          type: "textarea",
          label: "Tell us about the entities you'd like us to look after.",
          required: false,
          showIf: { field: "other_entities", equals: "Yes" },
        },
      ],
    },

    // ---------------------------------------------------------------------
    // ACKNOWLEDGEMENTS — the client must confirm each of these to submit.
    // (Confirmed for use on the New Client form.)
    // ---------------------------------------------------------------------
    {
      id: "acknowledgements",
      title: "Acknowledgements",
      subtitle: "Please read and confirm each of the following to continue.",
      questions: [
        {
          id: "ack_tax_ready",
          type: "acknowledge",
          required: true,
          label:
            "I understand that LMS cannot commence working on my return until my Income Tax " +
            "Finalisation for the year is noted as 'Tax Ready' in myGov or on the ATO Prefill report.",
        },
        {
          id: "ack_info_received",
          type: "acknowledge",
          required: true,
          label:
            "I understand that LMS will start working on my return when all of the information " +
            "requested from me has been received.",
        },
        {
          id: "ack_source_documents",
          type: "acknowledge",
          required: true,
          label:
            "Where source documents have not been provided (for example, items listed on a " +
            "spreadsheet without a receipt), I confirm the source documents are in my possession " +
            "and can be provided on request by LMS Advisory Pty Limited, the Australian Taxation " +
            "Office, or any other party with authority to request them.",
        },
        {
          id: "ack_withhold_lodgement",
          type: "acknowledge",
          required: true,
          label:
            "I understand LMS Advisory reserves the right to withhold lodgement of my return until " +
            "any outstanding invoice(s) for the preparation of that return have been paid.",
        },
      ],
    },
  ],
};

if (typeof module !== "undefined") module.exports = FORM_SCHEMA;
