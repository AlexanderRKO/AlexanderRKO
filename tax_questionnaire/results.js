/*
 * LMS Advisory — Staff results view
 * Renders a single submission with one-click copy on every field, plus a
 * Xero-shaped contact card so staff can paste straight into "Add Contact".
 *
 * It loads a submission from (in priority order):
 *   1. ?d=<base64url JSON>   — e.g. a link included in the notification email
 *   2. localStorage "lms_last_submission" — the most recent demo submission
 *   3. a paste box shown when nothing else is found
 */
(function () {
  "use strict";

  const root = document.getElementById("results-root");
  const toastEl = document.getElementById("toast");
  const schema = typeof FORM_SCHEMA !== "undefined" ? FORM_SCHEMA : { steps: [] };
  const labelOf = {};
  const typeOf = {};
  schema.steps.forEach((s) => s.questions.forEach((q) => { labelOf[q.id] = q.label; typeOf[q.id] = q.type; }));

  /* --------------------------------------------------------------- helpers */
  function el(tag, attrs, kids) {
    const n = document.createElement(tag);
    if (attrs)
      for (const k in attrs) {
        if (k === "class") n.className = attrs[k];
        else if (k.startsWith("on") && typeof attrs[k] === "function")
          n.addEventListener(k.slice(2).toLowerCase(), attrs[k]);
        else if (attrs[k] != null) n.setAttribute(k, attrs[k]);
      }
    (kids || []).forEach((c) => c != null && n.appendChild(typeof c === "string" ? document.createTextNode(c) : c));
    return n;
  }

  function toast(msg) {
    toastEl.textContent = msg;
    toastEl.classList.add("show");
    clearTimeout(toast._t);
    toast._t = setTimeout(() => toastEl.classList.remove("show"), 1200);
  }

  async function copy(text) {
    try {
      await navigator.clipboard.writeText(text);
    } catch (e) {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); } catch (_) {}
      document.body.removeChild(ta);
    }
  }

  function flash(node, label) {
    node.classList.add("copied");
    setTimeout(() => node.classList.remove("copied"), 1100);
    toast(label ? "Copied " + label : "Copied");
  }

  function b64urlDecode(s) {
    s = s.replace(/-/g, "+").replace(/_/g, "/");
    while (s.length % 4) s += "=";
    return decodeURIComponent(escape(atob(s)));
  }

  /* ------------------------------------------------------------ value text */
  function fmtBsb(v) {
    const d = String(v || "").replace(/\D/g, "");
    return d.length === 6 ? d.slice(0, 3) + "-" + d.slice(3) : d;
  }

  function displayValue(key, value) {
    if (value == null || value === "") return "—";
    if (typeOf[key] === "acknowledge") return value === true ? "Agreed ✓" : "—";
    if (typeof value === "boolean") return value ? "Yes" : "No";
    if (key === "mobile") {
      const d = String(value).replace(/\D/g, "");
      return d.length === 10 ? d.replace(/(\d{4})(\d{3})(\d{3})/, "$1 $2 $3") : value;
    }
    if (Array.isArray(value)) return value.length ? value.join(", ") : "—";
    if (typeof value === "object") {
      if ("bsb" in value)
        return `BSB ${fmtBsb(value.bsb)}   Acc ${value.account_number || "—"}\n${value.account_name || ""}`.trim();
      return JSON.stringify(value);
    }
    return String(value);
  }

  /* ----------------------------------------------------------- copy widgets */
  // Big labelled click-to-copy tile (used in the Xero card).
  function copyTile(label, value) {
    const has = value != null && String(value).trim() !== "";
    const tile = el("button", {
      class: "cp", type: "button", title: has ? "Click to copy" : "Not provided",
      onclick: () => { if (has) { copy(String(value)); flash(tile, label); } },
    }, [
      el("span", { class: "cp-body" }, [
        el("span", { class: "cp-label" }, [label]),
        el("span", { class: "cp-val" + (has ? "" : " empty") }, [has ? String(value) : "not provided"]),
      ]),
      el("span", { class: "cp-icon" }, [has ? "⧉ copy" : ""]),
    ]);
    return tile;
  }

  // Compact answer row with a copy button on the right.
  function answerRow(question, valueText, rawForCopy) {
    const btn = el("button", { class: "mini-copy", type: "button",
      onclick: () => { copy(rawForCopy); flash(btn); btn.textContent = "Copied ✓"; setTimeout(() => (btn.textContent = "Copy"), 1100); } },
      ["Copy"]);
    return el("div", { class: "ans-row" }, [
      el("div", { class: "ans-q" }, [question]),
      el("div", { class: "ans-right" }, [
        el("div", { class: "ans-v" }, [valueText]),
        btn,
      ]),
    ]);
  }

  /* --------------------------------------------------------------- render */
  function render(payload) {
    root.innerHTML = "";
    const a = payload.answers || {};
    const fullName = a.full_name || "Unknown client";
    const firstName = fullName.split(" ")[0] || "";
    const lastName = fullName.split(" ").slice(1).join(" ");
    const bank = a.bank || {};

    /* Header */
    const head = el("div", { class: "card" }, [
      el("div", { class: "results-head" }, [
        el("div", {}, [
          el("h2", { style: "margin:0" }, [fullName]),
          el("div", { class: "meta" }, [
            `${a.occupation || "Occupation n/a"} · Tax year ${a.tax_year || "n/a"}` +
            (payload.submitted_at ? " · " + new Date(payload.submitted_at).toLocaleString("en-AU") : ""),
          ]),
        ]),
        el("button", { class: "btn btn-ghost", type: "button",
          onclick: () => { copy(plainTextSummary(payload)); toast("Copied full summary"); } },
          ["Copy full summary"]),
      ]),

      /* Xero contact quick-copy */
      el("div", { class: "section-title" }, ["Xero · Add Contact"]),
      el("div", { class: "xero-card" }, [
        el("h3", {}, ["Paste these into Xero"]),
        el("p", { class: "hint" }, ["Click any field to copy it, then paste into the matching box in Xero's New Contact form."]),
        el("div", { class: "copy-grid" }, [
          copyTile("Contact name", fullName),
          copyTile("First name", firstName),
          copyTile("Last name", lastName),
          copyTile("Mobile", displayValue("mobile", a.mobile)),
          copyTile("Account name", bank.account_name),
          copyTile("BSB", fmtBsb(bank.bsb)),
          copyTile("Account number", bank.account_number),
          copyTile("Occupation", a.occupation),
        ]),
        el("div", { style: "margin-top:10px" }, [
          el("button", { class: "btn btn-primary", type: "button", style: "padding:10px 18px",
            onclick: (e) => { copy(xeroBlock(payload)); flash(e.target, "contact block"); } },
            ["⧉ Copy full contact block"]),
        ]),
      ]),
    ]);
    root.appendChild(head);

    /* All answers grouped by the form's steps */
    schema.steps.forEach((step) => {
      const rows = step.questions
        .filter((q) => q.id in a && a[q.id] != null && a[q.id] !== "" && !(Array.isArray(a[q.id]) && a[q.id].length === 0))
        .map((q) => {
          const vText = displayValue(q.id, a[q.id]);
          const raw = q.type === "bank" ? `${fmtBsb(a[q.id].bsb)} ${a[q.id].account_number} ${a[q.id].account_name}` : vText;
          return answerRow(q.label, vText, raw);
        });
      if (!rows.length) return;
      const card = el("div", { class: "card" }, [
        el("div", { class: "section-title", style: "margin-top:0" }, [step.title]),
        ...rows,
      ]);
      root.appendChild(card);
    });

    /* Attachments */
    if (payload.files && payload.files.length) {
      const card = el("div", { class: "card attachments" }, [
        el("div", { class: "section-title", style: "margin-top:0" }, ["Attachments"]),
        ...payload.files.map((f) =>
          el("div", { class: "ans-row" }, [
            el("a", { href: f.data || "#", download: f.name }, [f.name]),
            el("span", { class: "meta" }, [`${(f.size / 1024).toFixed(0)} KB`]),
          ])
        ),
      ]);
      root.appendChild(card);
    }
  }

  /* ------------------------------------------------------ copy compositions */
  function xeroBlock(payload) {
    const a = payload.answers || {};
    const bank = a.bank || {};
    return [
      `Contact name: ${a.full_name || ""}`,
      `First name: ${(a.full_name || "").split(" ")[0]}`,
      `Last name: ${(a.full_name || "").split(" ").slice(1).join(" ")}`,
      `Mobile: ${displayValue("mobile", a.mobile)}`,
      `Bank account name: ${bank.account_name || ""}`,
      `BSB: ${fmtBsb(bank.bsb)}`,
      `Account number: ${bank.account_number || ""}`,
    ].join("\n");
  }

  function plainTextSummary(payload) {
    const a = payload.answers || {};
    const lines = [`${a.full_name || "Client"} — Tax Questionnaire`,
      payload.submitted_at ? new Date(payload.submitted_at).toLocaleString("en-AU") : "", ""];
    schema.steps.forEach((step) => {
      step.questions.forEach((q) => {
        if (!(q.id in a)) return;
        const v = displayValue(q.id, a[q.id]);
        if (v === "—") return;
        lines.push(`${q.label}\n  ${v.replace(/\n/g, "\n  ")}`);
      });
    });
    if (payload.files && payload.files.length)
      lines.push("", "Attachments: " + payload.files.map((f) => f.name).join(", "));
    return lines.join("\n");
  }

  /* --------------------------------------------------------- data loading */
  function renderPasteBox() {
    root.innerHTML = "";
    const ta = el("textarea", { placeholder: "Paste the submission JSON here…" });
    root.appendChild(el("div", { class: "card paste-area" }, [
      el("div", { class: "step-head" }, [
        el("h2", {}, ["Open a submission"]),
        el("p", {}, ["No submission was supplied in the link. Paste a submission JSON below, or open this page via the link in the notification email."]),
      ]),
      ta,
      el("div", { class: "nav" }, [
        el("div", { class: "spacer" }),
        el("button", { class: "btn btn-primary", type: "button",
          onclick: () => { try { render(JSON.parse(ta.value)); } catch (e) { alert("That doesn't look like valid JSON."); } } },
          ["Open"]),
      ]),
    ]));
  }

  function load() {
    const params = new URLSearchParams(location.search);
    if (params.get("d")) {
      try { return render(JSON.parse(b64urlDecode(params.get("d")))); }
      catch (e) { /* fall through */ }
    }
    try {
      const raw = localStorage.getItem("lms_last_submission");
      if (raw) return render(JSON.parse(raw));
    } catch (e) {}
    renderPasteBox();
  }

  load();
})();
