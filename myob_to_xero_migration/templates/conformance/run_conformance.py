#!/usr/bin/env python3
"""Run the MYOB -> Xero conversion conformance suite.

Every case in cases/ pairs a synthetic MYOB report with an expected.json
describing what any correct implementation must produce. The suite is
deliberately implementation-agnostic: it drives a converter through a
command line, reads back the JSON summary, and compares.

That means a second implementation (the web app, say) can be checked by
the same fixtures — point --adapter at a command that accepts the same
flags and writes the same JSON summary shape.

    python run_conformance.py                    # check the Python converter
    python run_conformance.py --adapter "node dist/convert.js"
    python run_conformance.py --case 03_mixed_tax --verbose

Exit code is 0 only if every case passes.

Why the fixtures are synthetic
------------------------------
Real debtor data is client data. It never goes in a repository. These
files reproduce the structural quirks that matter — quoted names holding
commas, the differing Total Due column index between report layouts,
credit notes, end-of-month terms, mixed tax codes, an out-of-balance
file — without a single real name or amount.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = HERE / "cases"
DEFAULT_ADAPTER = (
    f"{shlex.quote(sys.executable)} "
    f"{shlex.quote(str(HERE.parent / 'scripts' / 'convert_myob_open_items.py'))}"
)

GREEN, RED, YELLOW, DIM, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"
)


def approx(a, b, tol=0.005) -> bool:
    if a is None or b is None:
        return a == b
    try:
        return abs(float(a) - float(b)) < tol
    except (TypeError, ValueError):
        return a == b


def check_scalar(path: str, want, got, failures: list[str]) -> None:
    if isinstance(want, (int, float)) and not isinstance(want, bool):
        if not approx(want, got):
            failures.append(f"{path}: expected {want}, got {got}")
    elif want != got:
        failures.append(f"{path}: expected {want!r}, got {got!r}")


def check_case(case_dir: Path, adapter: str, verbose: bool) -> tuple[bool, list[str]]:
    spec = json.loads((case_dir / "expected.json").read_text(encoding="utf-8"))
    args_spec = spec.get("args", {})
    expect = spec.get("expect", {})
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        summary_path = tmp_path / "summary.json"
        out_dir = tmp_path / "out"

        cmd = (
            f'{adapter} --report {shlex.quote(str(case_dir / "report.txt"))} '
            f'--side {args_spec.get("side", "AR")} '
            f'--out {shlex.quote(str(out_dir))} '
            f'--json-summary {shlex.quote(str(summary_path))}'
        )
        for flag, key in (("--terms-report", "terms_report"),
                          ("--tax-report", "tax_report")):
            if key in args_spec:
                cmd += f" {flag} {shlex.quote(str(case_dir / args_spec[key]))}"
        if "tax_type" in args_spec:
            cmd += f' --tax-type {shlex.quote(args_spec["tax_type"])}'
        if "default_terms" in args_spec:
            cmd += f' --default-terms {args_spec["default_terms"]}'
        if args_spec.get("force"):
            cmd += " --force"

        proc = subprocess.run(shlex.split(cmd), capture_output=True, text=True)
        if verbose:
            print(f"{DIM}$ {cmd}{RESET}")
            print(f"{DIM}{proc.stdout}{RESET}")

        if "exit_code" in expect:
            check_scalar("exit_code", expect["exit_code"], proc.returncode, failures)

        if "files_written" in expect:
            written = out_dir.exists() and any(out_dir.iterdir())
            check_scalar("files_written", expect["files_written"], written, failures)

        if not summary_path.exists():
            failures.append("no JSON summary produced — cannot check assertions")
            return not failures, failures

        summary = json.loads(summary_path.read_text(encoding="utf-8"))

        for section in ("gate", "totals"):
            for k, want in expect.get(section, {}).items():
                check_scalar(f"{section}.{k}", want, summary.get(section, {}).get(k),
                             failures)

        for k, want in expect.get("tax", {}).items():
            got = summary.get("tax", {}).get(k)
            if isinstance(want, list):
                if sorted(want) != sorted(got or []):
                    failures.append(f"tax.{k}: expected {want}, got {got}")
            else:
                check_scalar(f"tax.{k}", want, got, failures)

        by_id = {ln["id"]: ln for ln in summary.get("lines", [])}
        for want_line in expect.get("lines", []):
            lid = want_line["id"]
            got_line = by_id.get(lid)
            if got_line is None:
                failures.append(f"lines: {lid} missing from output")
                continue
            for k, want in want_line.items():
                if k == "id":
                    continue
                check_scalar(f"lines[{lid}].{k}", want, got_line.get(k), failures)

    return not failures, failures


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--adapter", default=DEFAULT_ADAPTER,
                   help="command implementing the conversion CLI contract")
    p.add_argument("--case", default=None, help="run a single case by directory name")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args(argv)

    dirs = sorted(d for d in CASES.iterdir()
                  if d.is_dir() and (d / "expected.json").exists())
    if args.case:
        dirs = [d for d in dirs if d.name == args.case]
        if not dirs:
            print(f"no such case: {args.case}", file=sys.stderr)
            return 1

    print(f"Conformance suite — {len(dirs)} case(s)")
    print(f"{DIM}adapter: {args.adapter}{RESET}\n")

    passed = 0
    for d in dirs:
        ok, failures = check_case(d, args.adapter, args.verbose)
        spec = json.loads((d / "expected.json").read_text(encoding="utf-8"))
        if ok:
            passed += 1
            print(f"  {GREEN}PASS{RESET}  {d.name}")
        else:
            print(f"  {RED}FAIL{RESET}  {d.name}")
            print(f"        {DIM}{spec.get('description', '')}{RESET}")
            for f in failures:
                print(f"        {RED}- {f}{RESET}")

    print()
    total = len(dirs)
    if passed == total:
        print(f"{GREEN}All {total} case(s) passed.{RESET}")
        return 0
    print(f"{RED}{total - passed} of {total} case(s) failed.{RESET}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
