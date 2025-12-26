"""
Sector Classification - Map ASX stocks to GICS sectors.

Uses a built-in database of common ASX stocks plus Yahoo Finance
for dynamic lookups.
"""

import logging
from typing import Dict, Optional, List, Any
from datetime import datetime

from .models import Sector, Holding, Portfolio

logger = logging.getLogger(__name__)


# GICS Sector mappings for common ASX stocks
# Source: ASX company classifications
ASX_SECTOR_MAP: Dict[str, Sector] = {
    # === FINANCIALS ===
    # Big 4 Banks
    "CBA": Sector.FINANCIALS,
    "WBC": Sector.FINANCIALS,
    "NAB": Sector.FINANCIALS,
    "ANZ": Sector.FINANCIALS,
    # Other Banks
    "MQG": Sector.FINANCIALS,
    "BEN": Sector.FINANCIALS,
    "BOQ": Sector.FINANCIALS,
    "SUN": Sector.FINANCIALS,
    "IAG": Sector.FINANCIALS,
    "QBE": Sector.FINANCIALS,
    "MPL": Sector.FINANCIALS,
    "AMP": Sector.FINANCIALS,
    "HUB": Sector.FINANCIALS,
    "NWL": Sector.FINANCIALS,
    "PPT": Sector.FINANCIALS,
    "CGF": Sector.FINANCIALS,
    "JHX": Sector.FINANCIALS,
    "ASX": Sector.FINANCIALS,

    # === MATERIALS (Mining) ===
    "BHP": Sector.MATERIALS,
    "RIO": Sector.MATERIALS,
    "FMG": Sector.MATERIALS,
    "MIN": Sector.MATERIALS,
    "S32": Sector.MATERIALS,
    "NCM": Sector.MATERIALS,
    "NST": Sector.MATERIALS,
    "EVN": Sector.MATERIALS,
    "NEM": Sector.MATERIALS,
    "IGO": Sector.MATERIALS,
    "OZL": Sector.MATERIALS,
    "SFR": Sector.MATERIALS,
    "AWC": Sector.MATERIALS,
    "ILU": Sector.MATERIALS,
    "ORI": Sector.MATERIALS,
    "AMC": Sector.MATERIALS,
    "BSL": Sector.MATERIALS,
    "WHC": Sector.MATERIALS,
    "PLS": Sector.MATERIALS,
    "LTR": Sector.MATERIALS,
    "AKE": Sector.MATERIALS,
    "PIL": Sector.MATERIALS,
    "LYC": Sector.MATERIALS,
    "SYR": Sector.MATERIALS,
    "KGN": Sector.MATERIALS,

    # === ENERGY ===
    "WDS": Sector.ENERGY,
    "STO": Sector.ENERGY,
    "ORG": Sector.ENERGY,
    "WPL": Sector.ENERGY,
    "OSH": Sector.ENERGY,
    "APA": Sector.ENERGY,
    "BPT": Sector.ENERGY,
    "KAR": Sector.ENERGY,
    "WHN": Sector.ENERGY,
    "VEA": Sector.ENERGY,

    # === HEALTH CARE ===
    "CSL": Sector.HEALTH_CARE,
    "COH": Sector.HEALTH_CARE,
    "RMD": Sector.HEALTH_CARE,
    "SHL": Sector.HEALTH_CARE,
    "PME": Sector.HEALTH_CARE,
    "FPH": Sector.HEALTH_CARE,
    "RHC": Sector.HEALTH_CARE,
    "ANN": Sector.HEALTH_CARE,
    "NHF": Sector.HEALTH_CARE,
    "TLX": Sector.HEALTH_CARE,
    "IMU": Sector.HEALTH_CARE,
    "NEU": Sector.HEALTH_CARE,
    "PNV": Sector.HEALTH_CARE,
    "PRU": Sector.HEALTH_CARE,
    "SIG": Sector.HEALTH_CARE,
    "SDR": Sector.HEALTH_CARE,

    # === CONSUMER DISCRETIONARY ===
    "WES": Sector.CONSUMER_DISCRETIONARY,
    "HVN": Sector.CONSUMER_DISCRETIONARY,
    "JBH": Sector.CONSUMER_DISCRETIONARY,
    "SUL": Sector.CONSUMER_DISCRETIONARY,
    "FLT": Sector.CONSUMER_DISCRETIONARY,
    "ALL": Sector.CONSUMER_DISCRETIONARY,
    "TAH": Sector.CONSUMER_DISCRETIONARY,
    "SXL": Sector.CONSUMER_DISCRETIONARY,
    "APE": Sector.CONSUMER_DISCRETIONARY,
    "BBN": Sector.CONSUMER_DISCRETIONARY,
    "NCK": Sector.CONSUMER_DISCRETIONARY,
    "PMV": Sector.CONSUMER_DISCRETIONARY,
    "BRG": Sector.CONSUMER_DISCRETIONARY,
    "AX1": Sector.CONSUMER_DISCRETIONARY,
    "NXT": Sector.CONSUMER_DISCRETIONARY,
    "DMP": Sector.CONSUMER_DISCRETIONARY,
    "REA": Sector.CONSUMER_DISCRETIONARY,
    "CAR": Sector.CONSUMER_DISCRETIONARY,
    "SEK": Sector.CONSUMER_DISCRETIONARY,
    "WTC": Sector.CONSUMER_DISCRETIONARY,
    "ARB": Sector.CONSUMER_DISCRETIONARY,

    # === CONSUMER STAPLES ===
    "WOW": Sector.CONSUMER_STAPLES,
    "COL": Sector.CONSUMER_STAPLES,
    "TWE": Sector.CONSUMER_STAPLES,
    "A2M": Sector.CONSUMER_STAPLES,
    "CCL": Sector.CONSUMER_STAPLES,
    "BAP": Sector.CONSUMER_STAPLES,
    "ING": Sector.CONSUMER_STAPLES,
    "BGA": Sector.CONSUMER_STAPLES,
    "GNC": Sector.CONSUMER_STAPLES,
    "ELD": Sector.CONSUMER_STAPLES,
    "CGC": Sector.CONSUMER_STAPLES,
    "TGR": Sector.CONSUMER_STAPLES,
    "SDF": Sector.CONSUMER_STAPLES,

    # === INDUSTRIALS ===
    "TCL": Sector.INDUSTRIALS,
    "SYD": Sector.INDUSTRIALS,
    "QAN": Sector.INDUSTRIALS,
    "BXB": Sector.INDUSTRIALS,
    "AZJ": Sector.INDUSTRIALS,
    "QUB": Sector.INDUSTRIALS,
    "DOW": Sector.INDUSTRIALS,
    "SEV": Sector.INDUSTRIALS,
    "AUB": Sector.INDUSTRIALS,
    "CIM": Sector.INDUSTRIALS,
    "NWH": Sector.INDUSTRIALS,
    "WOR": Sector.INDUSTRIALS,
    "ALQ": Sector.INDUSTRIALS,
    "MND": Sector.INDUSTRIALS,
    "DRR": Sector.INDUSTRIALS,
    "CDA": Sector.INDUSTRIALS,
    "IPL": Sector.INDUSTRIALS,
    "IEL": Sector.INDUSTRIALS,

    # === INFORMATION TECHNOLOGY ===
    "XRO": Sector.INFORMATION_TECHNOLOGY,
    "WTC": Sector.INFORMATION_TECHNOLOGY,
    "CPU": Sector.INFORMATION_TECHNOLOGY,
    "TLS": Sector.COMMUNICATION_SERVICES,  # Telco is communication services
    "TNE": Sector.INFORMATION_TECHNOLOGY,
    "ALU": Sector.INFORMATION_TECHNOLOGY,
    "APX": Sector.INFORMATION_TECHNOLOGY,
    "MP1": Sector.INFORMATION_TECHNOLOGY,
    "NXT": Sector.INFORMATION_TECHNOLOGY,
    "AD8": Sector.INFORMATION_TECHNOLOGY,
    "SQ2": Sector.INFORMATION_TECHNOLOGY,
    "TPG": Sector.COMMUNICATION_SERVICES,
    "APT": Sector.INFORMATION_TECHNOLOGY,
    "Z1P": Sector.INFORMATION_TECHNOLOGY,
    "TYR": Sector.INFORMATION_TECHNOLOGY,
    "NXL": Sector.INFORMATION_TECHNOLOGY,
    "MAD": Sector.INFORMATION_TECHNOLOGY,
    "SIQ": Sector.INFORMATION_TECHNOLOGY,

    # === COMMUNICATION SERVICES ===
    "TLS": Sector.COMMUNICATION_SERVICES,
    "TPG": Sector.COMMUNICATION_SERVICES,
    "REH": Sector.COMMUNICATION_SERVICES,
    "NWS": Sector.COMMUNICATION_SERVICES,
    "NEC": Sector.COMMUNICATION_SERVICES,
    "OML": Sector.COMMUNICATION_SERVICES,
    "SWM": Sector.COMMUNICATION_SERVICES,
    "CWN": Sector.COMMUNICATION_SERVICES,

    # === UTILITIES ===
    "AGL": Sector.UTILITIES,
    "ORG": Sector.UTILITIES,
    "APA": Sector.UTILITIES,
    "SKI": Sector.UTILITIES,
    "AST": Sector.UTILITIES,
    "DBI": Sector.UTILITIES,
    "MEZ": Sector.UTILITIES,

    # === REAL ESTATE (REITs) ===
    "GMG": Sector.REAL_ESTATE,
    "SCG": Sector.REAL_ESTATE,
    "DXS": Sector.REAL_ESTATE,
    "GPT": Sector.REAL_ESTATE,
    "MGR": Sector.REAL_ESTATE,
    "SGP": Sector.REAL_ESTATE,
    "VCX": Sector.REAL_ESTATE,
    "CHC": Sector.REAL_ESTATE,
    "BWP": Sector.REAL_ESTATE,
    "CLW": Sector.REAL_ESTATE,
    "CIP": Sector.REAL_ESTATE,
    "CQR": Sector.REAL_ESTATE,
    "HMC": Sector.REAL_ESTATE,
    "NSR": Sector.REAL_ESTATE,
    "SCP": Sector.REAL_ESTATE,
    "WPR": Sector.REAL_ESTATE,
    "ARF": Sector.REAL_ESTATE,
    "CNI": Sector.REAL_ESTATE,
    "RFF": Sector.REAL_ESTATE,
    "PGF": Sector.REAL_ESTATE,

    # === DIVERSIFIED (ETFs/LICs) ===
    # Broad market ETFs
    "VAS": Sector.DIVERSIFIED,
    "VGS": Sector.DIVERSIFIED,
    "A200": Sector.DIVERSIFIED,
    "IOZ": Sector.DIVERSIFIED,
    "STW": Sector.DIVERSIFIED,
    "IVV": Sector.DIVERSIFIED,
    "VDHG": Sector.DIVERSIFIED,
    "DHHF": Sector.DIVERSIFIED,
    "VHY": Sector.DIVERSIFIED,
    "HVST": Sector.DIVERSIFIED,
    "NDQ": Sector.DIVERSIFIED,
    "QUAL": Sector.DIVERSIFIED,
    "UMAX": Sector.DIVERSIFIED,
    "VEU": Sector.DIVERSIFIED,
    "VTS": Sector.DIVERSIFIED,
    "VDGR": Sector.DIVERSIFIED,
    "VDBA": Sector.DIVERSIFIED,
    "VDCO": Sector.DIVERSIFIED,

    # Listed Investment Companies
    "AFI": Sector.DIVERSIFIED,
    "ARG": Sector.DIVERSIFIED,
    "AUI": Sector.DIVERSIFIED,
    "BKI": Sector.DIVERSIFIED,
    "MLT": Sector.DIVERSIFIED,
    "SOL": Sector.DIVERSIFIED,
    "WAM": Sector.DIVERSIFIED,
    "MFF": Sector.DIVERSIFIED,
    "WLE": Sector.DIVERSIFIED,
    "WHF": Sector.DIVERSIFIED,

    # Sector-specific ETFs (classify by their sector focus)
    "HACK": Sector.INFORMATION_TECHNOLOGY,
    "TECH": Sector.INFORMATION_TECHNOLOGY,
    "ACDC": Sector.MATERIALS,  # Battery metals
    "CRYP": Sector.INFORMATION_TECHNOLOGY,  # Crypto-related
}


