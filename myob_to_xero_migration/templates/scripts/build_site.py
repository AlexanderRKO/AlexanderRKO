"""Static HTML status page generator for the MYOB → Xero migration toolkit.

Output is a single self-contained `index.html` (plus optionally the three
PDF deliverables copied into `pdfs/`). No external CSS/JS — runs anywhere
that serves static files, designed for GitHub Pages.

Data sources:
  * INDEX.md — artefact-status tracker (parsed for per-stage counts)
  * Header block of INDEX.md — client name, conversion date, MYOB product,
    Xero org target, lead accountant.

Privacy: only counts and labels are surfaced. Raw CSVs, balances, employee
data and the underlying artefacts are NOT copied into the build output.
Use `--include-pdfs` to additionally copy the three deliverable PDFs (these
are templates with placeholder data until `init` has been run with real
client values; verify before publishing publicly).

Usage:
    python build_site.py --root <toolkit-root> --out _site/
    python build_site.py --root <toolkit-root> --out _site/ --include-pdfs
"""

from __future__ import annotations

import argparse
import html
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

# Reuse the toolkit's own parsers so this stays in sync with `migration.py`.
SCRIPT_DIR = Path(__file__).resolve().parent
TOOLKIT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(TOOLKIT_ROOT))

from migration import parse_index, _field  # type: ignore[import-not-found]  # noqa: E402


def _field_prefix(text: str, prefix: str) -> str | None:
    """Match a markdown table row whose label *starts with* `prefix`.

    `_field` from migration.py requires an exact label match — but the
    real PLAN.md / INDEX.md use verbose labels like
    "MYOB product (AccountRight Live / Essentials / Business)".
    This relaxed match finds the value either way.
    """
    pat = rf"\|\s*{re.escape(prefix)}[^|]*\|\s*([^|]+?)\s*\|"
    m = re.search(pat, text)
    return m.group(1).strip() if m else None


STATUS_LABELS = {
    "done": "done",
    "wip": "in progress",
    "todo": "todo",
    "exception": "exception",
}
STATUS_COLOURS = {
    "done": "#22c55e",
    "wip": "#eab308",
    "todo": "#94a3b8",
    "exception": "#ef4444",
}

PHASES = [
    ("A", "Plan", "Engagement parameters, privacy gate, team sign-off."),
    ("B", "Extract", "Pull every export from MYOB into Stage 01."),
    ("C", "Cleanse", "Transform raw exports into Xero CSV templates (Stage 02)."),
    ("D", "Upload", "Load CSVs into Xero in the documented order (Stage 03)."),
    ("E", "Verify", "Trial-balance gate, post-upload checks, sign-off (Stage 04)."),
]


def _git_sha(repo_root: Path) -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return ""


