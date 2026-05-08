"""Parsers for monthly source files.

Each parser exposes a parse(path) function that returns a partial Month dict.
A higher-level builder merges all partial dicts plus a manual.yml override
into a complete Month entry.

All parsers are best-effort: they extract what they can from the file format,
and any field they can't determine is left out so the manual.yml override
can fill it in. The dashboard schema is the contract — see DASHBOARD_INSTRUCTIONS.md.
"""

from .zai_invoice import parse_zai_invoice
from .platform_revenue import parse_platform_revenue
from .agency_performance import parse_agency_performance
from .mw_charges import parse_mw_charges
from .manual import load_manual

__all__ = [
    "parse_zai_invoice",
    "parse_platform_revenue",
    "parse_agency_performance",
    "parse_mw_charges",
    "load_manual",
]