def get_sector(code: str) -> Sector:
    """
    Get the GICS sector for an ASX stock.

    Args:
        code: ASX ticker code

    Returns:
        Sector enum value
    """
    return ASX_SECTOR_MAP.get(code.upper(), Sector.UNKNOWN)


def classify_holding(holding: Holding) -> Sector:
    """
    Classify a holding's sector.

    Args:
        holding: Holding object to classify

    Returns:
        Sector enum value
    """
    # First check our built-in map
    sector = ASX_SECTOR_MAP.get(holding.code.upper())
    if sector:
        return sector

    # If not found, keep current or return unknown
    if holding.sector != Sector.UNKNOWN:
        return holding.sector

    return Sector.UNKNOWN


def classify_portfolio(portfolio: Portfolio) -> Dict[str, Any]:
    """
    Classify all holdings in a portfolio by sector.

    Args:
        portfolio: Portfolio to classify

    Returns:
        Dictionary with classification results
    """
    classified = 0
    unknown = 0

    for holding in portfolio.holdings:
        sector = classify_holding(holding)
        if sector != Sector.UNKNOWN:
            holding.sector = sector
            classified += 1
        else:
            unknown += 1

    return {
        "classified": classified,
        "unknown": unknown,
        "total": len(portfolio.holdings),
        "unknown_codes": [h.code for h in portfolio.holdings if h.sector == Sector.UNKNOWN],
    }


