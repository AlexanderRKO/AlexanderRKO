"""Streamlit workspace for the MYOB → Xero migration toolkit.

Interactive, not just a viewer: forms to scaffold a new engagement, per-row
status tickboxes that write back to INDEX.md, drag-and-drop uploads into
Stage 01 / 02 folders, a one-click acceptance-gate runner, an "add
exception" form, and download buttons for every PDF the toolkit produces.

Launch with the bundled double-click launcher
(`Start Migration Dashboard.command` on macOS, `.bat` on Windows,
`start_dashboard.sh` on Linux), or directly:

    pip install -r requirements.txt
    streamlit run dashboard.py
"""

from __future__ import annotations

import csv
import io
import re
import subprocess
import sys
import tempfile
from datetime import datetime, date
from pathlib import Path

import pandas as pd
import streamlit as st

from migration import (  # type: ignore[import-not-found]
    INDEX,
    PLAN,
    ROOT,
    SCRIPTS,
    STATUS_SYMBOLS,
    parse_index,
)
from _paste_parser import parse_pasted_table, to_csv_bytes


# --------------------------------------------------------------------------- #
# Page config                                                                 #
# --------------------------------------------------------------------------- #

# Cross-platform scratch dir. Resolves to /tmp on Linux/macOS, %TEMP% (e.g.
# C:\Users\<u>\AppData\Local\Temp) on Windows. Hard-coding "/tmp" broke the
# dashboard on Windows — PDF generation and the preflight validators both
# write here.
TMPDIR = Path(tempfile.gettempdir())

st.set_page_config(
    page_title="MYOB → Xero migration",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


SYMBOL_LABELS = {
    "⬜": "⬜ todo",
    "🟡": "🟡 in progress",
    "🟢": "🟢 done",
    "⚠": "⚠ exception",
}
SYMBOL_ORDER = list(SYMBOL_LABELS.keys())


# --------------------------------------------------------------------------- #
# Read helpers (cached)                                                       #
# --------------------------------------------------------------------------- #


@st.cache_data(ttl=5)
def load_text(path_str: str) -> str:
    p = Path(path_str)
    return p.read_text(encoding="utf-8") if p.exists() else ""


@st.cache_data(ttl=5)
def load_csv(path_str: str) -> pd.DataFrame:
    p = Path(path_str)
    if not p.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(p, encoding="utf-8-sig", dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def refresh() -> None:
    """Drop caches and rerun — call after any write."""
    load_text.clear()
    load_csv.clear()
    st.rerun()


def index_text() -> str:
    return load_text(str(INDEX))


def plan_text() -> str:
    return load_text(str(PLAN))


# --------------------------------------------------------------------------- #
# Write helpers (safe, targeted edits)                                        #
# --------------------------------------------------------------------------- #


_STAGE_HEADER_RE = re.compile(r"^## (0[1-4]) — ")
_INDEX_FIELD_RE = lambda label: re.compile(  # noqa: E731
    rf"(\|\s*{re.escape(label)}\s*\|\s*)([^|]+?)(\s*\|)"
)


def replace_field(text: str, label: str, value: str) -> str:
    return _INDEX_FIELD_RE(label).sub(rf"\g<1>{value}\3", text, count=1)


def update_engagement_params(values: dict[str, str]) -> list[tuple[str, str]]:
    """Update INDEX.md + PLAN.md engagement-parameter rows. Returns log."""
    INDEX_FIELDS = {
        "client": "Client / entity",
        "conversion_date": "Conversion date",
        "xero_org_target": "Xero org target",
        "lead": "Lead accountant",
    }
    PLAN_FIELDS = {
        "client": "Client / entity name",
        "abn": "ABN",
        "conversion_date": "Conversion date (first day reported in Xero)",
        "myob_product": "MYOB product (AccountRight Live / Essentials / Business)",
        "xero_plan": "Xero plan target (Starter / Standard / Premium / Ultimate)",
        "gst": "GST registered (Y/N) and reporting cycle",
        "payroll": "Payroll in scope (Y/N), STP phase",
        "inventory": "Inventory tracked (Y/N)",
    }
    log: list[tuple[str, str]] = []

    idx_text = INDEX.read_text(encoding="utf-8")
    for key, label in INDEX_FIELDS.items():
        v = values.get(key, "").strip()
        if v:
            new = replace_field(idx_text, label, v)
            if new != idx_text:
                log.append((f"INDEX.md / {label}", v))
                idx_text = new
    INDEX.write_text(idx_text, encoding="utf-8")

    pl_text = PLAN.read_text(encoding="utf-8")
    for key, label in PLAN_FIELDS.items():
        v = values.get(key, "").strip()
        if v:
            new = replace_field(pl_text, label, v)
            if new != pl_text:
                log.append((f"PLAN.md / {label}", v))
                pl_text = new
    PLAN.write_text(pl_text, encoding="utf-8")
    return log


def set_row_status(stage_num: str, row_key: str, new_symbol: str) -> bool:
    """Find the row in a Stage table containing row_key, replace its status."""
    if new_symbol not in SYMBOL_ORDER:
        return False
    lines = INDEX.read_text(encoding="utf-8").splitlines(keepends=True)
    in_stage = False
    for i, line in enumerate(lines):
        m = _STAGE_HEADER_RE.match(line)
        if m:
            in_stage = m.group(1) == stage_num
            continue
        if in_stage and line.startswith("|") and row_key in line:
            for sym in SYMBOL_ORDER:
                if sym in line:
                    lines[i] = line.replace(sym, new_symbol, 1)
                    INDEX.write_text("".join(lines), encoding="utf-8")
                    return True
    return False


def safe_subpath(stage_dir: Path, subfolder: str, filename: str) -> Path | None:
    """Reject path traversal; return resolved path inside stage_dir or None."""
    base = (stage_dir / subfolder).resolve()
    if not str(base).startswith(str(stage_dir.resolve())):
        return None
    safe_name = Path(filename).name  # strip any directory component
    return base / safe_name


def append_exception(row: dict) -> None:
    path = ROOT / "04_xero_post_upload_checks/05_exception_log/exceptions.csv"
    fieldnames = [
        "date_raised",
        "raised_by",
        "area",
        "account_or_contact",
        "variance",
        "root_cause",
        "resolution",
        "resolved_date",
        "resolved_by",
    ]
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        if write_header:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in fieldnames})


