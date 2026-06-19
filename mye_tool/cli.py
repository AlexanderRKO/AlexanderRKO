"""Command line interface for mye_tool.

Usage examples::

    python -m mye_tool info ledger.mye
    python -m mye_tool accounts ledger.mye
    python -m mye_tool journal ledger.mye --account 477 --search payroll
    python -m mye_tool check ledger.mye
    python -m mye_tool export ledger.mye -o out/ --format all
    python -m mye_tool unpack ledger.mye -o work/
    python -m mye_tool pack work/ -o edited.mye
"""

from __future__ import annotations

import argparse
import os
import sys

from . import __version__, core
from . import exporters


def _table(rows, headers):
    rows = [[str(c) for c in row] for row in rows]
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    lines = [fmt.format(*headers), fmt.format(*["-" * w for w in widths])]
    lines += [fmt.format(*row) for row in rows]
    return "\n".join(lines)


def cmd_info(args) -> int:
    mye = core.load(args.file)
    lines = [
        f"File:           {args.file}",
        f"Company:        {mye.company_name}",
        f"Address:        {mye.address}",
        f"Period:         {mye.period_start} to {mye.period_end}",
        f"Accounts:       {len(mye.accounts)}",
        f"Journal:        {len(mye.entries)} entries, "
        f"{sum(len(e.lines) for e in mye.entries)} lines",
    ]
    info = mye.extract_info()
    for key in ("DataFileName", "DateExtracted", "EntityType", "BatchID"):
        if key in info:
            lines.append(f"{key + ':':<16}{info[key]}")
    print("\n".join(lines))
    return 0


def cmd_accounts(args) -> int:
    mye = core.load(args.file)
    print(_table([(a.code, a.name) for a in mye.accounts], ["Code", "Account name"]))
    return 0


def cmd_journal(args) -> int:
    mye = core.load(args.file)
    names = mye.account_map()
    rows = []
    needle = args.search.lower() if args.search else None
    for i, entry in enumerate(mye.entries, 1):
        for line in entry.lines:
            if args.account and line.account_code != args.account:
                continue
            if needle and needle not in line.memo.lower():
                continue
            rows.append(
                (
                    i,
                    line.date,
                    line.reference,
                    line.account_code,
                    names.get(line.account_code, ""),
                    f"{line.debit:,.2f}" if line.debit else "",
                    f"{line.credit:,.2f}" if line.credit else "",
                    line.memo,
                )
            )
    if args.limit and len(rows) > args.limit:
        shown = rows[: args.limit]
        print(
            _table(
                shown,
                ["Entry", "Date", "Ref", "Acct", "Account name", "Debit", "Credit", "Memo"],
            )
        )
        print(f"... {len(rows) - args.limit} more lines (use --limit 0 to show all)")
    else:
        print(
            _table(
                rows,
                ["Entry", "Date", "Ref", "Acct", "Account name", "Debit", "Credit", "Memo"],
            )
        )
    return 0


def cmd_trial_balance(args) -> int:
    mye = core.load(args.file)
    rows = [
        (code, name, f"{debit:,.2f}", f"{credit:,.2f}", f"{net:,.2f}")
        for code, name, debit, credit, net in mye.trial_balance()
    ]
    print(_table(rows, ["Code", "Account name", "Debits", "Credits", "Net"]))
    return 0


def cmd_check(args) -> int:
    mye = core.load(args.file)
    problems = mye.validate()
    if not problems:
        print(
            f"OK: {len(mye.entries)} journal entries all balance, every account "
            "code is in the chart, all dates are valid and within the period."
        )
        return 0
    for problem in problems:
        print(f"PROBLEM: {problem}")
    print(f"\n{len(problems)} problem(s) found.")
    return 1


