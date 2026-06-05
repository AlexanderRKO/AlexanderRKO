"""Render a downloadable visual Getting-Started guide as a multi-page PDF.

Hand-built with reportlab so it doesn't depend on pandoc / mermaid /
weasyprint. The text mirrors GETTING_STARTED.md but the layout is
visual: cover page with a drawn pipeline diagram, colour-coded section
headers, callout boxes, syntax-styled code blocks, a four-quadrant
status-views grid, a troubleshooting table, and a cheat-sheet last page.

Usage:
    python build_getting_started_pdf.py [--output guide.pdf]
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# --------------------------------------------------------------------------- #
# Palette                                                                     #
# --------------------------------------------------------------------------- #

NAVY = colors.HexColor("#0b5394")
DEEP = colors.HexColor("#073763")
ORANGE = colors.HexColor("#e69138")
GREEN = colors.HexColor("#38761d")
AMBER = colors.HexColor("#bf9000")
LIGHT = colors.HexColor("#eef3fb")
SAND = colors.HexColor("#fff2cc")
CODE_BG = colors.HexColor("#f4f4f4")
INK = colors.HexColor("#222222")
GREY = colors.HexColor("#666666")


# --------------------------------------------------------------------------- #
# Styles                                                                      #
# --------------------------------------------------------------------------- #


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "cover_title",
            parent=base["Title"],
            fontSize=42,
            leading=48,
            alignment=TA_CENTER,
            textColor=NAVY,
            spaceAfter=8,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub",
            parent=base["Title"],
            fontSize=16,
            alignment=TA_CENTER,
            textColor=DEEP,
            spaceAfter=20,
        ),
        "cover_meta": ParagraphStyle(
            "cover_meta",
            parent=base["Normal"],
            fontSize=9,
            alignment=TA_CENTER,
            textColor=GREY,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontSize=20,
            textColor=NAVY,
            spaceBefore=4,
            spaceAfter=10,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontSize=13,
            textColor=DEEP,
            spaceBefore=10,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontSize=10,
            leading=14,
            textColor=INK,
            spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "small",
            parent=base["BodyText"],
            fontSize=8,
            leading=11,
            textColor=GREY,
        ),
        "code": ParagraphStyle(
            "code",
            parent=base["BodyText"],
            fontName="Courier",
            fontSize=9,
            leading=12,
            textColor=INK,
            backColor=CODE_BG,
            borderColor=colors.HexColor("#dddddd"),
            borderWidth=0.4,
            borderPadding=6,
            leftIndent=0,
            spaceAfter=8,
        ),
        "callout_warn": ParagraphStyle(
            "callout_warn",
            parent=base["BodyText"],
            fontSize=10,
            leading=14,
            textColor=DEEP,
            backColor=SAND,
            borderColor=AMBER,
            borderWidth=0.8,
            borderPadding=8,
            spaceAfter=10,
        ),
        "callout_info": ParagraphStyle(
            "callout_info",
            parent=base["BodyText"],
            fontSize=10,
            leading=14,
            textColor=DEEP,
            backColor=LIGHT,
            borderColor=NAVY,
            borderWidth=0.6,
            borderPadding=8,
            spaceAfter=10,
        ),
    }


# --------------------------------------------------------------------------- #
# Custom Flowable: pipeline diagram                                           #
# --------------------------------------------------------------------------- #


class PipelineDiagram(Flowable):
    """Four-stage pipeline drawn directly on the canvas."""

    def __init__(self, width: float, height: float = 70 * mm):
        super().__init__()
        self.width = width
        self.height = height

    def wrap(self, _aw, _ah):
        return self.width, self.height

    def draw(self):
        c = self.canv
        box_w = (self.width - 30) / 4
        box_h = 38 * mm
        gap = 10
        y_box = (self.height - box_h) / 2

        stages = [
            ("01", "Exports from MYOB", "raw, immutable", NAVY),
            ("02", "Cleansed for Xero", "template-compliant CSV", colors.HexColor("#1c6dbd")),
            ("03", "Finalized reports", "locked source of truth", colors.HexColor("#3a8bd6")),
            ("04", "Post-upload checks", "inside Xero", GREEN),
        ]

        for i, (num, title, sub, fill) in enumerate(stages):
            x = i * (box_w + gap)
            c.setFillColor(fill)
            c.setStrokeColor(DEEP)
            c.roundRect(x, y_box, box_w, box_h, 4, fill=1, stroke=1)

            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 22)
            c.drawCentredString(x + box_w / 2, y_box + box_h - 16 * mm, num)
            c.setFont("Helvetica-Bold", 10)
            c.drawCentredString(x + box_w / 2, y_box + box_h - 22 * mm, title)
            c.setFont("Helvetica-Oblique", 8)
            c.drawCentredString(x + box_w / 2, y_box + box_h - 27 * mm, sub)

            # arrow to next stage
            if i < len(stages) - 1:
                c.setStrokeColor(GREY)
                c.setFillColor(GREY)
                arrow_x = x + box_w + 1
                arrow_y = y_box + box_h / 2
                c.setLineWidth(1.2)
                c.line(arrow_x, arrow_y, arrow_x + gap - 4, arrow_y)
                c.setLineWidth(1)
                p = c.beginPath()
                p.moveTo(arrow_x + gap - 4, arrow_y)
                p.lineTo(arrow_x + gap - 8, arrow_y + 3)
                p.lineTo(arrow_x + gap - 8, arrow_y - 3)
                p.close()
                c.drawPath(p, fill=1, stroke=0)


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def code_block(text: str, style: ParagraphStyle) -> Paragraph:
    """Render multi-line shell snippet as a single Paragraph with <br/>s."""
    escaped = (
        text.strip()
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
        .replace("  ", "&nbsp;&nbsp;")
    )
    return Paragraph(escaped, style)


def bullet_table(items: list[str], style: ParagraphStyle) -> Table:
    rows = [[Paragraph("•", style), Paragraph(it, style)] for it in items]
    t = Table(rows, colWidths=[6 * mm, None])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    return t


def section_header(title: str, sub: str, style_h1: ParagraphStyle, style_sub: ParagraphStyle):
    return [
        Paragraph(title, style_h1),
        Paragraph(sub, style_sub),
        Spacer(1, 6),
    ]


# --------------------------------------------------------------------------- #
# Page numbers / footer                                                       #
# --------------------------------------------------------------------------- #


def _footer(canvas: Canvas, doc: SimpleDocTemplate) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GREY)
    canvas.drawString(
        18 * mm,
        12 * mm,
        "MYOB → Xero migration toolkit — Getting Started",
    )
    canvas.drawRightString(
        A4[0] - 18 * mm,
        12 * mm,
        f"page {doc.page}",
    )
    canvas.restoreState()


# --------------------------------------------------------------------------- #
# Page builders                                                               #
# --------------------------------------------------------------------------- #


def page_cover(s: dict, story: list) -> None:
    story.append(Spacer(1, 50 * mm))
    story.append(Paragraph("Getting Started", s["cover_title"]))
    story.append(Paragraph("MYOB Online → Xero Migration Toolkit", s["cover_sub"]))
    story.append(Spacer(1, 8 * mm))
    story.append(PipelineDiagram(width=A4[0] - 36 * mm))
    story.append(Spacer(1, 14 * mm))
    story.append(
        Paragraph(
            "A structured, repeatable framework for converting a client's MYOB Online "
            "company file into a verified Xero organisation.",
            s["cover_meta"],
        )
    )
    story.append(Spacer(1, 30 * mm))
    story.append(
        Paragraph(
            f"Generated {datetime.now():%Y-%m-%d %H:%M}  ·  "
            "alongside GETTING_STARTED.md, PLAN.md, PRIVACY.md",
            s["cover_meta"],
        )
    )
    story.append(PageBreak())


def page_before_you_start(s: dict, story: list) -> None:
    story += section_header(
        "1. Before you start",
        "Five minutes of prerequisites — do these before touching MYOB.",
        s["h1"],
        s["small"],
    )

    story.append(Paragraph("Accounts &amp; access", s["h2"]))
    story.append(
        bullet_table(
            [
                "MYOB Online access to the client's company file (Administrator or accountant role).",
                "Xero subscription created — or the existing Xero org confirmed as the target.",
                "Client's written authorisation for the migration on file.",
                "Firm-managed encrypted storage ready (SharePoint / OneDrive equivalent).",
                "MFA enabled on MYOB, Xero, email, and storage for every team member.",
            ],
            s["body"],
        )
    )
    story.append(Spacer(1, 8))

    story.append(Paragraph("Local environment", s["h2"]))
    story.append(
        bullet_table(
            ["Python 3.10 or newer.", "Git.", "Optional: a virtual environment."],
            s["body"],
        )
    )
    story.append(
        code_block(
            "python -m venv .venv\n"
            "source .venv/bin/activate          # Windows: .venv\\Scripts\\activate\n"
            "pip install -r requirements.txt    # for the dashboard + PDF",
            s["code"],
        )
    )
    story.append(
        Paragraph(
            "<b>The core CLI works with zero dependencies.</b> requirements.txt "
            "covers only the optional visual layer (Streamlit dashboard, PDF reports).",
            s["callout_info"],
        )
    )
    story.append(PageBreak())


def page_first_time_setup(s: dict, story: list) -> None:
    story += section_header(
        "2. First-time setup",
        "Run init to fill engagement parameters, then read three files.",
        s["h1"],
        s["small"],
    )

    story.append(Paragraph("Step 1 — Fill the engagement parameters", s["h2"]))
    story.append(
        code_block(
            "cd myob_to_xero_migration\n\n"
            "python migration.py init \\\n"
            '    --client "Acme Pty Ltd" \\\n'
            '    --abn "12 345 678 901" \\\n'
            "    --conversion-date 2026-07-01 \\\n"
            '    --myob-product "AccountRight Live" \\\n'
            "    --xero-org-target new \\\n"
            '    --gst "Y, quarterly" \\\n'
            '    --payroll "Y, STP Phase 2" \\\n'
            '    --inventory "Y" \\\n'
            '    --lead "J. Smith"',
            s["code"],
        )
    )

    story.append(Paragraph("Step 2 — Confirm it took", s["h2"]))
    story.append(code_block("python migration.py status", s["code"]))

    story.append(Paragraph("Step 3 — Read these three files, in order", s["h2"]))
    story.append(
        bullet_table(
            [
                "<b>PLAN.md</b> — five phases, export map, upload order, known Xero limitations.",
                "<b>PRIVACY.md</b> — Privacy Act &amp; TFN Rule controls. Complete §8 pre-pull sign-off before payroll exports.",
                "<b>INDEX.md</b> — your live status tracker; update as artefacts move between stages.",
            ],
            s["body"],
        )
    )
    story.append(
        Paragraph(
            "⚠ <b>Privacy gate.</b> Do not pull employee or payroll data until "
            "every item in PRIVACY.md §8 is ticked. A misdirected payroll export "
            "is a notifiable data breach.",
            s["callout_warn"],
        )
    )
    story.append(PageBreak())


def page_phases(s: dict, story: list) -> None:
    story += section_header(
        "3. The five phases",
        "Mapped to the four numbered folders. Top to bottom; do not skip.",
        s["h1"],
        s["small"],
    )

    phases = [
        ("A", "Discovery &amp; scoping", "—",
         "Confirm scope, conversion date, GST cycle, payroll status, historical-year needs. Lock the migration team in INDEX.md."),
        ("B", "Extract", "01_exports_from_myob/",
         "Complete the MYOB file-readiness checklist first. Then pull every export per PLAN §2. Tick rows in INDEX.md as files land."),
        ("C", "Transform &amp; cleanse", "02_cleansed_for_xero/",
         "Re-map accounts and tax codes. Validate every CSV against the Xero template — validator must exit 0 before a file is promoted."),
        ("D", "Reporting &amp; sign-off", "03_finalized_reports/",
         "Lock BS / P&amp;L / TB / Aged AR / Aged AP / BAS / Payroll Activity as PDFs. Client signs them off. Do not start Phase E without sign-off."),
        ("E", "Load &amp; verify", "04_xero_post_upload_checks/",
         "Upload to Xero in the order in PLAN §3. Run the acceptance gate after each upload. Resolve clearing accounts. Deliver the Action Checklist."),
    ]

    rows = [["Phase", "Name", "Folder", "What happens"]]
    for letter, name, folder, desc in phases:
        rows.append(
            [
                Paragraph(f"<b>{letter}</b>", s["body"]),
                Paragraph(name, s["body"]),
                Paragraph(f"<font face='Courier' size='8'>{folder}</font>", s["body"]),
                Paragraph(desc, s["body"]),
            ]
        )
    t = Table(rows, colWidths=[14 * mm, 38 * mm, 42 * mm, None])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                ("BOX", (0, 0), (-1, -1), 0.4, GREY),
                ("INNERGRID", (0, 0), (-1, -1), 0.2, colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            "Three <b>quality gates</b> in this pipeline: the pre-export MYOB-readiness "
            "checklist (before Phase B), the preflight CSV validator (end of Phase C), "
            "and the trial-balance acceptance gate (after Phase E upload).",
            s["callout_info"],
        )
    )
    story.append(PageBreak())


def page_status_views(s: dict, story: list) -> None:
    story += section_header(
        "4. Four ways to see status",
        "Same data, picked by audience and friction.",
        s["h1"],
        s["small"],
    )

    quadrants = [
        ("Terminal", "for the day-to-day operator",
         "python migration.py status",
         "Coloured per-stage progress bars, open exceptions, clearing roll-up, acceptance-gate verdict."),
        ("Browser", "for the partner or accountant",
         "streamlit run dashboard.py",
         "Seven-page Streamlit app: Overview · Stages 01–04 · Exceptions · Action Checklist · About."),
        ("Printable PDF", "for the client",
         "python migration.py report -o status.pdf",
         "One-page A4 with client header, stage progress, and the roll-up. Suitable for email."),
        ("CI artefact", "for reviewers on GitHub",
         "GitHub Actions: Migration status",
         "Runs on every push to myob_to_xero_migration/**. Uploads status.txt + PDF as a 30-day artefact."),
    ]

    rows = []
    for label, who, cmd, desc in quadrants:
        cell_block = [
            Paragraph(f"<b>{label}</b>", s["body"]),
            Paragraph(f"<i>{who}</i>", s["small"]),
            Spacer(1, 4),
            Paragraph(f"<font face='Courier' size='8'>{cmd}</font>", s["body"]),
            Spacer(1, 4),
            Paragraph(desc, s["small"]),
        ]
        rows.append(cell_block)

    grid = Table(
        [[rows[0], rows[1]], [rows[2], rows[3]]],
        colWidths=[(A4[0] - 36 * mm) / 2 - 4, (A4[0] - 36 * mm) / 2 - 4],
        rowHeights=[44 * mm, 44 * mm],
    )
    grid.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 0.4, GREY),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, GREY),
                ("BACKGROUND", (0, 0), (0, 0), LIGHT),
                ("BACKGROUND", (1, 1), (1, 1), LIGHT),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(grid)
    story.append(PageBreak())


def page_troubleshooting(s: dict, story: list) -> None:
    story += section_header(
        "5. Troubleshooting",
        "The eight gotchas you're most likely to hit.",
        s["h1"],
        s["small"],
    )

    items = [
        ("validate fails on header mismatch",
         "CSV saved with semicolons or BOM",
         "Re-save as UTF-8, comma-delimited."),
        ("Xero rejects the CoA upload",
         "Account Type value not in Xero's list",
         "Check templates/checklists/account_type_mapping.md."),
        ("Xero rejects an invoice import",
         "Contact name absent from Xero",
         "Upload contacts first; check exact spelling."),
        ("check fails by the GST amount on one account",
         "Conversion-date GST timing difference",
         "Post a clearing journal; record in clearing_accounts_tracker.csv."),
        ("Payroll opening off for one casual employee",
         "Casual leave balances are not migrated by Xero",
         "Re-enter manually in Xero; note in the Action Checklist."),
        ("Dashboard shows _TBD_ everywhere",
         "init not yet run for this client",
         "python migration.py init --client … --conversion-date …"),
        ("GitHub Actions artefact missing",
         "Push didn't touch myob_to_xero_migration/**",
         "Edit a file under that path, or run via workflow_dispatch."),
        ("status shows 0/6 clearing accounts but you've cleared them",
         "status column in clearing_accounts_tracker.csv not set",
         "Set to '🟢' or 'done' in the tracker CSV."),
    ]

    rows = [["Symptom", "Likely cause", "Fix"]]
    for sym, cause, fix in items:
        rows.append(
            [
                Paragraph(sym, s["body"]),
                Paragraph(cause, s["body"]),
                Paragraph(fix, s["body"]),
            ]
        )
    t = Table(rows, colWidths=[60 * mm, 55 * mm, None])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                ("BOX", (0, 0), (-1, -1), 0.4, GREY),
                ("INNERGRID", (0, 0), (-1, -1), 0.2, colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(t)
    story.append(PageBreak())


def page_cheat_sheet(s: dict, story: list) -> None:
    story += section_header(
        "6. Cheat sheet",
        "Every command in one place — pin this page.",
        s["h1"],
        s["small"],
    )

    commands = [
        ("Set up a new engagement",
         'python migration.py init --client "<name>" --conversion-date <YYYY-MM-DD> \\\n'
         '    --xero-org-target new --lead "<your name>"'),
        ("See progress in the terminal", "python migration.py status"),
        ("Validate a cleansed CSV",
         "python migration.py validate <cleansed.csv> templates/xero_csv_templates/<template>.csv"),
        ("Run the trial-balance acceptance gate after upload",
         "python migration.py check --myob <myob_tb.csv> --xero <xero_tb.csv>"),
        ("Generate a one-page PDF status report",
         "python migration.py report -o status_report.pdf"),
        ("Open the browser dashboard",
         "streamlit run dashboard.py     # http://localhost:8501"),
        ("Rebuild this visual guide",
         "python migration.py guide -o getting_started_visual.pdf"),
    ]
    for label, cmd in commands:
        story.append(Paragraph(f"<b>{label}</b>", s["body"]))
        story.append(code_block(cmd, s["code"]))

    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            "<b>One-line rule:</b> nothing leaves a stage until its row in "
            "INDEX.md is ticked and the matching quality gate (readiness "
            "checklist, validator, or acceptance gate) has passed.",
            s["callout_info"],
        )
    )


# --------------------------------------------------------------------------- #
# Entry point                                                                 #
# --------------------------------------------------------------------------- #


def build(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=22 * mm,
        title="Getting Started — MYOB → Xero Migration Toolkit",
        author="MYOB → Xero migration toolkit",
    )

    s = _styles()
    story: list = []
    page_cover(s, story)
    page_before_you_start(s, story)
    page_first_time_setup(s, story)
    page_phases(s, story)
    page_status_views(s, story)
    page_troubleshooting(s, story)
    page_cheat_sheet(s, story)

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    default_out = (
        Path(__file__).resolve().parents[2] / "getting_started_visual.pdf"
    )
    p.add_argument("--output", "-o", type=Path, default=default_out)
    args = p.parse_args(argv)
    try:
        build(args.output)
    except ImportError as exc:
        print(f"ERROR: {exc} — install reportlab via requirements.txt", file=sys.stderr)
        return 2
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
