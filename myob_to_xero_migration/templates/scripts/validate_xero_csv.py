"""Pre-flight validator for Xero import CSVs.

Checks that a cleansed CSV in `02_cleansed_for_xero/` matches the
corresponding Xero template header row exactly (column order included)
and that required (`*`) columns are not blank.

Usage:
    python validate_xero_csv.py <cleansed.csv> <template.csv>

Exit code 0 = pass, 1 = validation failed. A short report is printed to
stdout; route it into `02_cleansed_for_xero/_validation_logs/` when run
in a pipeline.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path


def read_header(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        return next(reader, [])


def required_columns(header: list[str]) -> list[str]:
    return [col for col in header if col.startswith("*")]


def validate(cleansed: Path, template: Path) -> int:
    template_header = read_header(template)
    cleansed_header = read_header(cleansed)

    errors: list[str] = []

    if cleansed_header != template_header:
        errors.append("Header row does not match template exactly.")
        errors.append(f"  expected: {template_header}")
        errors.append(f"  found   : {cleansed_header}")

    required = required_columns(template_header)
    required_idx = [template_header.index(col) for col in required]

    row_count = 0
    blank_required: list[tuple[int, str]] = []

    with cleansed.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        next(reader, None)
        for row_no, row in enumerate(reader, start=2):
            row_count += 1
            for idx in required_idx:
                if idx >= len(row) or not row[idx].strip():
                    blank_required.append((row_no, template_header[idx]))

    print(f"file       : {cleansed}")
    print(f"template   : {template}")
    print(f"data rows  : {row_count}")
    print(f"required   : {required}")

    if blank_required:
        errors.append(f"{len(blank_required)} blank required cells")
        for row_no, col in blank_required[:20]:
            errors.append(f"  row {row_no}: blank '{col}'")
        if len(blank_required) > 20:
            errors.append(f"  ... and {len(blank_required) - 20} more")

    # Privacy guard: this validator must never echo identified payroll
    # values. Only row counts, column names, and pass/fail are logged.
    # See PRIVACY.md.

    if errors:
        print("RESULT     : FAIL")
        for e in errors:
            print(e)
        return 1

    print("RESULT     : PASS")
    return 0


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    return validate(Path(sys.argv[1]), Path(sys.argv[2]))


if __name__ == "__main__":
    raise SystemExit(main())
