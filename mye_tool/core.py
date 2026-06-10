"""Core data model, parser and writer for MYOB .MYE general ledger files.

The on-disk format (reverse engineered from a Xero "Accountants
Enterprise (MAS)" export) is a ZIP archive with two members:

``Extract.inf``
    Windows INI text describing the extract (date range, company file
    name, batch id, ...).

``MYOBAO.TXT``
    cp1252 text, CRLF line endings, three sections::

        [MYOB2000.05]
        <name>\t<address>\t\t\t<period start DD/MM/YYYY>\t<period end>
        [ACCOUNTS]
        <code>\t\t<account name>\t          (one line per account)
        [JOURNAL]
        <date>\t<ref>\t<code>\t<amount>\t<memo>\r   (note: line ends \r\r\n)
        ...                                 (blank line between entries)

    Amounts use four decimal places; positive values are debits and
    negative values are credits, so every journal entry sums to zero.

The writer reproduces this byte layout exactly, so a parse -> write
round trip of an unmodified file yields identical MYOBAO.TXT bytes.
"""

from __future__ import annotations

import configparser
import io
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Iterable, Iterator, List, Optional

ENCODING = "cp1252"
HEADER_SECTION = "[MYOB2000.05]"
ACCOUNTS_SECTION = "[ACCOUNTS]"
JOURNAL_SECTION = "[JOURNAL]"
DATA_MEMBER = "MYOBAO.TXT"
INF_MEMBER = "Extract.inf"
DATE_FORMAT = "%d/%m/%Y"


def parse_date(value: str) -> Optional[datetime]:
    try:
        return datetime.strptime(value, DATE_FORMAT)
    except ValueError:
        return None


@dataclass
class Account:
    """One row of the [ACCOUNTS] section.

    The section stores four tab-separated fields; fields 2 and 4 are
    blank in every file observed so far but are preserved verbatim so
    unknown data is never dropped.
    """

    code: str
    name: str
    extra1: str = ""
    extra2: str = ""

    @classmethod
    def from_fields(cls, fields: List[str]) -> "Account":
        fields = fields + [""] * (4 - len(fields))
        return cls(code=fields[0], name=fields[2], extra1=fields[1], extra2=fields[3])

    def to_fields(self) -> List[str]:
        return [self.code, self.extra1, self.name, self.extra2]


@dataclass
class JournalLine:
    """One debit/credit line of a journal entry."""

    date: str  # DD/MM/YYYY, kept as text to preserve formatting
    reference: str  # journal/entry number
    account_code: str
    amount: Decimal  # positive = debit, negative = credit
    memo: str

    @property
    def debit(self) -> Decimal:
        return self.amount if self.amount > 0 else Decimal("0")

    @property
    def credit(self) -> Decimal:
        return -self.amount if self.amount < 0 else Decimal("0")

    @classmethod
    def from_fields(cls, fields: List[str]) -> "JournalLine":
        fields = fields + [""] * (5 - len(fields))
        return cls(
            date=fields[0],
            reference=fields[1],
            account_code=fields[2],
            amount=Decimal(fields[3]) if fields[3] else Decimal("0"),
            memo=fields[4],
        )

    def to_fields(self) -> List[str]:
        return [
            self.date,
            self.reference,
            self.account_code,
            f"{self.amount:.4f}",
            self.memo,
        ]


@dataclass
class JournalEntry:
    """A group of journal lines separated from its neighbours by a blank
    line in the file. Lines of an entry share a reference number and
    should sum to zero."""

    lines: List[JournalLine] = field(default_factory=list)

    @property
    def reference(self) -> str:
        return self.lines[0].reference if self.lines else ""

    @property
    def date(self) -> str:
        return self.lines[0].date if self.lines else ""

    @property
    def total(self) -> Decimal:
        return sum((l.amount for l in self.lines), Decimal("0"))

    @property
    def is_balanced(self) -> bool:
        return self.total == 0