# --------------------------------------------------------------------------- #
# Subfolder maps (which folders each stage page exposes for uploads)          #
# --------------------------------------------------------------------------- #

STAGE_DIRS = {
    "01": ROOT / "01_exports_from_myob",
    "02": ROOT / "02_cleansed_for_xero",
    "03": ROOT / "03_finalized_reports",
    "04": ROOT / "04_xero_post_upload_checks",
}


def stage_subfolders(stage_num: str) -> list[str]:
    """Sorted list of subfolder names under the given stage."""
    base = STAGE_DIRS[stage_num]
    return sorted(
        p.name for p in base.iterdir() if p.is_dir() and not p.name.startswith(".")
    )


# --------------------------------------------------------------------------- #
# Table parsing                                                               #
# --------------------------------------------------------------------------- #

STAGE_TABLE_RE = re.compile(
    r"^## (0[1-4]) — (?P<title>.+?)\s*$\n(?P<body>(?:^\|.*$\n?)+)",
    re.MULTILINE,
)


def stage_dataframe(stage_number: str) -> pd.DataFrame:
    for m in STAGE_TABLE_RE.finditer(index_text()):
        if m.group(1) == stage_number:
            return _md_table_to_df(m.group("body"))
    return pd.DataFrame()


def _md_table_to_df(body: str) -> pd.DataFrame:
    rows: list[list[str]] = []
    for raw in body.strip().splitlines():
        if not raw.strip().startswith("|"):
            continue
        cells = [c.strip() for c in raw.strip().strip("|").split("|")]
        if all(re.fullmatch(r"-+", c) for c in cells if c):
            continue
        rows.append(cells)
    if not rows:
        return pd.DataFrame()
    headers, *data = rows
    width = len(headers)
    data = [r + [""] * (width - len(r)) if len(r) < width else r[:width] for r in data]
    return pd.DataFrame(data, columns=headers)


