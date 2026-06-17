# Editing the form with no software — the in-browser editor

`standalone/LMS-Form-Editor.html` lets you change the questions and download a
ready-to-use form using **only what comes standard on Windows or Mac** — a web
browser (Edge, Safari or Chrome). Nothing to install, no Node, no Notepad.

## Open it

Double-click **`LMS-Form-Editor.html`**. It opens in your browser with two panes:

- **Left** — the editor: settings at the top, then every section and question.
- **Right** — a **live preview** of the actual form that updates as you type.

## Make changes

- **Settings** (top left): the firm name and subtitle shown in the header, your
  Privacy Policy link, where answers are sent (leave blank to test), and whether
  the consent tick is required.
- **Questions**: edit the wording of any question, its help text, whether it’s
  required, and the list of options (for multiple-choice questions — one per line).
- **Add / remove / reorder**: use **+ Add question** (pick a type), **+ Add a
  section**, and the **↑ ↓ ✕** buttons to move or delete.

The preview on the right reflects every change immediately.

## Save and finish

- **⤓ Download form** — saves a finished, single-file questionnaire
  (`lms-new-client-questionnaire.html`) to your Downloads. That’s the file you
  host or share — see `STANDALONE.md` for where to put it.
- **Save working copy** — downloads a small `.json` of your edits so you can come
  back later. Use **Open saved** to load it again next time. (Browsers can’t save
  back into a file on their own, so keep this `.json` if you want to continue
  editing in a future session.)

## Good to know

- Edits in the editor don’t change anything live until you **download** the new
  form and put it in place of the old one.
- Advanced logic — follow-up questions that only appear after a “Yes”, or the
  bank/validation fields — is preserved as-is. To change that wiring, edit
  `schema.js` and rebuild (a developer task), or ask us.
- The editor is self-contained: the form engine and LMS styling are built in, so
  the forms it produces look and behave exactly like the live tool.
