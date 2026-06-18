"""Heuristic parser for tabular text pasted out of MYOB Business browser screens.

MYOB Business (the cloud-only product, not AccountRight) has no CSV export
for chart of accounts, customers, suppliers, or items. Users have to copy
the on-screen table and paste it. The clipboard usually contains tab-
separated cells with the screen's column order, but the formatting is
fragile: indented rows, blank lines between groups, currency symbols
inside numeric cells, multi-line cells, and an inconsistent header row.

`parse_pasted_table` tries a sequence of split strategies (tab → pipe →
multi-space) and returns the first one that gives consistent column
counts, plus the detected header.
"""

from __future__ import annotations

import re
from io import StringIO

import pandas as pd


_HEADER_HINTS = (
    "account",
    "name",
    "type",
    "code",
    "tax",
    "balance",
    "active",
    "contact",
    "abn",
    "email",
    "phone",
    "item",
    "description",
)

# Group headings MYOB Business inserts between rows when you copy from
# the Categories screen. Used by the single-column reshape to ignore
# them when computing the column stride.
_GROUP_HEADINGS = {
    "asset",
    "assets",
    "liability",
    "liabilities",
    "equity",
    "income",
    "revenue",
    "cost of sales",
    "expense",
    "expenses",
    "other income",
    "other expense",
    "current asset",
    "current liability",
    "non-current asset",
    "non-current liability",
}

# Patterns that look like an MYOB account number (with optional dash).
_ACCT_CODE_RE = re.compile(r"^\d[\d-]{1,7}$")


def _split_tab(line: str) -> list[str]:
    return [c.strip() for c in line.split("\t")]


def _split_pipe(line: str) -> list[str]:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells if len(cells) > 1 else []


def _split_multispace(line: str) -> list[str]:
    return [c.strip() for c in re.split(r" {2,}", line) if c.strip()]


_STRATEGIES = [
    ("tab", _split_tab),
    ("pipe", _split_pipe),
    ("multispace", _split_multispace),
]


def _looks_like_header(cells: list[str]) -> bool:
    blob = " ".join(cells).lower()
    return sum(1 for h in _HEADER_HINTS if h in blob) >= 2


def _strip_currency(value: str) -> str:
    """Turn '$1,234.56' / '($500.00)' into '1234.56' / '-500.00'."""
    v = value.strip()
    if not v:
        return v
    neg = v.startswith("(") and v.endswith(")")
    v = v.strip("()").replace("$", "").replace(",", "")
    if neg and v:
        v = "-" + v
    return v


def _looks_like_account_code(s: str) -> bool:
    return bool(_ACCT_CODE_RE.fullmatch(s.strip()))


def _is_group_heading(line: str) -> bool:
    s = line.strip().lower().rstrip(":")
    return s in _GROUP_HEADINGS


def _reshape_single_column(lines: list[str]) -> tuple[list[str], list[list[str]], int] | None:
    """Detect the column stride from a flat one-cell-per-line paste.

    MYOB Business's "copy from screen → paste into Excel" pours every source
    cell into Excel column A as a separate row. We detect this by finding
    repeating account-code-looking entries and using the modal gap between
    them as the column count.

    Returns (header, rows, stride) or None if no stride could be detected.
    """
    # Strip group headings before computing strides.
    filtered = [ln for ln in lines if not _is_group_heading(ln)]
    code_positions = [
        i for i, s in enumerate(filtered) if _looks_like_account_code(s)
    ]
    if len(code_positions) < 2:
        return None
    gaps = [
        code_positions[i + 1] - code_positions[i]
        for i in range(len(code_positions) - 1)
    ]
    stride = max(set(gaps), key=gaps.count)
    if not (2 <= stride <= 12):
        return None

    # Header is everything before the first code; if it doesn't match the
    # stride length, synthesise.
    header_candidates = filtered[: code_positions[0]]
    if len(header_candidates) == stride and _looks_like_header(header_candidates):
        header = header_candidates
        body_start = code_positions[0]
    else:
        header = [f"col_{i+1}" for i in range(stride)]
        body_start = code_positions[0]

    body = filtered[body_start:]
    rows = [body[i : i + stride] for i in range(0, len(body), stride)]
    rows = [r + [""] * (stride - len(r)) for r in rows if r]
    return header, rows, stride


def parse_pasted_table(text: str) -> tuple[pd.DataFrame, dict]:
    """Parse the pasted blob into a DataFrame.

    Returns (df, meta) where meta has:
      - strategy: which split strategy worked
      - header_row: index of the row used as header (or -1 if synthesised)
      - dropped: count of skipped blank/group-header lines
    """
    # Keep lines that have any non-whitespace content.
    raw_lines = [ln for ln in text.splitlines() if ln.strip()]
    if not raw_lines:
        return pd.DataFrame(), {"strategy": None, "header_row": -1, "dropped": 0}

    best: tuple[str, list[list[str]], int] | None = None
    for name, splitter in _STRATEGIES:
        rows = [splitter(ln) for ln in raw_lines]
        rows = [r for r in rows if r]  # drop empty splits (pipe path on plain text)
        if not rows:
            continue
        # Score by the modal column count: more rows agreeing = better.
        counts = [len(r) for r in rows]
        modal = max(set(counts), key=counts.count)
        if modal < 2:
            continue
        agreement = counts.count(modal)
        if best is None or agreement > best[2]:
            best = (name, rows, agreement)

    if best is None:
        # Last resort: assume Excel-style single-column paste (MYOB Business
        # Categories screen) and reshape using detected stride.
        reshape = _reshape_single_column(raw_lines)
        if reshape is None:
            return pd.DataFrame(), {"strategy": None, "header_row": -1, "dropped": 0}
        header, rows, stride = reshape
        df = pd.DataFrame(rows, columns=_dedup_headers(header))
        for col in df.columns:
            if "balance" in col.lower() or "amount" in col.lower():
                df[col] = df[col].map(_strip_currency)
        return df, {
            "strategy": "single_column_reshape",
            "header_row": 0 if header[0] != "col_1" else -1,
            "stride": stride,
            "dropped": 0,
        }

    strategy, rows, _ = best
    modal = max(set(len(r) for r in rows), key=lambda n: sum(1 for r in rows if len(r) == n))

    # Detect header.
    header_row = -1
    for i, r in enumerate(rows[:5]):
        if len(r) == modal and _looks_like_header(r):
            header_row = i
            break

    if header_row >= 0:
        header = rows[header_row]
        data = rows[header_row + 1 :]
    else:
        header = [f"col_{i+1}" for i in range(modal)]
        data = rows

    # Pad / truncate to modal width.
    data = [r + [""] * (modal - len(r)) if len(r) < modal else r[:modal] for r in data]

    # Drop pure-group-heading rows (single cell with text, rest empty).
    cleaned = []
    dropped = 0
    for r in data:
        nonblank = sum(1 for c in r if c)
        if nonblank <= 1 and len(r) > 1:
            dropped += 1
            continue
        cleaned.append(r)

    df = pd.DataFrame(cleaned, columns=_dedup_headers(header))

    # Best-effort tidy: strip currency in obviously-numeric columns.
    for col in df.columns:
        if "balance" in col.lower() or "amount" in col.lower():
            df[col] = df[col].map(_strip_currency)

    return df, {
        "strategy": strategy,
        "header_row": header_row,
        "dropped": dropped,
    }


def _dedup_headers(header: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out: list[str] = []
    for h in header:
        h = h or "col"
        if h in seen:
            seen[h] += 1
            out.append(f"{h}_{seen[h]}")
        else:
            seen[h] = 1
            out.append(h)
    return out


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")