def first_status_symbol(row_text: str) -> str | None:
    for sym in SYMBOL_ORDER:
        if sym in row_text:
            return sym
    return None


# --------------------------------------------------------------------------- #
# Sidebar                                                                     #
# --------------------------------------------------------------------------- #

with st.sidebar:
    st.title("📊 Migration workspace")
    st.caption(f"`{ROOT}`")
    st.divider()
    page = st.radio(
        "View",
        [
            "Overview",
            "Stage 01 — Exports",
            "Stage 02 — Cleansed",
            "Stage 03 — Reports",
            "Stage 04 — Verification",
            "Paste from MYOB Business",
            "Exceptions",
            "Action Checklist",
            "Downloads",
            "About",
        ],
        index=0,
    )
    st.divider()
    if st.button("↻ Refresh", width="stretch"):
        refresh()
    st.caption(f"Loaded {datetime.now():%H:%M:%S}")


# --------------------------------------------------------------------------- #
# Page: Overview                                                              #
# --------------------------------------------------------------------------- #


def field(text: str, label: str) -> str:
    m = re.search(rf"\|\s*{re.escape(label)}\s*\|\s*([^|]+?)\s*\|", text)
    return m.group(1).strip() if m else "_TBD_"


def page_overview() -> None:
    st.title("MYOB → Xero migration")
    txt = index_text()
    head = st.columns(4)
    head[0].metric("Client", field(txt, "Client / entity"))
    head[1].metric("Conversion date", field(txt, "Conversion date"))
    head[2].metric("Xero org", field(txt, "Xero org target"))
    head[3].metric("Lead", field(txt, "Lead accountant"))

    with st.expander(
        "🚀 Set up a new engagement (or update parameters)", expanded=False
    ):
        st.caption(
            "Fills the engagement-parameter rows in INDEX.md and PLAN.md. "
            "Leave a field blank to keep its existing value."
        )
        with st.form("init", clear_on_submit=False):
            c1, c2 = st.columns(2)
            client = c1.text_input("Client / entity", value="")
            abn = c2.text_input("ABN", value="")
            c3, c4 = st.columns(2)
            conv_date = c3.date_input(
                "Conversion date", value=None, format="YYYY-MM-DD"
            )
            xero_org = c4.selectbox(
                "Target Xero org", options=["", "new", "existing"], index=0
            )
            c5, c6 = st.columns(2)
            myob_prod = c5.selectbox(
                "MYOB product",
                options=["", "AccountRight Live", "Essentials", "Business"],
                index=0,
            )
            xero_plan = c6.selectbox(
                "Xero plan target",
                options=["", "Starter", "Standard", "Premium", "Ultimate"],
                index=0,
            )
            c7, c8 = st.columns(2)
            gst = c7.text_input("GST (Y/N, cycle)", value="")
            payroll = c8.text_input("Payroll (Y/N, STP phase)", value="")
            c9, c10 = st.columns(2)
            inv = c9.text_input("Inventory tracked (Y/N)", value="")
            lead = c10.text_input("Lead accountant", value="")

            submitted = st.form_submit_button("Save engagement parameters")
            if submitted:
                values = {
                    "client": client,
                    "abn": abn,
                    "conversion_date": conv_date.isoformat() if isinstance(conv_date, date) else "",
                    "xero_org_target": xero_org,
                    "myob_product": myob_prod,
                    "xero_plan": xero_plan,
                    "gst": gst,
                    "payroll": payroll,
                    "inventory": inv,
                    "lead": lead,
                }
                log = update_engagement_params(values)
                if log:
                    st.success(f"Updated {len(log)} field(s).")
                    for where, val in log:
                        st.write(f"• `{where}` → `{val}`")
                    refresh()
                else:
                    st.info("Nothing changed (no values supplied).")

    st.divider()
    st.subheader("Pipeline progress")
    stages = parse_index(txt)
    grid = st.columns(4)
    for stage, col in zip(stages, grid):
        with col:
            st.markdown(f"**Stage {stage.name.split()[0]}**")
            short = re.sub(r"\s*\(.*\)\s*$", "", stage.name)
            st.caption(" ".join(short.split()[1:]) or short)
            pct = stage.pct / 100.0 if stage.total else 0.0
            st.progress(pct, text=f"{stage.done}/{stage.total}  ({stage.pct:.1f}%)")
            badges = []
            if stage.counts.get("wip"):
                badges.append(f"🟡 {stage.counts['wip']} wip")
            if stage.counts.get("exception"):
                badges.append(f"⚠ {stage.counts['exception']} exc")
            if stage.counts.get("todo"):
                badges.append(f"⬜ {stage.counts['todo']} todo")
            st.caption(" · ".join(badges) if badges else "🟢 all done")

    st.divider()
    st.subheader("Roll-up")
    exceptions = load_csv(
        str(ROOT / "04_xero_post_upload_checks/05_exception_log/exceptions.csv")
    )
    clearing = load_csv(
        str(
            ROOT
            / "04_xero_post_upload_checks/03_balance_reconciliations/clearing_accounts_tracker.csv"
        )
    )
    tb_diff = load_csv(
        str(
            ROOT
            / "04_xero_post_upload_checks/01_account_by_account_checklists/trial_balance_diff.csv"
        )
    )
    open_exc = (
        len(
            exceptions[
                exceptions.get("resolved_date", "").astype(str).str.strip() == ""
            ]
        )
        if not exceptions.empty and "resolved_date" in exceptions.columns
        else 0
    )
    clearing_total = len(clearing)
    clearing_done = (
        len(
            clearing[
                clearing.get("status", "")
                .astype(str)
                .str.strip()
                .isin(["🟢", "done"])
            ]
        )
        if clearing_total and "status" in clearing.columns
        else 0
    )
    if tb_diff.empty:
        gate_label = "not yet run"
    else:
        fails = (
            tb_diff[tb_diff.get("status", "").astype(str).str.strip() == "FAIL"]
            if "status" in tb_diff.columns
            else tb_diff.iloc[0:0]
        )
        gate_label = "PASS" if fails.empty else f"FAIL ({len(fails)})"

    c1, c2, c3 = st.columns(3)
    c1.metric("Open exceptions", open_exc)
    c2.metric(
        "Clearing accts at NIL",
        f"{clearing_done}/{clearing_total}" if clearing_total else "—",
    )
    c3.metric("Acceptance gate", gate_label)


