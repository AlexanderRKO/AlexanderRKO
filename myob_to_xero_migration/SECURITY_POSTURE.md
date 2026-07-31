# Security posture — migration tooling

Companion to `PRIVACY.md`, which covers the obligations. This covers the
architectural decision taken to reduce the exposure those obligations
create, and what has to stay true for it to hold.

## Decision

**Client files are processed in the browser or on the local machine and
are never stored on a server.**

The client-upload portal and cross-device collaboration were considered
and deliberately dropped. They were the only features requiring
server-side storage of client files, and the convenience did not justify
holding employee tax file numbers and bank details in third-party cloud
storage.

Both tools follow this: the Python toolkit runs locally by design, and
the web app processes uploads in-browser without persisting file
contents.

## What this removes

Storing client files server-side raises a set of obligations that mostly
disappear when nothing is stored.

| Obligation | Why it no longer bites |
| ---------- | ---------------------- |
| **APP 8** — cross-border disclosure | No disclosure occurs. Without this, a US-hosted backend would make the firm accountable for the overseas recipient's handling, and its breach would be the firm's breach. |
| **TFN Rule 2015** (s17 Privacy Act) — secure storage and destruction | Nothing is retained, so there is nothing to secure or destroy. The alternative was an open-ended retention of TFNs with no deletion policy, which the rule does not permit. |
| **APP 11** — security of held information | Materially narrowed. The firm secures devices, not a file store. |
| **Notifiable Data Breach scheme** | No stored client files means no breachable store of client files. |
| Subprocessor DPAs, virus scanning, retention policies, signed-URL expiry | All were controls on a store that no longer exists. |

What remains is ordinary device and workstation security, which the firm
already manages.

## What must stay true

The decision only holds if these are all true. They are verifiable, and
should be re-checked whenever the app changes.

1. **No file contents reach the network.** Parsing uses the browser's
   local file APIs. No upload endpoint, no storage bucket write.
2. **No file contents reach an LLM or third-party API.** This is the
   easiest one to reintroduce accidentally — "smart" parsing, column
   detection or error explanation that calls out to a model endpoint
   sends the client's data to that provider. Parsing here is
   deterministic text handling and needs no model.
3. **No file contents in telemetry.** Error and analytics tooling can
   capture form state, request bodies and local variables. If any is
   used, confirm it scrubs file contents and parsed rows.
4. **No file contents in logs.** No `console.log` of parsed data in a
   production build; browser consoles persist and get screenshotted.
5. **No caching of file contents.** No service worker, IndexedDB or
   localStorage persistence of uploaded files or parsed rows.
6. **Output downloads locally.** The generated Xero CSVs are produced
   client-side and saved directly, never round-tripped through a server.
7. **The service-role key is server-side only.** It bypasses every
   row-level security policy. It must never appear in client-side code,
   in a build-time environment variable exposed to the bundle, or in the
   repository. Check this whenever the backend changes, regardless of
   what is stored.

## What may be persisted

Project state is useful and low-risk provided it excludes personal
information. The line is derived figures, not row-level data.

**May persist** — client or engagement name, conversion date, which
stage the conversion has reached, checklist status, reconciliation
verdicts, control totals and counts (for example "AR reconciled,
342 items, $836,970.61, nil out of balance"), audit events recording who
did what and when.

**Must not persist** — debtor and creditor names, invoice or bill line
detail, contact details, and anything from a payroll export. Contact
names are personal information in their own right where the contact is
an individual or sole trader.

Control totals attached to a named client are confidential under
APES 110 but are not personal information, so they carry the same
obligations as any practice management record.

## Residual risks

Being honest about what this does not solve:

- **Device security.** Files exist on the workstation before and during
  processing. Full-disk encryption, screen lock and current patching
  matter more under this model, not less.
- **Local copies accumulate.** Exports downloaded from MYOB sit in
  Downloads folders. Delete them once Stage 4 verification passes.
- **Personal cloud sync.** A Downloads folder synced to a personal cloud
  drive silently recreates the problem this decision avoids. Keep
  engagement files off synced personal folders.
- **Screenshots and working papers.** Mask TFNs in anything leaving the
  engagement team.
- **The archived MYOB file.** History retained through MYOB AE is still
  client data and still needs controlled access.

## Review

Re-check this document when the web app's backend changes, when any new
third-party service is added to either tool, and at least annually.
