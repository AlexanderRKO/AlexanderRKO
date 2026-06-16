/*
 * LMS Advisory — Existing Client Tax Questionnaire
 * ------------------------------------------------
 * This file defines every question in the form. Non-developers can safely edit
 * labels, help text, options and ordering here without touching the form engine.
 *
 * Each question supports:
 *   id        Unique key used in the submission payload (keep stable once live).
 *   type      One of: text | tel | email | textarea | select | yesno |
 *             checkboxes | date | bank | acknowledge | file | info
 *   label     The question text shown to the client.
 *   help      Optional supporting text shown beneath the label.
 *   required  true = client must answer before continuing.
 *   options   For select / checkboxes: array of strings.
 *   placeholder  Optional input placeholder.
 *   validate  Optional named validator: 'mobile' | 'bsb' | 'account' | 'abn'.
 *   showIf    Optional condition: { field: 'id', equals: 'Yes' }
 *                                or { field: 'id', in: ['A','B'] }.
 *             The question only appears (and is only required) when it matches.
 *
 * Steps group questions into pages of the wizard.
 */

const FORM_SCHEMA = {
  title: "Existing Client Tax Questionnaire",
  intro:
    "Please complete the questions below so we can prepare your income tax return. " +
    "Your progress is saved automatically on this device — you can return and finish later.",

  steps: [
    {
      id: "about",
      title: "About you",
      subtitle: "So we know who we're acting for and how to reach you.",
      questions: [
        {
          id: "full_name",
          type: "text",
          label: "What is your full name, including any middle names?",
          required: true,
          placeholder: "e.g. Owen James Smith",
        },
        {
          id: "mobile",
          type: "tel",
          label: "Confirm your mobile phone number",
          help:
            "Used to give you secure access to documents and to complete electronic " +
            "signature verification.",
          required: true,
          validate: "mobile",
          placeholder: "04xx xxx xxx",
        },
        {
          id: "occupation",
          type: "text",
          label: "What would you describe as your primary occupation?",
          required: true,
          placeholder: "e.g. Landscaper",
        },
      ],
    },

    {
      id: "year_refund",
      title: "Tax year & refund",
      subtitle: "The year we're lodging and where any refund should go.",
      questions: [
        {
          id: "tax_year",
          type: "select",
          label: "What tax year are we completing for you?",
          required: true,
          options: ["2025", "2024", "2023", "2022", "Other / multiple years"],
        },
        {
          id: "bank",
          type: "bank",
          label: "What is your preferred bank account for your refund?",
          help:
            "Please provide this even if you expect your return to be payable this year.",
          required: true,
        },
        {
          id: "use_trust_account",
          type: "yesno",
          label:
            "If your return is refundable, do you intend to use the LMS Trust Account " +
            "service to pay your tax return fee from your refund?",
          required: true,
        },
      ],
    },

    {
      id: "situation",
      title: "Your situation this year",
      subtitle:
        "These help us claim everything you're entitled to. Answer 'Yes' and we'll ask " +
        "for a little more where it's relevant.",
      questions: [
        {
          id: "want_checklist",
          type: "yesno",
          label:
            "Would you like a copy of our Tax Checklist to help you gather the documents " +
            "we'll need to complete your return?",
          required: true,
        },
        {
          id: "need_consultation",
          type: "yesno",
          label:
            "Do you require a consultation with an accountant in relation to your tax " +
            "affairs this year?",
          required: true,
        },
        {
          id: "significant_changes",
          type: "yesno",
          label:
            "Have you had any significant changes in circumstances since last year's return?",
          help: "For example: marriage, separation, new dependents, a new job or business.",
          required: true,
        },
        {
          id: "significant_changes_detail",
          type: "textarea",
          label: "Please tell us briefly what has changed.",
          required: true,
          showIf: { field: "significant_changes", equals: "Yes" },
        },

        {
          id: "property_investor",
          type: "yesno",
          label: "Did you own a rental or investment property during the year?",
          required: true,
        },
        {
          id: "rental_summary_ready",
          type: "yesno",
          label: "Do you have your agent's Annual Rental Summary ready to provide?",
          help:
            "We'll also need your loan statements and any out-of-pocket expenses not paid " +
            "by the managing agent. Our checklist has a detailed rental schedule you can complete.",
          required: true,
          showIf: { field: "property_investor", equals: "Yes" },
        },
        {
          id: "work_from_home",
          type: "yesno",
          label: "Did you work from home during the year?",
          help:
            "Work-from-home deductions have been reduced, but we can still help you claim.",
          required: true,
        },
        {
          id: "crypto",
          type: "yesno",
          label:
            "Did you have any reportable crypto trading during the year (or in prior years " +
            "you may have forgotten to mention)?",
          required: true,
        },
        {
          id: "crypto_detail",
          type: "textarea",
          label: "Please give us a brief overview of your crypto activity.",
          help: "Exchanges used and roughly how many transactions — we'll follow up for detail.",
          required: true,
          showIf: { field: "crypto", equals: "Yes" },
        },
        {
          id: "super_contributions",
          type: "yesno",
          label:
            "Did you make any personal or salary-sacrifice super contributions during the year?",
          required: true,
        },
        {
          id: "super_detail",
          type: "textarea",
          label: "Which fund, and roughly how much did you contribute?",
          required: false,
          showIf: { field: "super_contributions", equals: "Yes" },
        },
        {
          id: "sole_trader",
          type: "yesno",
          label:
            "Do you run your own small business under a personal ABN that needs to be " +
            "reported in this return?",
          required: true,
        },
        {
          id: "abn",
          type: "text",
          label: "What is your ABN?",
          required: true,
          validate: "abn",
          placeholder: "11 digits",
          showIf: { field: "sole_trader", equals: "Yes" },
        },
      ],
    },

    {
      id: "documents",
      title: "Documents & other services",
      subtitle: "Upload anything relevant and tell us if we can help elsewhere.",
      questions: [
        {
          id: "upload_documents",
          type: "yesno",
          label: "Would you like to upload any documents linked to the questions above?",
          required: true,
        },
        {
          id: "documents",
          type: "file",
          label: "Upload your documents",
          help: "PDF, images, Word or Excel. You can add several files.",
          required: false,
          showIf: { field: "upload_documents", equals: "Yes" },
        },
        {
          id: "other_services",
          type: "checkboxes",
          label: "Are you interested in any of the other services LMS can provide?",
          help: "Select any that apply, or 'No thanks'.",
          required: true,
          options: [
            "No thanks",
            "Financial planning",
            "Self-managed super (SMSF)",
            "Bookkeeping",
            "Business advisory",
            "Mortgage & lending",
            "Estate planning",
          ],
        },
        {
          id: "express_priority",
          type: "yesno",
          label:
            "Is your return urgent and does it need to be processed under our Express " +
            "Priority Return service?",
          help: "Additional fees apply to the Express Priority service.",
          required: true,
        },
        {
          id: "preferred_date",
          type: "date",
          label: "Do you have a preferred date for completion?",
          required: false,
        },
      ],
    },

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
            "I understand that LMS cannot commence working on my return until my Income " +
            "Tax Finalisation for the year is noted as 'Tax Ready' in myGov or on the ATO " +
            "Prefill report.",
        },
        {
          id: "ack_info_received",
          type: "acknowledge",
          required: true,
          label:
            "I understand that LMS will start working on my return when all of the " +
            "information requested from me has been received.",
        },
        {
          id: "ack_source_documents",
          type: "acknowledge",
          required: true,
          label:
            "Where source documents have not been provided (for example, items listed on a " +
            "spreadsheet without a receipt), I confirm the source documents are in my " +
            "possession and can be provided on request by LMS Advisory Pty Limited, the " +
            "Australian Taxation Office, or any other party with authority to request them.",
        },
        {
          id: "ack_withhold_lodgement",
          type: "acknowledge",
          required: true,
          label:
            "I understand LMS Advisory reserves the right to withhold lodgement of my return " +
            "until any outstanding invoice(s) for the preparation of that return have been paid.",
        },
      ],
    },
  ],
};

if (typeof module !== "undefined") module.exports = FORM_SCHEMA;