# --------------------------------------------------------------------------- #
# Pages: per-stage workspace                                                  #
# --------------------------------------------------------------------------- #


def page_stage(stage_num: str, title: str) -> None:
    st.title(f"Stage {stage_num} — {title}")
    df = stage_dataframe(stage_num)
    if df.empty:
        st.info("No table found for this stage in INDEX.md.")
        return

    # Status editor
    st.subheader("Update artefact status")
    st.caption("Pick a new status to write it back to INDEX.md immediately.")
    name_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
    for i, row in df.iterrows():
        row_blob = " | ".join(str(v) for v in row.values)
        current = first_status_symbol(row_blob) or "⬜"
        c_label, c_status = st.columns([5, 2])
        with c_label:
            st.markdown(f"**{row[name_col]}**  \n_{row.iloc[0]}_")
        with c_status:
            new = st.selectbox(
                "status",
                options=SYMBOL_ORDER,
                format_func=lambda s: SYMBOL_LABELS[s],
                index=SYMBOL_ORDER.index(current),
                key=f"s_{stage_num}_{i}",
                label_visibility="collapsed",
            )
            if new != current:
                key = str(row[name_col])
                if set_row_status(stage_num, key, new):
                    st.toast(f"{key}: {current} → {new}", icon="✅")
                    refresh()

    # File uploader (only for Stages 01 and 02 where we receive files)
    if stage_num in {"01", "02"}:
        st.divider()
        st.subheader("Drop files into a stage subfolder")
        subfolders = stage_subfolders(stage_num)
        if subfolders:
            sub = st.selectbox(
                "Destination subfolder",
                options=subfolders,
                key=f"sub_{stage_num}",
            )
            uploads = st.file_uploader(
                "Files to upload",
                accept_multiple_files=True,
                key=f"up_{stage_num}",
            )
            if uploads and st.button("Save uploads", key=f"save_{stage_num}"):
                ok = []
                for f in uploads:
                    target = safe_subpath(STAGE_DIRS[stage_num], sub, f.name)
                    if target is None:
                        st.error(f"Refused unsafe path: {f.name}")
                        continue
                    target.write_bytes(f.getbuffer())
                    ok.append(str(target.relative_to(ROOT)))
                st.success(f"Saved {len(ok)} file(s).")
                for p in ok:
                    st.code(p, language="text")

    # Stage-02 only: per-file validator
    if stage_num == "02":
        st.divider()
        st.subheader("Validate a cleansed CSV against its Xero template")
        templates = sorted(
            (ROOT / "templates" / "xero_csv_templates").glob("*.csv")
        )
        col_a, col_b = st.columns(2)
        cleansed = col_a.file_uploader(
            "Cleansed CSV", type=["csv"], key="val_cleansed"
        )
        tmpl_name = col_b.selectbox(
            "Xero template",
            options=[t.name for t in templates],
            key="val_tmpl",
        )
        if cleansed and st.button("Run validator", key="val_run"):
            with st.spinner("Running preflight validation..."):
                tmp = TMPDIR / f"_validate_{cleansed.name}"
                tmp.write_bytes(cleansed.getbuffer())
                tmpl_path = ROOT / "templates" / "xero_csv_templates" / tmpl_name
                result = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPTS / "validate_xero_csv.py"),
                        str(tmp),
                        str(tmpl_path),
                    ],
                    capture_output=True,
                    text=True,
                )
            if result.returncode == 0:
                st.success("PASS — template matches and required cells are present.")
            else:
                st.error(f"FAIL (exit {result.returncode})")
            with st.expander("Validator output"):
                st.code(result.stdout or result.stderr, language="text")

    # Stage-04 only: acceptance gate runner
    if stage_num == "04":
        st.divider()
        st.subheader("🚦 Trial-balance acceptance gate")
        st.caption(
            "Upload the locked MYOB TB and the freshly-exported Xero TB. "
            "Each CSV needs columns: account_code, account_name, debit, credit."
        )
        c1, c2, c3 = st.columns([3, 3, 1])
        myob_csv = c1.file_uploader("MYOB TB", type=["csv"], key="gate_myob")
        xero_csv = c2.file_uploader("Xero TB", type=["csv"], key="gate_xero")
        tolerance = c3.text_input("Tolerance ($)", value="1.00", key="gate_tol")
        if myob_csv and xero_csv and st.button("Run acceptance gate", key="gate_run"):
            with st.spinner("Diffing trial balances..."):
                m_tmp = TMPDIR / "_gate_myob.csv"
                x_tmp = TMPDIR / "_gate_xero.csv"
                m_tmp.write_bytes(myob_csv.getbuffer())
                x_tmp.write_bytes(xero_csv.getbuffer())
                out_dir = (
                    ROOT
                    / "04_xero_post_upload_checks/01_account_by_account_checklists"
                )
                result = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPTS / "post_upload_acceptance_check.py"),
                        "--myob",
                        str(m_tmp),
                        "--xero",
                        str(x_tmp),
                        "--out",
                        str(out_dir),
                        "--tolerance",
                        tolerance,
                    ],
                    capture_output=True,
                    text=True,
                )
            if result.returncode == 0:
                st.success("PASS — every account within tolerance. Stage 04 cleared.")
            else:
                st.error(f"FAIL — at least one variance breached tolerance.")
            st.code(result.stdout or result.stderr, language="text")
            diff_path = out_dir / "trial_balance_diff.csv"
            if diff_path.exists():
                st.dataframe(
                    load_csv(str(diff_path)),
                    width="stretch",
                    hide_index=True,
                )