def _days_to(target: str) -> tuple[int | None, str]:
    """Return (days, label) where days may be negative if past."""
    try:
        d = datetime.strptime(target, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None, ""
    delta = (d - date.today()).days
    if delta > 0:
        return delta, f"{delta} day{'s' if delta != 1 else ''} until conversion"
    if delta < 0:
        return delta, f"{-delta} day{'s' if delta != -1 else ''} since conversion"
    return 0, "Conversion day"


def _phase_for(stage_pcts: list[float]) -> str:
    """Pick the current phase letter from per-stage completion."""
    s01, s02, s03, s04 = (stage_pcts + [0, 0, 0, 0])[:4]
    if s04 > 0:
        return "E"
    if s03 > 0:
        return "D"
    if s02 > 0:
        return "C"
    if s01 > 0:
        return "B"
    return "A"


def render_html(ctx: dict) -> str:
    """Return the complete self-contained HTML page."""
    e = html.escape

    def chip(status: str, count: int) -> str:
        return (
            f'<span class="chip" style="background:{STATUS_COLOURS[status]}1a;'
            f'color:{STATUS_COLOURS[status]};border-color:{STATUS_COLOURS[status]}55">'
            f"{count} {STATUS_LABELS[status]}</span>"
        )

    stage_cards = []
    for s in ctx["stages"]:
        c = s["counts"]
        pct = s["pct"]
        bar_colour = (
            STATUS_COLOURS["done"]
            if pct >= 100
            else STATUS_COLOURS["wip"]
            if pct >= 50
            else STATUS_COLOURS["exception"]
            if pct > 0
            else STATUS_COLOURS["todo"]
        )
        chips = "".join(
            chip(k, c.get(k, 0))
            for k in ("done", "wip", "todo", "exception")
            if c.get(k, 0) > 0
        )
        stage_cards.append(
            f"""<article class="stage">
              <header><h3>{e(s["name"])}</h3>
                <span class="pct">{pct:.0f}%</span></header>
              <div class="bar"><div class="fill" style="width:{pct:.1f}%;background:{bar_colour}"></div></div>
              <div class="chips">{chips or '<span class="chip muted">no artefacts tracked</span>'}</div>
              <p class="sub">{s["done"]} of {s["total"]} artefacts landed</p>
            </article>"""
        )

    phase_pills = []
    current = ctx["current_phase"]
    for letter, name, desc in PHASES:
        cls = "phase active" if letter == current else "phase"
        phase_pills.append(
            f'<li class="{cls}" title="{e(desc)}">'
            f'<span class="letter">{letter}</span>'
            f"<span class=\"name\">{e(name)}</span></li>"
        )

    pdf_links = ""
    if ctx["pdfs"]:
        items = "".join(
            f'<li><a href="pdfs/{e(p)}" download>{e(p)}</a></li>'
            for p in ctx["pdfs"]
        )
        pdf_links = f'<ul class="pdfs">{items}</ul>'
    else:
        pdf_links = (
            '<p class="muted">No PDFs published with this build. To include them, '
            "rebuild with <code>python migration.py site --include-pdfs</code>.</p>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{e(ctx["client"])} — MYOB → Xero migration</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Live status page for the MYOB → Xero migration of {e(ctx["client"])}.">
<style>
:root {{
  --bg:#f8fafc; --panel:#fff; --text:#0f172a; --muted:#64748b;
  --line:#e2e8f0; --accent:#6366f1; --accent-dim:#eef2ff;
}}
@media (prefers-color-scheme:dark) {{
  :root {{
    --bg:#0b1220; --panel:#111827; --text:#f1f5f9; --muted:#94a3b8;
    --line:#1f2937; --accent:#818cf8; --accent-dim:#1e1b4b;
  }}
}}
*{{box-sizing:border-box}}
html,body{{margin:0;background:var(--bg);color:var(--text);
  font:15px/1.55 -apple-system,Segoe UI,Inter,Roboto,system-ui,sans-serif}}
a{{color:var(--accent);text-decoration:none}}
a:hover{{text-decoration:underline}}
.wrap{{max-width:980px;margin:0 auto;padding:32px 20px 64px}}
header.top{{display:flex;flex-wrap:wrap;gap:16px 24px;align-items:baseline;
  margin-bottom:8px}}
header.top h1{{font-size:24px;margin:0;font-weight:600;letter-spacing:-0.01em}}
header.top .meta{{color:var(--muted);font-size:14px}}
.subtitle{{color:var(--muted);margin:0 0 24px;font-size:14px}}
.cards{{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));
  margin:0 0 28px}}
.meta-card{{background:var(--panel);border:1px solid var(--line);border-radius:10px;
  padding:14px 16px}}
.meta-card .label{{color:var(--muted);font-size:12px;text-transform:uppercase;
  letter-spacing:0.05em;margin:0 0 4px}}
.meta-card .value{{font-size:16px;font-weight:600;margin:0}}
.meta-card .accent{{color:var(--accent)}}
h2{{font-size:13px;text-transform:uppercase;letter-spacing:0.08em;color:var(--muted);
  font-weight:600;margin:32px 0 12px}}