def cmd_export(args) -> int:
    mye = core.load(args.file)
    base = os.path.splitext(os.path.basename(args.file))[0]
    os.makedirs(args.out, exist_ok=True)
    written = []
    formats = {"all": ("csv", "xlsx", "json", "iif", "xero-coa")}.get(
        args.format, (args.format,)
    )
    if "csv" in formats:
        written += exporters.export_csv(mye, args.out)
    if "xlsx" in formats:
        written.append(exporters.export_xlsx(mye, os.path.join(args.out, base + ".xlsx")))
    if "json" in formats:
        written.append(exporters.export_json(mye, os.path.join(args.out, base + ".json")))
    if "iif" in formats:
        written.append(exporters.export_iif(mye, os.path.join(args.out, base + ".iif")))
    if "xero-coa" in formats:
        renumber = getattr(args, "renumber", False)
        written.append(
            exporters.export_xero_coa(
                mye,
                os.path.join(args.out, "xero_chart_of_accounts.csv"),
                renumber=renumber,
            )
        )
        written.append(
            exporters.export_xero_coa_review(
                mye,
                os.path.join(args.out, "xero_chart_of_accounts_REVIEW.csv"),
                renumber=renumber,
            )
        )
        if renumber:
            written.append(
                exporters.export_code_mapping(
                    mye, os.path.join(args.out, "code_mapping.csv")
                )
            )
    for path in written:
        print(f"wrote {path}")
    return 0


def cmd_unpack(args) -> int:
    mye = core.load(args.file)
    for path in exporters.unpack(mye, args.out):
        print(f"wrote {path}")
    print(
        "\nEdit accounts.csv / journal.csv / company.csv (Excel is fine), then run:\n"
        f"  python -m mye_tool pack {args.out} -o edited.mye"
    )
    return 0


def cmd_pack(args) -> int:
    mye = exporters.pack_dir(args.dir)
    problems = mye.validate()
    if problems and not args.force:
        for problem in problems:
            print(f"PROBLEM: {problem}", file=sys.stderr)
        print(
            f"\nRefusing to write an invalid .MYE ({len(problems)} problem(s)). "
            "Fix the CSVs or re-run with --force.",
            file=sys.stderr,
        )
        return 1
    mye.save(args.out)
    print(
        f"wrote {args.out} ({len(mye.accounts)} accounts, {len(mye.entries)} "
        f"journal entries)"
    )
    if problems:
        print(f"warning: written with --force despite {len(problems)} problem(s)")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="mye_tool",
        description="Read, validate, convert and edit MYOB AE/MAS .MYE general "
        "ledger files (e.g. Xero's 'Accountants Enterprise (MAS)' export).",
    )
    parser.add_argument("--version", action="version", version=f"mye_tool {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("info", help="show file metadata and record counts")
    p.add_argument("file")
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("accounts", help="list the chart of accounts")
    p.add_argument("file")
    p.set_defaults(func=cmd_accounts)

    p = sub.add_parser("journal", help="list journal lines")
    p.add_argument("file")
    p.add_argument("--account", help="only lines posted to this account code")
    p.add_argument("--search", help="only lines whose memo contains this text")
    p.add_argument(
        "--limit", type=int, default=50, help="max lines to print (0 = all, default 50)"
    )
    p.set_defaults(func=cmd_journal)

    p = sub.add_parser("trial-balance", help="net movement per account")
    p.add_argument("file")
    p.set_defaults(func=cmd_trial_balance)

    p = sub.add_parser("check", help="validate balancing, account codes and dates")
    p.add_argument("file")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("export", help="export to csv / xlsx / json / iif")
    p.add_argument("file")
    p.add_argument("-o", "--out", default="mye_export", help="output directory")
    p.add_argument(
        "--format",
        choices=["csv", "xlsx", "json", "iif", "xero-coa", "all"],
        default="all",
        help="which format(s) to write (default: all). 'xero-coa' writes a "
        "Xero (AU) chart-of-accounts import CSV plus a review file.",
    )
    p.add_argument(
        "--renumber",
        action="store_true",
        help="with xero-coa: assign clean 3-digit account codes (keeps "
        "existing valid 3-digit codes, renumbers the rest) and write "
        "code_mapping.csv",
    )
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("unpack", help="explode into editable CSVs")
    p.add_argument("file")
    p.add_argument("-o", "--out", default="mye_work", help="output directory")
    p.set_defaults(func=cmd_unpack)

    p = sub.add_parser("pack", help="rebuild a .MYE from an unpacked directory")
    p.add_argument("dir")
    p.add_argument("-o", "--out", required=True, help="output .mye path")
    p.add_argument(
        "--force", action="store_true", help="write even if validation fails"
    )
    p.set_defaults(func=cmd_pack)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
