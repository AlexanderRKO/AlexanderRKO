#!/usr/bin/env python3
"""Build a branded Word (.docx) version of tax-questionnaire-export.md.

Parses the export markdown and produces a clean, LMS-branded document suitable
for circulating internally (e.g. in Cowork). Run:  python3 build-docx.py
"""
import re
from pathlib import Path

from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tax-questionnaire-export.md"
OUT = ROOT / "tax-questionnaire-export.docx"

NAVY = RGBColor(0x00, 0x25, 0x55)
ORANGE = RGBColor(0xED, 0x8B, 0x00)
GREY = RGBColor(0x5B, 0x65, 0x73)
INK = RGBColor(0x1F, 0x2A, 0x38)

doc = Document()
base = doc.styles["Normal"]
base.font.name = "Calibri"
base.font.size = Pt(10.5)
base.font.color.rgb = INK
for m in doc.sections:
    m.left_margin = m.right_margin = Inches(0.9)
    m.top_margin = m.bottom_margin = Inches(0.8)


def run(p, text, *, size=10.5, bold=False, italic=False, color=INK):
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.bold = bold
    r.italic = italic
    r.font.color.rgb = color
    return r


def para(space_before=0, space_after=4, align=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    if align is not None:
        p.alignment = align
    return p


def bullet(text, key=None, numbered=False):
    p = doc.add_paragraph(style="List Number" if numbered else "List Bullet")
    p.paragraph_format.space_after = Pt(2)
    if key:
        run(p, key + ": ", bold=True, color=NAVY, size=10.5)
        run(p, text, size=10.5)
    else:
        run(p, text, size=10.5)
    return p


lines = SRC.read_text(encoding="utf-8").splitlines()
i = 0
in_options = False  # whether following indented numbers are option items

while i < len(lines):
    line = lines[i].rstrip()
    stripped = line.strip()

    if not stripped:
        in_options = False
        i += 1
        continue

    # Title
    if line.startswith("# "):
        p = para(space_after=2)
        run(p, line[2:].strip(), size=20, bold=True, color=NAVY)
        i += 1
        continue

    # Section heading
    if line.startswith("## Section:"):
        name = line.split(":", 1)[1].strip()
        p = para(space_before=14, space_after=4)
        run(p, "Section: ", size=14, bold=True, color=ORANGE)
        run(p, name, size=14, bold=True, color=NAVY)
        i += 1
        continue

    # Horizontal rule -> subtle spacer
    if stripped == "---":
        i += 1
        continue

    # Question line:  **Q1. text**  *(required)*
    mq = re.match(r"^\*\*(Q\d+\..*?)\*\*\s*(?:\*\((required|optional)\)\*)?\s*$", line)
    if mq:
        qtext, status = mq.group(1), mq.group(2)
        p = para(space_before=9, space_after=2)
        run(p, qtext, size=11.5, bold=True, color=INK)
        if status:
            run(p, "   " + status, size=9, bold=True,
                color=ORANGE if status == "required" else GREY)
        i += 1
        continue

    # Attribute bullet:  - Key: value   OR   - Options:
    if line.startswith("- "):
        body = line[2:].strip()
        if ": " in body:
            key, val = body.split(": ", 1)
            bullet(val, key=key)
        elif body.endswith(":"):
            bullet("", key=body[:-1])
            in_options = body[:-1].lower().startswith("options")
        else:
            bullet(body)
        i += 1
        continue

    # Indented numbered list (option items under "Options:")
    mnum = re.match(r"^\s+\d+\.\s+(.*)$", line)
    if mnum:
        bullet(mnum.group(1), numbered=True)
        i += 1
        continue

    # Summary paragraph (bold lead-in)
    if stripped.startswith("**Summary.**"):
        rest = stripped[len("**Summary.**"):].strip()
        p = para(space_before=6, space_after=6)
        run(p, "Summary. ", bold=True, color=NAVY)
        run(p, rest)
        i += 1
        continue

    # Italic caption / subtitle / note:  *...*
    if stripped.startswith("*") and stripped.endswith("*") and not stripped.startswith("**"):
        p = para(space_after=4)
        run(p, stripped.strip("*").strip(), size=9, italic=True, color=GREY)
        i += 1
        continue

    # Fallback: plain paragraph
    p = para()
    run(p, stripped)
    i += 1

doc.save(OUT)
print(f"Wrote {OUT}  ({OUT.stat().st_size // 1024} KB)")