ol.phases{{list-style:none;padding:0;margin:0 0 28px;display:grid;
  grid-template-columns:repeat(5,1fr);gap:8px}}
ol.phases .phase{{background:var(--panel);border:1px solid var(--line);
  border-radius:10px;padding:12px 10px;text-align:center}}
ol.phases .phase.active{{background:var(--accent-dim);border-color:var(--accent)}}
ol.phases .letter{{display:block;font-size:18px;font-weight:700;color:var(--accent)}}
ol.phases .name{{display:block;font-size:13px;color:var(--muted);margin-top:2px}}
.stages{{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));
  margin:0 0 28px}}
article.stage{{background:var(--panel);border:1px solid var(--line);border-radius:10px;
  padding:16px}}
article.stage header{{display:flex;justify-content:space-between;align-items:baseline;
  margin:0 0 10px}}
article.stage h3{{font-size:14px;margin:0;font-weight:600}}
article.stage .pct{{font-size:13px;color:var(--muted);font-variant-numeric:tabular-nums}}
.bar{{height:6px;background:var(--line);border-radius:999px;overflow:hidden;
  margin:0 0 10px}}
.bar .fill{{height:100%;border-radius:999px;transition:width .4s}}
.chips{{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 8px}}
.chip{{font-size:12px;padding:3px 8px;border-radius:999px;border:1px solid;
  font-variant-numeric:tabular-nums}}
.chip.muted{{color:var(--muted);background:transparent;border-color:var(--line)}}
.sub{{margin:0;font-size:12px;color:var(--muted)}}
ul.pdfs{{list-style:none;padding:0;margin:0;display:grid;
  grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px}}
ul.pdfs li a{{display:block;background:var(--panel);border:1px solid var(--line);
  border-radius:8px;padding:12px 14px}}
ul.pdfs li a:hover{{border-color:var(--accent);text-decoration:none}}
.muted{{color:var(--muted)}}
footer{{margin-top:48px;padding-top:20px;border-top:1px solid var(--line);
  color:var(--muted);font-size:12px;line-height:1.6}}
footer code{{background:var(--accent-dim);color:var(--accent);padding:1px 6px;
  border-radius:4px;font-size:11px}}
.privacy{{background:var(--accent-dim);border:1px solid var(--accent);color:var(--text);
  border-radius:8px;padding:10px 14px;margin:0 0 24px;font-size:13px}}
.privacy strong{{color:var(--accent)}}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <h1>{e(ctx["client"])}</h1>
    <span class="meta">MYOB → Xero migration · live status</span>
  </header>
  <p class="subtitle">{e(ctx["days_label"]) or "Conversion date not yet set."}</p>

  {ctx["privacy_banner"]}

  <div class="cards">
    <div class="meta-card"><p class="label">Conversion date</p>
      <p class="value accent">{e(ctx["conversion"])}</p></div>
    <div class="meta-card"><p class="label">MYOB product</p>
      <p class="value">{e(ctx["myob_product"])}</p></div>
    <div class="meta-card"><p class="label">Xero org</p>
      <p class="value">{e(ctx["xero_org"])}</p></div>
    <div class="meta-card"><p class="label">Lead</p>
      <p class="value">{e(ctx["lead"])}</p></div>
  </div>

  <h2>Phase</h2>
  <ol class="phases">{"".join(phase_pills)}</ol>

  <h2>Stage progress</h2>
  <div class="stages">{"".join(stage_cards)}</div>

  <h2>Deliverables</h2>
  {pdf_links}

  <footer>
    Built {e(ctx["built_at"])}{f" from <code>{e(ctx['sha'])}</code>" if ctx["sha"] else ""}.
    Data source: <code>INDEX.md</code>. Status surfaces counts only — no raw
    client data, balances, or employee records are published by this page.
    <br>Generated by <code>python migration.py site</code>.
  </footer>
