"""mye_tool - read, edit, and convert MYOB AE/MAS General Ledger .MYE files.

A .MYE file (as produced by Xero's "Export accounting data" feature for
MYOB Accountants Enterprise / MAS, and by MYOB AccountRight/AccountEdge
"Accountants Link") is a ZIP archive containing:

  Extract.inf  - INI-style metadata about the extract
  MYOBAO.TXT   - tab-delimited general ledger data with [SECTION] headers:
                   [MYOB2000.05]  company name, address, period start/end
                   [ACCOUNTS]     chart of accounts (code, name)
                   [JOURNAL]      journal lines (date, ref, account,
                                  amount, memo), entries separated by
                                  blank lines; positive = debit,
                                  negative = credit
"""

from .core import (
    Account,
    JournalEntry,
    JournalLine,
    MyeFile,
    load,
    loads,
)

__version__ = "1.0.0"

__all__ = [
    "Account",
    "JournalEntry",
    "JournalLine",
    "MyeFile",
    "load",
    "loads",
    "__version__",
]