def get_sector_summary(portfolio: Portfolio) -> Dict[str, Dict[str, Any]]:
    """
    Get a summary of holdings by sector.

    Args:
        portfolio: Portfolio to analyze

    Returns:
        Dictionary mapping sector names to their details
    """
    sector_data: Dict[Sector, Dict[str, Any]] = {}

    for holding in portfolio.holdings:
        sector = holding.sector
        if sector not in sector_data:
            sector_data[sector] = {
                "count": 0,
                "market_value": 0,
                "cost_base": 0,
                "profit_loss": 0,
                "weight": 0,
                "holdings": [],
            }

        data = sector_data[sector]
        data["count"] += 1
        data["market_value"] += float(holding.market_value)
        data["cost_base"] += float(holding.cost_base)
        data["profit_loss"] += float(holding.profit_loss)
        data["weight"] += float(holding.portfolio_weight)
        data["holdings"].append(holding.code)

    # Calculate returns for each sector
    result = {}
    for sector, data in sorted(sector_data.items(), key=lambda x: x[1]["weight"], reverse=True):
        sector_name = sector.value.replace("_", " ").title()
        data["return_percent"] = (
            (data["profit_loss"] / data["cost_base"]) * 100
            if data["cost_base"] > 0 else 0
        )
        result[sector_name] = data

    return result