@dataclass
class MyeFile:
    """Parsed contents of a .MYE archive."""

    # [MYOB2000.05] company line: name, address, two spare fields,
    # period start, period end - preserved as the raw field list.
    company_fields: List[str] = field(default_factory=lambda: ["", "", "", "", "", ""])
    accounts: List[Account] = field(default_factory=list)
    entries: List[JournalEntry] = field(default_factory=list)
    # Raw bytes of Extract.inf, preserved for byte-exact repacking.
    extract_inf: bytes = b""

    # ----- convenience accessors -------------------------------------

    @property
    def company_name(self) -> str:
        return self.company_fields[0] if self.company_fields else ""

    @company_name.setter
    def company_name(self, value: str) -> None:
        self.company_fields[0] = value

    @property
    def address(self) -> str:
        return self.company_fields[1] if len(self.company_fields) > 1 else ""

    @property
    def period_start(self) -> str:
        return self.company_fields[4] if len(self.company_fields) > 4 else ""

    @property
    def period_end(self) -> str:
        return self.company_fields[5] if len(self.company_fields) > 5 else ""

    @property
    def journal_lines(self) -> Iterator[JournalLine]:
        for entry in self.entries:
            yield from entry.lines

    def account_map(self) -> dict:
        return {a.code: a.name for a in self.accounts}

    def extract_info(self) -> dict:
        """Extract.inf parsed into a flat dict (read-only view)."""
        parser = configparser.ConfigParser(interpolation=None)
        parser.optionxform = str  # keep key case
        try:
            parser.read_string(self.extract_inf.decode(ENCODING, "replace"))
        except configparser.Error:
            return {}
        info: dict = {}
        for section in parser.sections():
            for key, value in parser.items(section):
                info[key] = value
        return info

    def trial_balance(self) -> List[tuple]:
        """Net movement per account over the export period.

        Returns (code, name, debit_total, credit_total, net) tuples in
        chart-of-accounts order, then any codes used in the journal but
        missing from the chart.
        """
        totals: dict = {}
        debits: dict = {}
        credits: dict = {}
        for line in self.journal_lines:
            totals[line.account_code] = (
                totals.get(line.account_code, Decimal("0")) + line.amount
            )
            debits[line.account_code] = (
                debits.get(line.account_code, Decimal("0")) + line.debit
            )
            credits[line.account_code] = (
                credits.get(line.account_code, Decimal("0")) + line.credit
            )
        names = self.account_map()
        rows = []
        seen = set()
        for account in self.accounts:
            if account.code in totals:
                seen.add(account.code)
                rows.append(
                    (
                        account.code,
                        account.name,
                        debits[account.code],
                        credits[account.code],
                        totals[account.code],
                    )
                )
        for code in sorted(set(totals) - seen):
            rows.append(
                (code, names.get(code, "(not in chart)"), debits[code], credits[code], totals[code])
            )
        return rows

    def validate(self) -> List[str]:
        """Return a list of human-readable problems (empty = clean)."""
        problems: List[str] = []
        known_codes = {a.code for a in self.accounts}
        start = parse_date(self.period_start)
        end = parse_date(self.period_end)
        for i, entry in enumerate(self.entries, 1):
            if not entry.is_balanced:
                problems.append(
                    f"Entry #{i} (ref {entry.reference}, {entry.date}) does not "
                    f"balance: net {entry.total:+.4f}"
                )
            refs = {l.reference for l in entry.lines}
            if len(refs) > 1:
                problems.append(
                    f"Entry #{i} mixes reference numbers: {', '.join(sorted(refs))}"
                )
            for line in entry.lines:
                if line.account_code not in known_codes:
                    problems.append(
                        f"Entry #{i} (ref {entry.reference}) uses account "
                        f"'{line.account_code}' which is not in the chart of accounts"
                    )
                d = parse_date(line.date)
                if d is None:
                    problems.append(
                        f"Entry #{i} (ref {entry.reference}) has unparseable "
                        f"date '{line.date}'"
                    )
                elif start and end and not (start <= d <= end):
                    problems.append(
                        f"Entry #{i} (ref {entry.reference}) dated {line.date} is "
                        f"outside the export period {self.period_start} - {self.period_end}"
                    )
        return problems

    # ----- serialisation ----------------------------------------------

    def data_text_bytes(self) -> bytes:
        """Serialise MYOBAO.TXT exactly as MYOB/Xero write it."""
        out = io.BytesIO()

        def w(text: str) -> None:
            out.write(text.encode(ENCODING))

        w(HEADER_SECTION + "\r\n")
        w("\t".join(self.company_fields) + "\r\n")
        w(ACCOUNTS_SECTION + "\r\n")
        for account in self.accounts:
            w("\t".join(account.to_fields()) + "\r\n")
        w(JOURNAL_SECTION + "\r\n")
        for entry in self.entries:
            for line in entry.lines:
                # Journal lines genuinely end \r\r\n in MYOB's output.
                w("\t".join(line.to_fields()) + "\r\r\n")
            w("\r\n")
        return out.getvalue()

    def save(self, path: str) -> None:
        """Write a .MYE (ZIP) archive."""
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(INF_MEMBER, self.extract_inf)
            z.writestr(DATA_MEMBER, self.data_text_bytes())


# ----- parsing ---------------------------------------------------------


def _parse_data_text(data: bytes) -> MyeFile:
    mye = MyeFile()
    text = data.decode(ENCODING)
    section = None
    pending_entry: Optional[JournalEntry] = None

    for raw_line in text.split("\r\n"):
        line = raw_line.rstrip("\r")  # journal lines carry an extra \r
        if line.startswith("[") and line.endswith("]"):
            section = line
            pending_entry = None
            continue
        if section == HEADER_SECTION:
            mye.company_fields = line.split("\t")
            section = "header-done"
        elif section == ACCOUNTS_SECTION:
            if line:
                mye.accounts.append(Account.from_fields(line.split("\t")))
        elif section == JOURNAL_SECTION:
            if not line:
                pending_entry = None  # blank line closes the entry
                continue
            if pending_entry is None:
                pending_entry = JournalEntry()
                mye.entries.append(pending_entry)
            pending_entry.lines.append(JournalLine.from_fields(line.split("\t")))
    return mye


def loads(archive_bytes: bytes) -> MyeFile:
    """Parse a .MYE archive from memory."""
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as z:
        names = {n.lower(): n for n in z.namelist()}
        data_name = names.get(DATA_MEMBER.lower())
        if data_name is None:
            txts = [n for n in z.namelist() if n.lower().endswith(".txt")]
            if not txts:
                raise ValueError(
                    f"Not a recognised .MYE file: no {DATA_MEMBER} inside the archive "
                    f"(members: {', '.join(z.namelist()) or 'none'})"
                )
            data_name = txts[0]
        mye = _parse_data_text(z.read(data_name))
        inf_name = names.get(INF_MEMBER.lower())
        if inf_name:
            mye.extract_inf = z.read(inf_name)
    return mye


def load(path: str) -> MyeFile:
    """Parse a .MYE file from disk."""
    with open(path, "rb") as fh:
        data = fh.read()
    if not data.startswith(b"PK"):
        raise ValueError(
            f"{path} is not a ZIP-based .MYE file (it may be an older "
            "StuffIt-packed AccountEdge export; extract it with The "
            "Unarchiver/unar first)"
        )
    return loads(data)
