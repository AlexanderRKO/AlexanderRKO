"""Streamlit dashboard for the MYOB → Xero migration toolkit.

Run from the toolkit root:

    pip install -r requirements.txt
    streamlit run dashboard.py

The dashboard is read-only — it visualises the same `INDEX.md` and
Stage-04 trackers that `python migration.py status` reads, plus the
exception log and the live Trial-Balance diff. Nothing here modifies
client data.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from migration import (  # type: ignore[import-not-found]
    INDEX,
    PLAN,
    ROOT,
    STATUS_SYMBOLS,
    parse_index,
)


# --------------------------------------------------------------------------- #
# Page config + global styling                                                #
# --------------------------------------------------------------------------- #

st.set_page_config(
    page_title="MYOB → Xero migration",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _client_header_field(text: str, label: str) -> str:
    m = re.search(rf"\|\s*{re.escape(label)}\s*\|\s*([^|]+?)\s*\|", text)
    return m.group(1).strip() if m else "_TBD_"


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, encoding="utf-8-sig")
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    return df


# --------------------------------------------------------------------------- #
# Sidebar                                                                     #
# --------------------------------------------------------------------------- #

with st.sidebar:
    st.title("📊 Migration dashboard")
    st.caption(f"Toolkit root: `{ROOT}`")
    st.divider()

    page = st.radio(
        "View",
        [
            "Overview",
            "Stage 01 — Exports",
            "Stage 02 — Cleansed",
            "Stage 03 — Reports",
            "Stage 04 — Verification",
            "Exceptions",
            "Action Checklist",
            "About",
        ],
        index=0,
    )

    st.divider()
    if st.button("↻ Refresh", width="stretch"):
        st.rerun()
    st.caption(f"Loaded at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


# --------------------------------------------------------------------------- #
# Data loaders (cached for snappy navigation)                                 #
# --------------------------------------------------------------------------- #


@st.cache_data(ttl=10)
def load_index_text() -> str:
    return INDEX.read_text(encoding="utf-8") if INDEX.exists() else ""


@st.cache_data(ttl=10)
def load_plan_text() -> str:
    return PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""


@st.cache_data(ttl=10)
def load_stages():
    return parse_index(load_index_text())


@st.cache_data(ttl=10)
def load_csv(path_str: str) -> pd.DataFrame:
    return _read_csv(Path(path_str))


@st.cache_data(ttl=10)
def load_markdown(path_str: str) -> str:
    p = Path(path_str)
    return p.read_text(encoding="utf-8") if p.exists() else ""


index_text = load_index_text()
stages = load_stages()
exceptions = load_csv(
    str(ROOT / "04_xero_post_upload_checks/05_exception_log/exceptions.csv")
)
clearing = load_csv(
    str(
        ROOT
        / "04_xero_post_upload_checks/03_balance_reconciliations/clearing_accounts_tracker.csv"
    )
)
equity_check = load_csv(
    str(
        ROOT
        / "04_xero_post_upload_checks/03_balance_reconciliations/equity_vs_net_profit_check.csv"
    )
)
tb_diff = load_csv(
    str(
        ROOT
        / "04_xero_post_upload_checks/01_account_by_account_checklists/trial_balance_diff.csv"
    )
)


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


STAGE_TABLE_RE = re.compile(
    r"^## (0[1-4]) — (?P<title>.+?)\s*$\n(?P<body>(?:^\|.*$\n?)+)",
    re.MULTILINE,
)


def stage_dataframe(stage_number: str) -> pd.DataFrame:
    """Return the markdown table for a given stage as a DataFrame."""
    for m in STAGE_TABLE_RE.finditer(index_text):
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


def status_breakdown(df: pd.DataFrame) -> dict[str, int]:
    counts = {k: 0 for k in STATUS_SYMBOLS}
    if df.empty:
        return counts
    blob = "\n".join(df.astype(str).agg(" | ".join, axis=1))
    for key, sym in STATUS_SYMBOLS.items():
        counts[key] = blob.count(sym)
    return counts


def render_stage_view(stage_number: str, title: str) -> None:
    st.header(f"Stage {stage_number} — {title}")
    df = stage_dataframe(stage_number)
    if df.empty:
        st.info("No table found for this stage in INDEX.md.")
        return

    counts = status_breakdown(df)
    total = sum(counts.values())
    done = counts["done"]
    cols = st.columns(4)
    cols[0].metric("Total artefacts", total)
    cols[1].metric("Done", done)
    cols[2].metric("In progress", counts["wip"])
    cols[3].metric("Exceptions", counts["exception"])
    if total:
        st.progress(done / total, text=f"{done}/{total} done ({100*done/total:.1f}%)")
    st.divider()
    st.dataframe(df, width="stretch", hide_index=True)


# --------------------------------------------------------------------------- #
# Page: Overview                                                              #
# --------------------------------------------------------------------------- #


def page_overview() -> None:
    st.title("MYOB → Xero migration")

    client = _client_header_field(index_text, "Client / entity")
    conv = _client_header_field(index_text, "Conversion date")
    org_target = _client_header_field(index_text, "Xero org target")
    lead = _client_header_field(index_text, "Lead accountant")

    head = st.columns(4)
    head[0].metric("Client", client)
    head[1].metric("Conversion date", conv)
    head[2].metric("Xero org", org_target)
    head[3].metric("Lead", lead)

    st.divider()
    st.subheader("Pipeline progress")

    grid = st.columns(4)
    for stage, col in zip(stages, grid):
        with col:
            st.markdown(f"**Stage {stage.name.split()[0]}**")
            short = re.sub(r"\s*\(.*\)\s*$", "", stage.name)
            st.caption(" ".join(short.split()[1:]) or short)
            pct = stage.pct / 100.0 if stage.total else 0.0
            st.progress(pct, text=f"{stage.done}/{stage.total}  ({stage.pct:.1f}%)")
            counts = stage.counts
            wip = counts.get("wip", 0)
            exc = counts.get("exception", 0)
            todo = counts.get("todo", 0)
            badges = []
            if wip:
                badges.append(f"🟡 {wip} wip")
            if exc:
                badges.append(f"⚠ {exc} exc")
            if todo:
                badges.append(f"⬜ {todo} todo")
            st.caption(" · ".join(badges) if badges else "🟢 all done")

    st.divider()
    st.subheader("Roll-up")

    open_exc = (
        len(exceptions[exceptions.get("resolved_date", "").astype(str).str.strip() == ""])
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
        gate_delta = None
    else:
        fails = (
            tb_diff[tb_diff.get("status", "").astype(str).str.strip() == "FAIL"]
            if "status" in tb_diff.columns
            else tb_diff.iloc[0:0]
        )
        gate_label = "PASS" if fails.empty else f"FAIL ({len(fails)})"
        gate_delta = (
            None if fails.empty else f"{len(fails)} accounts breach tolerance"
        )

    cols = st.columns(3)
    cols[0].metric("Open exceptions", open_exc, delta=None if open_exc == 0 else f"+{open_exc}", delta_color="inverse")
    cols[1].metric("Clearing accts at NIL", f"{clearing_done}/{clearing_total}" if clearing_total else "—")
    cols[2].metric("Acceptance gate", gate_label, delta=gate_delta, delta_color="inverse" if gate_delta else "off")

    if not equity_check.empty and "variance" in equity_check.columns:
        st.divider()
        st.subheader("Equity vs Net Profit reconciliation")
        st.dataframe(equity_check, width="stretch", hide_index=True)


# --------------------------------------------------------------------------- #
# Page: Exceptions                                                            #
# --------------------------------------------------------------------------- #


def page_exceptions() -> None:
    st.title("⚠ Exception log")
    if exceptions.empty:
        st.success("No exceptions logged.")
        return
    open_filter = st.toggle("Show only open exceptions", value=True)
    df = exceptions.copy()
    if open_filter and "resolved_date" in df.columns:
        df = df[df["resolved_date"].astype(str).str.strip() == ""]
    st.caption(f"{len(df)} row(s)")
    st.dataframe(df, width="stretch", hide_index=True)


# --------------------------------------------------------------------------- #
# Page: Action Checklist                                                      #
# --------------------------------------------------------------------------- #


def page_action_checklist() -> None:
    st.title("📋 Conversion Action Checklist")
    md = load_markdown(
        str(
            ROOT
            / "04_xero_post_upload_checks/06_final_sign_off/action_checklist_template.md"
        )
    )
    if not md:
        st.warning("Action Checklist template not found.")
        return
    st.caption(
        "This is the consolidated client-facing summary delivered at "
        "sign-off. Fill the template before sending."
    )
    st.markdown(md)


# --------------------------------------------------------------------------- #
# Page: About                                                                 #
# --------------------------------------------------------------------------- #


def page_about() -> None:
    st.title("About this dashboard")
    st.markdown(
        """
        Read-only view of the MYOB → Xero migration toolkit. Data sources:

        - `INDEX.md` — per-stage tables and client header.
        - `04_xero_post_upload_checks/05_exception_log/exceptions.csv` — open variances.
        - `04_xero_post_upload_checks/03_balance_reconciliations/clearing_accounts_tracker.csv` — clearing/suspense roll-up.
        - `04_xero_post_upload_checks/01_account_by_account_checklists/trial_balance_diff.csv` — acceptance-gate output.
        - `04_xero_post_upload_checks/06_final_sign_off/action_checklist_template.md` — client deliverable.

        Caches refresh every 10 seconds; use ↻ Refresh in the sidebar to force.
        """
    )
    st.divider()
    st.subheader("Privacy reminder")
    st.warning(
        "If this dashboard is rendering real client data, run it locally only "
        "(`streamlit run dashboard.py`). Do not expose the port; do not "
        "deploy with payroll data to any public host."
    )


# --------------------------------------------------------------------------- #
# Router                                                                      #
# --------------------------------------------------------------------------- #


if page == "Overview":
    page_overview()
elif page == "Stage 01 — Exports":
    render_stage_view("01", "Exports from MYOB")
elif page == "Stage 02 — Cleansed":
    render_stage_view("02", "Cleansed for Xero")
elif page == "Stage 03 — Reports":
    render_stage_view("03", "Finalized reports")
elif page == "Stage 04 — Verification":
    render_stage_view("04", "Xero post-upload checks")
elif page == "Exceptions":
    page_exceptions()
elif page == "Action Checklist":
    page_action_checklist()
elif page == "About":
    page_about()