# --------------------------------------------------------------------------- #
# Page: Exceptions                                                            #
# --------------------------------------------------------------------------- #


def page_exceptions() -> None:
    st.title("⚠ Exception log")
    df = load_csv(
        str(ROOT / "04_xero_post_upload_checks/05_exception_log/exceptions.csv")
    )

    with st.expander("➕ Add a new exception", expanded=False):
        with st.form("add_exc", clear_on_submit=True):
            c1, c2 = st.columns(2)
            d = c1.date_input("Date raised", value=date.today(), format="YYYY-MM-DD")
            by = c2.text_input("Raised by")
            c3, c4 = st.columns(2)
            area = c3.text_input(
                "Area (e.g. AR, AP, payroll, GST, privacy-incident)"
            )
            acct = c4.text_input("Account or contact")
            c5, c6 = st.columns(2)
            var = c5.text_input("Variance ($)")
            cause = c6.text_input("Root cause")
            resolution = st.text_area("Resolution (leave blank if not yet resolved)")
            submitted = st.form_submit_button("Add exception")
            if submitted:
                append_exception(
                    {
                        "date_raised": d.isoformat(),
                        "raised_by": by,
                        "area": area,
                        "account_or_contact": acct,
                        "variance": var,
                        "root_cause": cause,
                        "resolution": resolution,
                        "resolved_date": "",
                        "resolved_by": "",
                    }
                )
                st.success("Exception added.")
                refresh()

    if df.empty:
        st.info("No exceptions logged.")
        return
    open_only = st.toggle("Show only open exceptions", value=True)
    show = df.copy()
    if open_only and "resolved_date" in show.columns:
        show = show[show["resolved_date"].astype(str).str.strip() == ""]
    st.caption(f"{len(show)} row(s)")
    st.dataframe(show, width="stretch", hide_index=True)


