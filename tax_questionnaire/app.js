/*
 * LMS Advisory — Tax Questionnaire form engine
 * Schema-driven, dependency-free. Renders FORM_SCHEMA using FORM_CONFIG.
 */
(function () {
  "use strict";

  const schema = FORM_SCHEMA;
  const cfg = FORM_CONFIG;
  const root = document.getElementById("form-root");

  const REVIEW = schema.steps.length; // virtual step index for the review page

  const state = {
    stepIndex: 0,
    answers: {}, // id -> value
    files: [], // {name, size, type, data} for the 'documents' question
    submitting: false,
  };

  /* ---------------------------------------------------------------- utils */
  const flatQuestions = schema.steps.flatMap((s) => s.questions);
  const byId = (id) => flatQuestions.find((q) => q.id === id);

  function isActive(q) {
    if (!q.showIf) return true;
    const v = state.answers[q.showIf.field];
    if ("equals" in q.showIf) return v === q.showIf.equals;
    if ("in" in q.showIf) return q.showIf.in.includes(v);
    if ("contains" in q.showIf) return Array.isArray(v) && v.includes(q.showIf.contains);
    return true;
  }

  function activeQuestions(step) {
    return step.questions.filter(isActive);
  }

  function normalizeMobile(v) {
    let d = String(v || "").replace(/\D/g, "");
    if (d.startsWith("61") && d.length === 11) d = "0" + d.slice(2);
    return d;
  }

  const validators = {
    mobile: (v) => /^04\d{8}$/.test(normalizeMobile(v)),
    bsb: (v) => /^\d{6}$/.test(String(v || "").replace(/\D/g, "")),
    account: (v) => /^\d{5,12}$/.test(String(v || "").replace(/\D/g, "")),
    abn: (v) => /^\d{11}$/.test(String(v || "").replace(/\D/g, "")),
    email: (v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(v || "").trim()),
  };

  function isAnswered(q) {
    const v = state.answers[q.id];
    if (q.type === "bank") {
      return v && v.bsb && v.account_number && v.account_name;
    }
    if (q.type === "checkboxes") return Array.isArray(v) && v.length > 0;
    if (q.type === "acknowledge") return v === true;
    if (q.type === "file") return state.files.length > 0;
    return v !== undefined && v !== null && String(v).trim() !== "";
  }

  function questionError(q) {
    const v = state.answers[q.id];
    if (q.required && !isAnswered(q)) {
      return q.type === "acknowledge"
        ? "Please confirm to continue."
        : "This field is required.";
    }
    if (!isAnswered(q)) return null; // optional & empty
    if (q.type === "bank") {
      if (!validators.bsb(v.bsb)) return "BSB should be 6 digits (e.g. 062-000).";
      if (!validators.account(v.account_number)) return "Account number looks incorrect.";
      return null;
    }
    if (q.validate && validators[q.validate]) {
      if (!validators[q.validate](v)) {
        if (q.validate === "mobile") return "Enter a valid Australian mobile (04xx xxx xxx).";
        if (q.validate === "abn") return "An ABN is 11 digits.";
        if (q.validate === "email") return "Enter a valid email address.";
        return "That value doesn't look right.";
      }
    }
    return null;
  }

  /* --------------------------------------------------------------- storage */
  function save() {
    try {
      const data = { stepIndex: state.stepIndex, answers: state.answers };
      localStorage.setItem(cfg.storageKey, JSON.stringify(data));
    } catch (e) {
      /* storage full or unavailable — non-fatal */
    }
  }
  function restore() {
    try {
      const raw = localStorage.getItem(cfg.storageKey);
      if (!raw) return;
      const data = JSON.parse(raw);
      state.answers = data.answers || {};
      state.stepIndex = Math.min(data.stepIndex || 0, schema.steps.length - 1);
    } catch (e) {
      /* ignore corrupt state */
    }
  }
  function clearSaved() {
    try { localStorage.removeItem(cfg.storageKey); } catch (e) {}
  }

  /* ------------------------------------------------------------ rendering */
  function el(tag, attrs, children) {
    const n = document.createElement(tag);
    if (attrs) {
      for (const k in attrs) {
        if (k === "class") n.className = attrs[k];
        else if (k === "html") n.innerHTML = attrs[k];
        else if (k.startsWith("on") && typeof attrs[k] === "function")
          n.addEventListener(k.slice(2).toLowerCase(), attrs[k]);
        else if (attrs[k] != null) n.setAttribute(k, attrs[k]);
      }
    }
    (children || []).forEach((c) => {
      if (c == null) return;
      n.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return n;
  }

  // Once the user has tried to advance (state.showErrors), give live feedback on
  // text fields without a full re-render (which would steal focus): clear the
  // error optimistically as they type, and re-check when they leave the field.
  function clearQError(target) {
    if (!state.showErrors || !target.closest) return;
    const w = target.closest(".q"); if (!w) return;
    w.classList.remove("invalid");
    const fe = w.querySelector(".field-error"); if (fe) fe.textContent = "";
    target.removeAttribute("aria-invalid");
  }
  function revalidateQ(q, target) {
    if (!state.showErrors || !target.closest) return;
    const w = target.closest(".q"); if (!w) return;
    const err = questionError(q);
    w.classList.toggle("invalid", !!err);
    const fe = w.querySelector(".field-error"); if (fe) fe.textContent = err || "";
    if (err) target.setAttribute("aria-invalid", "true");
    else target.removeAttribute("aria-invalid");
  }
  // Suggest the right mobile keyboard for a given field type.
  const INPUTMODE = { tel: "tel", email: "email" };

  function renderField(q) {
    const set = (val) => { state.answers[q.id] = val; save(); };

    switch (q.type) {
      case "text":
      case "tel":
      case "email": {
        return el("input", {
          type: q.type, value: state.answers[q.id] || "",
          placeholder: q.placeholder || "",
          autocomplete: q.autocomplete || null,
          inputmode: INPUTMODE[q.type] || null,
          oninput: (e) => { set(e.target.value); clearQError(e.target); },
          onblur: (e) => revalidateQ(q, e.target),
        });
      }
      case "textarea":
        return el("textarea", {
          placeholder: q.placeholder || "",
          autocomplete: q.autocomplete || null,
          oninput: (e) => { set(e.target.value); clearQError(e.target); },
          onblur: (e) => revalidateQ(q, e.target),
        }, [state.answers[q.id] || ""]);

      case "date":
        return el("input", {
          type: "date", value: state.answers[q.id] || "",
          autocomplete: q.autocomplete || null,
          oninput: (e) => { set(e.target.value); clearQError(e.target); },
          onblur: (e) => revalidateQ(q, e.target),
        });

      case "select": {
        const sel = el("select", { onchange: (e) => set(e.target.value) }, [
          el("option", { value: "" }, ["Please choose…"]),
          ...q.options.map((o) =>
            el("option", { value: o, selected: state.answers[q.id] === o ? "selected" : null }, [o])
          ),
        ]);
        return sel;
      }

      case "yesno": {
        const wrap = el("div", { class: "yesno", role: "group" });
        ["Yes", "No"].forEach((opt) => {
          wrap.appendChild(
            el("button", {
              type: "button",
              "aria-pressed": state.answers[q.id] === opt ? "true" : "false",
              onclick: () => { set(opt); renderStep(); },
            }, [opt])
          );
        });
        return wrap;
      }

      case "radio": {
        const list = el("div", { class: "opt-list" });
        q.options.forEach((opt) => {
          const checked = state.answers[q.id] === opt;
          list.appendChild(
            el("label", { class: "opt" + (checked ? " checked" : "") }, [
              el("input", {
                type: "radio", name: q.id, checked: checked ? "checked" : null,
                onchange: () => { set(opt); renderStep(); },
              }),
              el("span", {}, [opt]),
            ])
          );
        });
        return list;
      }

      case "checkboxes": {
        const list = el("div", { class: "opt-list" });
        const current = Array.isArray(state.answers[q.id]) ? state.answers[q.id] : [];
        q.options.forEach((opt) => {
          const exclusive = /^no thanks$/i.test(opt);
          const checked = current.includes(opt);
          const row = el("label", { class: "opt" + (checked ? " checked" : "") }, [
            el("input", {
              type: "checkbox", checked: checked ? "checked" : null,
              onchange: (e) => {
                let next = Array.isArray(state.answers[q.id]) ? [...state.answers[q.id]] : [];
                if (e.target.checked) {
                  next = exclusive ? [opt] : next.filter((x) => !/^no thanks$/i.test(x));
                  if (!next.includes(opt)) next.push(opt);
                } else {
                  next = next.filter((x) => x !== opt);
                }
                set(next); renderStep();
              },
            }),
            el("span", {}, [opt]),
          ]);
          list.appendChild(row);
        });
        return list;
      }

      case "acknowledge": {
        const checked = state.answers[q.id] === true;
        return el("label", { class: "opt ack" + (checked ? " checked" : "") }, [
          el("input", {
            type: "checkbox", checked: checked ? "checked" : null,
            onchange: (e) => { set(e.target.checked); renderStep(); },
          }),
          el("span", {}, [q.label]),
        ]);
      }

      case "bank": {
        const v = state.answers[q.id] || {};
        const upd = (k, val) => { set({ ...(state.answers[q.id] || {}), [k]: val }); };
        return el("div", { class: "bank" }, [
          el("div", {}, [
            el("label", {}, ["BSB"]),
            el("input", { type: "text", inputmode: "numeric", placeholder: "062-000",
              value: v.bsb || "", oninput: (e) => upd("bsb", e.target.value) }),
          ]),
          el("div", {}, [
            el("label", {}, ["Account number"]),
            el("input", { type: "text", inputmode: "numeric", placeholder: "12345678",
              value: v.account_number || "", oninput: (e) => upd("account_number", e.target.value) }),
          ]),
          el("div", { class: "full" }, [
            el("label", {}, ["Account name"]),
            el("input", { type: "text", placeholder: "Name on the account",
              value: v.account_name || "", oninput: (e) => upd("account_name", e.target.value) }),
          ]),
        ]);
      }

      case "file": {
        const wrap = el("div");
        const input = el("input", {
          type: "file", multiple: "multiple",
          onchange: (e) => addFiles(e.target.files),
        });
        const drop = el("label", { class: "file-drop" }, [
          "Tap to choose files, or drag them here", input,
        ]);
        wrap.appendChild(drop);
        const list = el("div", { class: "file-list" });
        state.files.forEach((f, i) => {
          list.appendChild(el("div", { class: "file-chip" }, [
            el("span", {}, [`${f.name} · ${(f.size / 1024).toFixed(0)} KB`]),
            el("button", { type: "button", onclick: () => { state.files.splice(i, 1); renderStep(); } }, ["Remove"]),
          ]));
        });
        wrap.appendChild(list);
        return wrap;
      }

      default:
        return el("div", {}, [String(state.answers[q.id] || "")]);
    }
  }

  function addFiles(fileList) {
    const maxBytes = cfg.maxUploadMb * 1024 * 1024;
    let total = state.files.reduce((s, f) => s + f.size, 0);
    const arr = Array.from(fileList);
    if (arr.length === 0) return;
    // Only accept files that keep the running total under the cap; tell the user
    // which were skipped rather than silently bloating the submission.
    const accepted = [];
    const skipped = [];
    arr.forEach((file) => {
      if (total + file.size > maxBytes) { skipped.push(file.name); return; }
      total += file.size;
      accepted.push(file);
    });
    let queued = accepted.length;
    if (queued === 0) {
      alert(`These files would exceed the ${cfg.maxUploadMb} MB limit, so they weren't added. Please upload smaller files or email them to us.`);
      return;
    }
    accepted.forEach((file) => {
      const reader = new FileReader();
      reader.onload = () => {
        state.files.push({ name: file.name, size: file.size, type: file.type, data: reader.result });
        if (--queued === 0) {
          renderStep();
          if (skipped.length) {
            alert(`Added ${accepted.length} file(s). Skipped (over ${cfg.maxUploadMb} MB): ${skipped.join(", ")}.`);
          }
        }
      };
      reader.readAsDataURL(file);
    });
  }

  // Types backed by a single native control we can associate a <label for> with.
  const SINGLE_CONTROL = ["text", "tel", "email", "textarea", "date", "select"];
  // Composite controls exposed as an ARIA group/radiogroup.
  const GROUP_ROLE = { yesno: "radiogroup", radio: "radiogroup", checkboxes: "group", bank: "group", file: "group" };

  function renderQuestion(q) {
    const err = state.showErrors ? questionError(q) : null;
    const labelId = "lbl_" + q.id, errId = "err_" + q.id, helpId = "help_" + q.id, fieldId = "f_" + q.id;
    const wrap = el("div", { class: "q" + (err ? " invalid" : ""), "data-qid": q.id });

    if (q.type !== "acknowledge") {
      wrap.appendChild(
        el("label", {
          class: "q-label", id: labelId,
          for: SINGLE_CONTROL.includes(q.type) ? fieldId : null,
        }, [q.label, q.required ? el("span", { class: "req", title: "Required" }, ["*"]) : null])
      );
    }
    if (q.help) wrap.appendChild(el("p", { class: "q-help", id: helpId }, [q.help]));

    const field = renderField(q);
    const describedBy = [q.help ? helpId : null, err ? errId : null].filter(Boolean).join(" ") || null;

    // Wire ARIA: associate the control(s) with the label, help and error text.
    if (SINGLE_CONTROL.includes(q.type)) {
      const ctrl = field.matches && field.matches("input,select,textarea") ? field : field.querySelector("input,select,textarea");
      if (ctrl) {
        ctrl.id = fieldId;
        if (q.required) ctrl.setAttribute("aria-required", "true");
        if (err) ctrl.setAttribute("aria-invalid", "true");
        if (describedBy) ctrl.setAttribute("aria-describedby", describedBy);
      }
    } else if (GROUP_ROLE[q.type]) {
      field.setAttribute("role", GROUP_ROLE[q.type]);
      field.setAttribute("aria-labelledby", labelId);
      if (q.required) field.setAttribute("aria-required", "true");
      if (err) field.setAttribute("aria-invalid", "true");
      if (describedBy) field.setAttribute("aria-describedby", describedBy);
    }

    wrap.appendChild(field);
    wrap.appendChild(el("div", { class: "field-error", id: errId, role: "alert" }, [err || ""]));
    return wrap;
  }

  /* --------------------------------------------------------- review page */
  function answerText(q) {
    const v = state.answers[q.id];
    if (q.type === "bank" && v) {
      const bsb = String(v.bsb || "").replace(/\D/g, "").replace(/(\d{3})(\d{3})/, "$1-$2");
      return `BSB ${bsb}  Acc ${v.account_number}\n${v.account_name}`;
    }
    if (q.type === "checkboxes" && Array.isArray(v)) return v.join(", ");
    if (q.type === "acknowledge") return v ? "Agreed" : "—";
    if (q.type === "file") return state.files.length ? `${state.files.length} file(s) attached` : "—";
    return v ? String(v) : "—";
  }

  function renderReview() {
    const card = el("div", { class: "card" });
    card.appendChild(el("div", { class: "step-head" }, [
      el("h2", {}, ["Review your answers"]),
      el("p", {}, ["Please check everything below, then submit. You can jump back to edit any section."]),
    ]));
    schema.steps.forEach((step, i) => {
      activeQuestions(step).forEach((q) => {
        if (q.type === "info") return;
        card.appendChild(el("div", { class: "review-item" }, [
          el("button", { class: "review-edit", type: "button",
            onclick: () => { state.stepIndex = i; state.showErrors = false; render(); } }, ["Edit"]),
          el("div", { class: "review-q" }, [q.label]),
          el("div", { class: "review-a" }, [answerText(q)]),
        ]));
      });
    });

    if (state.errorBanner) {
      card.appendChild(el("div", { class: "banner banner-error" }, [state.errorBanner]));
    }

    const nav = el("div", { class: "nav" }, [
      el("button", { class: "btn btn-ghost", type: "button",
        onclick: () => { state.stepIndex = schema.steps.length - 1; render(); } }, ["Back"]),
      el("div", { class: "spacer" }),
      el("button", {
        class: "btn btn-primary", type: "button",
        disabled: state.submitting ? "disabled" : null,
        onclick: submit,
      }, [state.submitting ? "Submitting…" : "Submit questionnaire"]),
    ]);
    card.appendChild(nav);
    return card;
  }

  /* ------------------------------------------------------------ step view */
  function renderStep() { render(); }

  function render() {
    root.innerHTML = "";
    root.appendChild(renderProgress());

    if (state.done) { root.appendChild(renderSuccess()); postHeight(); return; }
    if (state.stepIndex === REVIEW) { root.appendChild(renderReview()); postHeight(); return; }

    const step = schema.steps[state.stepIndex];
    const card = el("div", { class: "card" });
    // Welcome note on the first step (uses the schema intro if present).
    if (state.stepIndex === 0 && schema.intro) {
      card.appendChild(el("p", { class: "intro-note" }, [schema.intro]));
    }
    card.appendChild(el("div", { class: "step-head" }, [
      el("h2", {}, [step.title]),
      step.subtitle ? el("p", {}, [step.subtitle]) : null,
    ]));

    activeQuestions(step).forEach((q) => card.appendChild(renderQuestion(q)));

    if (state.showErrors && stepHasErrors(step)) {
      card.appendChild(el("div", { class: "banner banner-error" }, [
        "Please complete the highlighted questions above.",
      ]));
    }

    const isFirst = state.stepIndex === 0;
    const nav = el("div", { class: "nav" }, [
      el("button", { class: "btn btn-ghost", type: "button", disabled: isFirst ? "disabled" : null,
        onclick: prev }, ["Back"]),
      el("div", { class: "spacer" }),
      el("button", { class: "btn btn-primary", type: "button", onclick: next },
        [state.stepIndex === schema.steps.length - 1 ? "Review" : "Continue"]),
    ]);
    card.appendChild(nav);
    root.appendChild(card);
    window.scrollTo({ top: 0, behavior: "smooth" });
    postHeight();
  }

  // When embedded in an iframe, tell the parent page our height so it can size
  // the iframe with no inner scrollbar. The parent listens for this message
  // (see the embed snippet in README.md). Harmless when not embedded.
  function postHeight() {
    if (window.parent === window) return;
    requestAnimationFrame(() => {
      const h = document.body.scrollHeight;
      window.parent.postMessage({ type: "lms-form-height", height: h }, "*");
    });
  }

  function renderProgress() {
    const total = schema.steps.length + 1; // + review
    const current = Math.min(state.stepIndex, schema.steps.length) + 1;
    const pct = state.done ? 100 : ((current - 1) / total) * 100 + 8;
    const label = state.done
      ? "Complete"
      : state.stepIndex === REVIEW
        ? "Final step · Review & submit"
        : `Step ${current} of ${total} · ${schema.steps[state.stepIndex].title}`;
    const pctClamped = Math.round(Math.min(pct, 100));
    return el("div", { class: "progress" }, [
      el("div", {
        class: "progress-track", role: "progressbar",
        "aria-valuemin": "0", "aria-valuemax": "100", "aria-valuenow": String(pctClamped),
        "aria-label": label,
      }, [
        el("div", { class: "progress-fill", style: `width:${Math.min(pct, 100)}%` }),
      ]),
      el("div", { class: "progress-label" }, [label]),
    ]);
  }

  function stepHasErrors(step) {
    return activeQuestions(step).some((q) => questionError(q));
  }

  // After a failed validation, move keyboard focus to the first problem field
  // and bring it into view — clearer than a generic banner alone.
  function focusFirstInvalid() {
    const bad = root.querySelector(".q.invalid");
    if (!bad) return;
    const ctrl = bad.querySelector("input,select,textarea,button");
    if (ctrl) {
      ctrl.focus({ preventScroll: true });
      bad.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  function prev() {
    state.showErrors = false;
    state.errorBanner = null;
    if (state.stepIndex > 0) state.stepIndex -= 1;
    save();
    render();
  }

  function next() {
    const step = schema.steps[state.stepIndex];
    if (stepHasErrors(step)) {
      state.showErrors = true;
      render();
      focusFirstInvalid();
      return;
    }
    state.showErrors = false;
    state.stepIndex += 1;
    save();
    render();
  }

  /* -------------------------------------------------------------- submit */
  function buildPayload() {
    const answers = {};
    flatQuestions.forEach((q) => {
      if (!isActive(q)) return;
      if (q.type === "file") return; // handled separately
      answers[q.id] = state.answers[q.id] ?? null;
    });
    if (answers.mobile) answers.mobile = normalizeMobile(answers.mobile);
    return {
      form: schema.title,
      submitted_at: new Date().toISOString(),
      answers,
      files: state.files.map((f) => ({ name: f.name, type: f.type, size: f.size, data: f.data })),
    };
  }

  // Stash the most recent submission so the staff results view (results.html)
  // can open it locally. Files can be large, so retry without their data if the
  // browser's storage quota is exceeded.
  function saveLastSubmission(payload) {
    try {
      localStorage.setItem("lms_last_submission", JSON.stringify(payload));
    } catch (e) {
      try {
        const slim = { ...payload, files: (payload.files || []).map((f) => ({ name: f.name, type: f.type, size: f.size })) };
        localStorage.setItem("lms_last_submission", JSON.stringify(slim));
      } catch (_) {}
    }
  }

  async function submit() {
    // Final full validation across all steps.
    const firstBadStep = schema.steps.findIndex((s) => stepHasErrors(s));
    if (firstBadStep !== -1) {
      state.stepIndex = firstBadStep;
      state.showErrors = true;
      state.errorBanner = null;
      render();
      focusFirstInvalid();
      return;
    }

    const payload = buildPayload();

    if (!cfg.submitEndpoint) {
      // DEMO mode — no backend configured.
      console.log("Submission payload (demo mode):", payload);
      saveLastSubmission(payload);
      state.reference = "DEMO-" + Date.now().toString(36).toUpperCase();
      state.done = true;
      clearSaved();
      render();
      return;
    }

    state.submitting = true;
    state.errorBanner = null;
    render();
    try {
      const res = await fetch(cfg.submitEndpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json().catch(() => ({}));
      saveLastSubmission(payload);
      state.reference = data.reference || "LMS-" + Date.now().toString(36).toUpperCase();
      state.done = true;
      clearSaved();
    } catch (err) {
      state.errorBanner =
        "Sorry — we couldn't submit your questionnaire just now. Please try again, " +
        "or email us and we'll help. (" + err.message + ")";
    } finally {
      state.submitting = false;
      render();
    }
  }

  function renderSuccess() {
    return el("div", { class: "card success" }, [
      el("div", { class: "check" }, ["✓"]),
      el("h2", {}, ["Thanks — we've got what we need to get started"]),
      el("p", {}, [
        "One of our team will be in touch shortly to begin preparing your return. A quick " +
        "reminder: we can only start once your income shows as 'Tax Ready' in myGov and we " +
        "have all of your information.",
      ]),
      el("div", { class: "ref" }, ["Reference: " + state.reference]),
      // In demo mode (no backend) offer a quick link to preview the staff
      // copy-paste results view. This block does not appear once an endpoint
      // is configured, so clients never see it in production.
      !cfg.submitEndpoint
        ? el("p", { style: "margin-top:18px" }, [
            el("a", { href: "results.html", class: "review-edit", style: "float:none" },
              ["Staff preview: open copy-paste results →"]),
          ])
        : null,
    ]);
  }

  /* ---------------------------------------------------------------- init */
  document.getElementById("brand-name").textContent = cfg.brandName;
  document.getElementById("brand-tag").textContent = cfg.brandTagline;
  restore();
  render();
})();
