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

# Distinctive markers in an MYOB Business "copy from screen" paste.
_SELECT_ROW_RE = re.compile(r"^Select row \d+$", re.IGNORECASE)
_LEVEL_RE = re.compile(r"^Level\s+\d+$", re.IGNORECASE)


def _parse_myob_business(lines: list[str]) -> tuple[list[str], list[list[str]]] | None:
    """Special-case parser for the MYOB Business 'Select row N' paste.

    A paste copied from any MYOB Business list screen (Chart of accounts,
    Customers, …) and pasted into Excel produces:

        Bulk select        <- header column for the row checkboxes
        Code
        Name
        Status
        Type
        Tax code
        Linked
        Level
        Current balance ($)
        Select row 0       <- row delimiter, then 5-7 data cells follow
        1-0000
        Assets
        ...

    Optional columns (Status, Tax code, Linked) are *omitted entirely*
    when the cell would be empty, so row widths vary. We classify cells
    by content — Level matches "Level N", Linked is the literal
    "Linked", Balance is numeric — then fill Code / Name / Type / Tax
    code by position in what's left.
    """
    stripped = [str(ln).strip() for ln in lines]
    boundaries = [i for i, ln in enumerate(stripped) if _SELECT_ROW_RE.match(ln)]
    if len(boundaries) < 2:
        return None

    # Header: cells before the first "Select row 0".
    header_block = [c for c in stripped[: boundaries[0]] if c]
    # Drop the row-checkbox column and "Status" (always omitted from each row).
    header_block = [
        h for h in header_block if h.lower() not in {"bulk select", "status"}
    ]
    schema = header_block or [
        "Code",
        "Name",
        "Type",
        "Tax code",
        "Linked",
        "Level",
        "Current balance ($)",
    ]

    rows: list[list[str]] = []
    for i, start in enumerate(boundaries):
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(stripped)
        cells = [c for c in stripped[start + 1 : end] if c]
        if not cells:
            continue
        rows.append(_align_myob_row(cells, schema))

    return schema, rows


def _align_myob_row(cells: list[str], schema: list[str]) -> list[str]:
    """Place cells into schema slots by content classification.

    Anchors from the right: Balance is the last cell, Level matches
    "Level N", Linked is the literal "Linked". Anything between the
    Type slot and those anchors is Tax code.
    """
    n = len(cells)
    out = {c: "" for c in schema}
    balance_idx = n - 1 if n >= 1 else None
    level_idx = (
        n - 2 if n >= 2 and _LEVEL_RE.match(cells[n - 2]) else None
    )
    linked_idx = (
        level_idx - 1
        if level_idx is not None
        and level_idx >= 1
        and cells[level_idx - 1].lower() == "linked"
        else None
    )
    right_limit = (
        linked_idx
        if linked_idx is not None
        else (level_idx if level_idx is not None else balance_idx)
    )
    if right_limit is None:
        right_limit = n

    # Always treat the leftmost cell as Code, even if it doesn't match the
    # account-number regex. Excel routinely corrupts codes like "1-9000"
    # into dates ("1950-01-01") on paste; keeping them in the Code column
    # preserves row alignment so the user can spot and fix them in the
    # data editor, instead of shifting every downstream column.
    left = 0
    if left < right_limit:
        out["Code"] = cells[left]
        left += 1
    if left < right_limit:
        out["Name"] = cells[left]
        left += 1
    if left < right_limit:
        out["Type"] = cells[left]
        left += 1
    if left < right_limit:
        out["Tax code"] = cells[left]

    if linked_idx is not None:
        out["Linked"] = cells[linked_idx]
    if level_idx is not None:
        out["Level"] = cells[level_idx]
    if balance_idx is not None:
        out["Current balance ($)"] = cells[balance_idx]

    return [out.get(c, "") for c in schema]


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

    # Try the MYOB-Business-specific path first. It has unmistakable
    # "Select row N" delimiters, so if they're present this is unambiguous.
    myob = _parse_myob_business(raw_lines)
    if myob is not None:
        header, rows = myob
        df = pd.DataFrame(rows, columns=_dedup_headers(header))
        for col in df.columns:
            if "balance" in col.lower() or "amount" in col.lower():
                df[col] = df[col].map(_strip_currency)
        # Detect Excel date-corruption of account codes ("1-9000" → "1950-01-01")
        code_col = next((c for c in df.columns if c.lower() == "code"), None)
        date_like_codes = 0
        if code_col is not None:
            for v in df[code_col]:
                s = str(v).strip()
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}( 00:00:00)?", s):
                    date_like_codes += 1
        return df, {
            "strategy": "myob_business",
            "header_row": 0,
            "rows": len(rows),
            "dropped": 0,
            "date_corrupted_codes": date_like_codes,
        }

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