</div>
</body>
</html>
"""


def build(root: Path, out: Path, include_pdfs: bool) -> int:
    index_path = root / "INDEX.md"
    if not index_path.exists():
        print(f"ERROR: {index_path} not found", file=sys.stderr)
        return 1

    text = index_path.read_text(encoding="utf-8")
    stages_raw = parse_index(text)
    stages = [
        {
            "name": s.name,
            "counts": dict(s.counts),
            "total": s.total,
            "done": s.done,
            "pct": s.pct,
        }
        for s in stages_raw
    ]
    stage_pcts = [s["pct"] for s in stages]

    # Engagement metadata lives across INDEX.md AND PLAN.md (PLAN.md holds
    # MYOB product / Xero org target). Concatenate and search both.
    plan_path = root / "PLAN.md"
    combined = text + ("\n" + plan_path.read_text(encoding="utf-8") if plan_path.exists() else "")

    client = _field_prefix(combined, "Client / entity") or "_TBD_"
    conversion = _field_prefix(combined, "Conversion date") or "_TBD_"
    myob_product = _field_prefix(combined, "MYOB product") or "_TBD_"
    xero_org = _field_prefix(combined, "Xero org target") or "_TBD_"
    lead = _field_prefix(combined, "Lead accountant") or "_TBD_"

    _, days_label = _days_to(conversion)
    sha = _git_sha(root.parent if (root.parent / ".git").exists() else root)
    built_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    out.mkdir(parents=True, exist_ok=True)

    # PDFs (optional). Drop them under /pdfs/ if the source files exist at
    # the toolkit root; otherwise skip silently.
    pdfs_in_site: list[str] = []
    if include_pdfs:
        pdf_dir = out / "pdfs"
        pdf_dir.mkdir(exist_ok=True)
        for fname in (
            "migration_plan.pdf",
            "action_checklist.pdf",
            "post_conversion_checklist.pdf",
            "getting_started_visual.pdf",
        ):
            src = root / fname
            if src.exists():
                shutil.copy2(src, pdf_dir / fname)
                pdfs_in_site.append(fname)

    privacy_banner = ""
    placeholder_count = sum(
        1 for v in (client, conversion, myob_product, xero_org, lead) if v == "_TBD_"
    )
    if placeholder_count >= 3:
        privacy_banner = (
            '<div class="privacy"><strong>Template state.</strong> This site '
            "was built from an uninitialised toolkit (most fields show "
            "<code>_TBD_</code>). Run "
            "<code>python migration.py init</code> with the engagement parameters "
            "before publishing, or this page will be empty.</div>"
        )

    ctx = {
        "client": client,
        "conversion": conversion,
        "days_label": days_label,
        "myob_product": myob_product,
        "xero_org": xero_org,
        "lead": lead,
        "stages": stages,
        "current_phase": _phase_for(stage_pcts),
        "pdfs": pdfs_in_site,
        "sha": sha,
        "built_at": built_at,
        "privacy_banner": privacy_banner,
    }

    out_html = out / "index.html"
    out_html.write_text(render_html(ctx), encoding="utf-8")
    print(f"  wrote {out_html}", file=sys.stderr)
    if pdfs_in_site:
        print(f"  copied {len(pdfs_in_site)} PDF(s) into {out / 'pdfs'}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--root",
        type=Path,
        default=TOOLKIT_ROOT,
        help="toolkit root containing INDEX.md (default: %(default)s)",
    )
    p.add_argument(
        "--out",
        type=Path,
        required=True,
        help="output directory; will be created if missing",
    )
    p.add_argument(
        "--include-pdfs",
        action="store_true",
        help="also copy the deliverable PDFs into <out>/pdfs/",
    )
    args = p.parse_args(argv)
    return build(args.root.resolve(), args.out.resolve(), args.include_pdfs)


if __name__ == "__main__":
    raise SystemExit(main())