def fetch_sector_from_yahoo(code: str) -> Optional[Sector]:
    """
    Fetch sector classification from Yahoo Finance.

    Args:
        code: ASX ticker code

    Returns:
        Sector enum or None if fetch failed
    """
    try:
        import requests
    except ImportError:
        return None

    try:
        # Yahoo Finance quote summary endpoint
        url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{code}.AX"
        params = {"modules": "assetProfile"}
        headers = {"User-Agent": "Mozilla/5.0"}

        response = requests.get(url, params=params, headers=headers, timeout=5)
        response.raise_for_status()

        data = response.json()
        profile = data.get("quoteSummary", {}).get("result", [{}])[0].get("assetProfile", {})
        sector_name = profile.get("sector", "").lower()

        # Map Yahoo sector names to our Sector enum
        sector_map = {
            "financial services": Sector.FINANCIALS,
            "financials": Sector.FINANCIALS,
            "basic materials": Sector.MATERIALS,
            "materials": Sector.MATERIALS,
            "energy": Sector.ENERGY,
            "healthcare": Sector.HEALTH_CARE,
            "health care": Sector.HEALTH_CARE,
            "consumer cyclical": Sector.CONSUMER_DISCRETIONARY,
            "consumer discretionary": Sector.CONSUMER_DISCRETIONARY,
            "consumer defensive": Sector.CONSUMER_STAPLES,
            "consumer staples": Sector.CONSUMER_STAPLES,
            "industrials": Sector.INDUSTRIALS,
            "technology": Sector.INFORMATION_TECHNOLOGY,
            "information technology": Sector.INFORMATION_TECHNOLOGY,
            "communication services": Sector.COMMUNICATION_SERVICES,
            "utilities": Sector.UTILITIES,
            "real estate": Sector.REAL_ESTATE,
        }

        return sector_map.get(sector_name, Sector.UNKNOWN)

    except Exception as e:
        logger.debug(f"Failed to fetch sector for {code}: {e}")
        return None


def update_sectors_from_yahoo(portfolio: Portfolio) -> Dict[str, Any]:
    """
    Update unknown sectors by fetching from Yahoo Finance.

    Args:
        portfolio: Portfolio to update

    Returns:
        Dictionary with update results
    """
    unknown_holdings = [h for h in portfolio.holdings if h.sector == Sector.UNKNOWN]

    if not unknown_holdings:
        return {"updated": 0, "failed": 0, "total": 0}

    updated = 0
    failed = 0

    for holding in unknown_holdings:
        sector = fetch_sector_from_yahoo(holding.code)
        if sector and sector != Sector.UNKNOWN:
            holding.sector = sector
            updated += 1
            logger.info(f"Updated {holding.code} sector to {sector.value}")
        else:
            failed += 1

    return {
        "updated": updated,
        "failed": failed,
        "total": len(unknown_holdings),
    }
