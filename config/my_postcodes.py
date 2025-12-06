"""
Your Tracked Postcodes Configuration

Add the postcodes you want to track here. The scraper will ONLY
fetch auction results for these suburbs - nothing else.

This keeps requests minimal and respectful to realestate.com.au
"""

# =============================================================================
# ADD YOUR POSTCODES HERE
# =============================================================================
# Format: "postcode": "suburb-name-for-url"
# The suburb name should be lowercase with hyphens (as it appears in the URL)
#
# To find the correct format:
# 1. Go to https://www.realestate.com.au/auction-results/nsw
# 2. Click on your suburb
# 3. Copy the suburb-postcode part from the URL
#    e.g., /auction-results/nsw/paddington-2021 -> "2021": "paddington"

TRACKED_POSTCODES = {
    # Sydney Eastern Suburbs - Examples (edit these!)
    # "2021": "paddington",
    # "2026": "bondi",
    # "2027": "darling-point",
    # "2028": "double-bay",

    # Sydney Inner West - Examples
    # "2040": "leichhardt",
    # "2041": "balmain",

    # Sydney North Shore - Examples
    # "2065": "crows-nest",
    # "2066": "lane-cove",

    # Northern Beaches - Examples
    # "2095": "manly",
    # "2099": "dee-why",

    # Add your postcodes below:
    # "XXXX": "suburb-name",
}

# =============================================================================
# OPTIONAL: Group your postcodes for reporting
# =============================================================================
MY_REGIONS = {
    "my_watch_list": list(TRACKED_POSTCODES.keys()),

    # You can create custom groups:
    # "investment_targets": ["2021", "2026"],
    # "family_homes": ["2066", "2067"],
}


def get_tracked_suburbs():
    """
    Returns list of suburb URLs to track.

    Returns:
        List of dicts with suburb info
    """
    from config.settings import BASE_URL

    suburbs = []
    for postcode, suburb_slug in TRACKED_POSTCODES.items():
        suburbs.append({
            'suburb': suburb_slug.replace('-', ' ').title(),
            'postcode': postcode,
            'slug': suburb_slug,
            'url': f"{BASE_URL}/auction-results/nsw/{suburb_slug}-{postcode}"
        })

    return suburbs


def validate_config():
    """Check if any postcodes are configured."""
    if not TRACKED_POSTCODES:
        print("=" * 60)
        print("NO POSTCODES CONFIGURED!")
        print("=" * 60)
        print()
        print("Edit config/my_postcodes.py and add the postcodes you")
        print("want to track. For example:")
        print()
        print('TRACKED_POSTCODES = {')
        print('    "2021": "paddington",')
        print('    "2026": "bondi",')
        print('}')
        print()
        return False
    return True