# --------------------------------------------------------------------------- #
# Page: Action Checklist                                                      #
# --------------------------------------------------------------------------- #


def page_action_checklist() -> None:
    st.title("📋 Conversion Action Checklist")
    md = load_text(
        str(
            ROOT
            / "04_xero_post_upload_checks/06_final_sign_off/action_checklist_template.md"
        )
    )
    if not md:
        st.warning("Action Checklist template not found.")
        return
    st.caption("Client-facing summary delivered at sign-off.")
    st.download_button(
        "⬇ Download as Markdown",
        data=md.encode("utf-8"),
        file_name="action_checklist.md",
        mime="text/markdown",
    )
    st.markdown(md)


# --------------------------------------------------------------------------- #
# Page: Downloads                                                             #
# --------------------------------------------------------------------------- #


def _generate_pdf(subcommand: str, output_name: str) -> bytes | None:
    """Run `python migration.py <subcommand>` into the OS scratch dir, return bytes."""
    out = TMPDIR / output_name
    result = subprocess.run(
        [sys.executable, str(ROOT / "migration.py"), subcommand, "-o", str(out)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        st.error(f"{subcommand} failed (exit {result.returncode})")
        st.code(result.stderr or result.stdout, language="text")
        return None
    return out.read_bytes() if out.exists() else None


def page_downloads() -> None:
    st.title("⬇ Downloads")
    st.caption(
        "Generate the PDF deliverables on demand. Each one is built from the "
        "current INDEX.md and tracker CSVs."
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("### One-page status report")
        st.caption("A4 PDF suitable for emailing to the client / partner.")
        if st.button("Generate status PDF", key="dl_status"):
            data = _generate_pdf("report", "status_report.pdf")
            if data:
                st.session_state["pdf_status"] = data
        if "pdf_status" in st.session_state:
            st.download_button(
                "⬇ Download status_report.pdf",
                data=st.session_state["pdf_status"],
                file_name="status_report.pdf",
                mime="application/pdf",
            )

    with c2:
        st.markdown("### Visual Getting-Started guide")
        st.caption("Seven-page A4 onboarding pack for a new team member.")
        if st.button("Generate guide PDF", key="dl_guide"):
            data = _generate_pdf("guide", "getting_started_visual.pdf")
            if data:
                st.session_state["pdf_guide"] = data
        if "pdf_guide" in st.session_state:
            st.download_button(
                "⬇ Download getting_started_visual.pdf",
                data=st.session_state["pdf_guide"],
                file_name="getting_started_visual.pdf",
                mime="application/pdf",
            )

    with c3:
        st.markdown("### Action Checklist (Markdown)")
        st.caption("Client-facing sign-off summary.")
        md = load_text(
            str(
                ROOT
                / "04_xero_post_upload_checks/06_final_sign_off/action_checklist_template.md"
            )
        )
        if md:
            st.download_button(
                "⬇ Download action_checklist.md",
                data=md.encode("utf-8"),
                file_name="action_checklist.md",
                mime="text/markdown",
            )
        else:
            st.info("Template not found.")


# --------------------------------------------------------------------------- #
# Page: About                                                                 #
# --------------------------------------------------------------------------- #


def page_paste_myob() -> None:
    st.title("📋 Paste from MYOB Business")
    st.caption(
        "MYOB Business has no CSV export for chart of accounts, customers, "
        "suppliers, or items — you copy from the screen and the clipboard "
        "pastes one cell per line into Excel. Paste that mess here and we "
        "reshape it into a clean table you can fix in-place, then save."
    )

    st.warning(
        "**Paste directly into the box below — do not paste into Excel first.** "
        "Excel auto-converts MYOB codes like `1-9000` into dates "
        "(`1950-01-01`), silently corrupting your chart of accounts. "
        "This dashboard reads the clipboard as text and preserves the "
        "original codes."
    )

    with st.expander("How to copy from MYOB Business", expanded=False):
        st.markdown(
            "1. Open the screen you want (e.g. **Accounting ▸ Chart of accounts**).\n"
            "2. Click into the table, press **Ctrl+A** then **Ctrl+C** "
            "(macOS: **⌘+A** / **⌘+C**).\n"
            "3. Paste **directly into the box below** — not into Excel.\n"
            "4. The parser auto-detects the layout:\n"
            "   - the MYOB Business 'Select row N' format (chart of accounts, "
            "contacts, items — every list screen),\n"
            "   - tab-separated rows,\n"
            "   - multi-space-separated rows,\n"
            "   - or generic single-column reshape from account-code pattern.\n"
            "5. Fix any misparsed cells in the editor that appears.\n"
            "6. Save to a Stage 01 sub-folder.\n"
            "\n"
            "**If you've already pasted into Excel** and want to recover what "
            "you can: copy column A from Excel and paste it here. The parser "
            "will still align the columns correctly and flag every code "
            "Excel turned into a date so you can fix them manually."
        )

    if "paste_text" not in st.session_state:
        st.session_state["paste_text"] = ""
    if "paste_df" not in st.session_state:
        st.session_state["paste_df"] = None

    text = st.text_area(
        "Paste here",
        value=st.session_state["paste_text"],
        height=240,
        placeholder="Paste the copied table here — header row + data, "
        "or one cell per line if you copied from MYOB Business.",
        key="paste_input",
    )

    c1, c2 = st.columns([1, 5])
    if c1.button("Parse", type="primary"):
        st.session_state["paste_text"] = text
        df, meta = parse_pasted_table(text)
        st.session_state["paste_df"] = df
        st.session_state["paste_meta"] = meta

    if c2.button("Clear"):
        st.session_state["paste_text"] = ""
        st.session_state["paste_df"] = None
        st.session_state.pop("paste_meta", None)
        st.rerun()

    df = st.session_state.get("paste_df")
    if df is None or df.empty:
        if df is not None and df.empty and st.session_state.get("paste_meta"):
            st.warning(
                "Could not detect a tabular structure. Try copying again "
                "with all rows selected, or paste a header row above the "
                "data."
            )
        return

    meta = st.session_state.get("paste_meta", {})
    strat = meta.get("strategy", "?")
    stride = meta.get("stride")
    label = {
        "tab": "tab-separated",
        "pipe": "pipe-separated",
        "multispace": "multi-space-separated",
        "single_column_reshape": f"single-column → reshaped to {stride} columns",
        "myob_business": "MYOB Business 'Select row N' format",
    }.get(strat, strat)
    dropped = meta.get("dropped", 0)
    note = f"Detected layout: **{label}** · {len(df)} row(s) parsed"
    if dropped:
        note += f" · {dropped} group-heading row(s) dropped"
    st.info(note)

    corrupted = meta.get("date_corrupted_codes", 0)
    if corrupted:
        st.error(
            f"⚠ Excel date-corruption detected: **{corrupted}** account code(s) "
            "look like dates (e.g. `1950-01-01`). This happens when "
            "MYOB codes like `1-9000` are pasted through Excel — Excel "
            "interprets them as January 9000 and rewrites them as date "
            "serials. Fix these in the **Code** column below before "
            "saving, or re-copy from MYOB Business and paste directly here."
        )

    st.subheader("Review & fix")
    st.caption(
        "Edit any cell directly. Click a column header to rename it — "
        "Xero is picky about column names later, so set them now."
    )
    edited = st.data_editor(
        df,
        width="stretch",
        num_rows="dynamic",
        key="paste_editor",
    )

    st.subheader("Save")
    save_choice = st.radio(
        "Where should this go?",
        options=[
            "Download CSV (don't save to the project)",
            "Save into a Stage 01 sub-folder",
        ],
        horizontal=False,
        key="paste_save_choice",
    )

    if save_choice.startswith("Download"):
        filename = st.text_input(
            "File name", value="chart_of_accounts_pasted.csv", key="paste_dl_name"
        )
        st.download_button(
            "⬇ Download CSV",
            data=to_csv_bytes(edited),
            file_name=filename or "pasted.csv",
            mime="text/csv",
        )
    else:
        stage_dir = ROOT / "01_exports_from_myob"
        subfolders = sorted(
            p.name for p in stage_dir.iterdir() if p.is_dir() and not p.name.startswith(".")
        )
        default_idx = (
            subfolders.index("01_chart_of_accounts")
            if "01_chart_of_accounts" in subfolders
            else 0
        )
        sub = st.selectbox(
            "Sub-folder", options=subfolders, index=default_idx, key="paste_subdir"
        )
        default_name = (
            "chart_of_accounts_pasted.csv"
            if sub == "01_chart_of_accounts"
            else f"{sub}_pasted.csv"
        )
        filename = st.text_input(
            "File name", value=default_name, key="paste_save_name"
        )
        if st.button("💾 Save to project", type="primary", key="paste_save_btn"):
            target = safe_subpath(stage_dir, sub, filename or "pasted.csv")
            if target is None:
                st.error(f"Refused unsafe path: {filename}")
            else:
                target.write_bytes(to_csv_bytes(edited))
                rel = target.relative_to(ROOT)
                st.success(f"Saved → `{rel}`")
                st.caption(
                    "Don't forget to tick the corresponding row on the "
                    "**Stage 01 — Exports** page."
                )


def page_about() -> None:
    st.title("About this workspace")
    st.markdown(
        f"""
        Interactive workspace for the MYOB → Xero migration toolkit. Every
        view here writes back to the toolkit's own files (INDEX.md and the
        Stage-04 tracker CSVs) — there is no separate database.

        **Toolkit root:** `{ROOT}`

        **What you can do without leaving the browser:**

        - Set up a new engagement (Overview ▸ "Set up a new engagement")
        - Update artefact status per row (Stage 01–04 pages)
        - Upload files into Stage 01 / Stage 02 subfolders
        - Validate a Stage-02 CSV against a Xero template
        - Run the Stage-04 trial-balance acceptance gate
        - Add an entry to the exception log
        - Generate and download the three PDF deliverables
        """
    )
    st.divider()
    st.warning(
        "**Privacy reminder.** If this dashboard is rendering real client "
        "data, run it locally only (`streamlit run dashboard.py` or the "
        "double-click launcher). Do not expose the port; do not deploy with "
        "payroll data to any public host. See `PRIVACY.md`."
    )


# --------------------------------------------------------------------------- #
# Router                                                                      #
# --------------------------------------------------------------------------- #

PAGES = {
    "Overview": page_overview,
    "Stage 01 — Exports": lambda: page_stage("01", "Exports from MYOB"),
    "Stage 02 — Cleansed": lambda: page_stage("02", "Cleansed for Xero"),
    "Stage 03 — Reports": lambda: page_stage("03", "Finalized reports"),
    "Stage 04 — Verification": lambda: page_stage("04", "Xero post-upload checks"),
    "Paste from MYOB Business": page_paste_myob,
    "Exceptions": page_exceptions,
    "Action Checklist": page_action_checklist,
    "Downloads": page_downloads,
    "About": page_about,
}

PAGES[page]()
