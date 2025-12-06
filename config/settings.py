"""
Configuration settings for NSW Auction Results Scraper
"""
from pathlib import Path
from datetime import datetime

# Base paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
ARCHIVE_DIR = DATA_DIR / "archive"

# Database
DATABASE_PATH = DATA_DIR / "auction_results.db"

# Scraper settings
BASE_URL = "https://www.realestate.com.au"
AUCTION_RESULTS_URL = f"{BASE_URL}/auction-results/nsw"

# Request settings - mimic a real browser
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-AU,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Cache-Control": "max-age=0",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

# Rate limiting - be respectful to the server
REQUEST_DELAY_MIN = 2  # Minimum seconds between requests
REQUEST_DELAY_MAX = 5  # Maximum seconds between requests
MAX_RETRIES = 3
RETRY_DELAY = 10  # Seconds to wait before retry

# Schedule settings
# Auction results refresh every Sunday at 5am AEDT
SCHEDULE_DAY = "sunday"
SCHEDULE_TIME = "06:00"  # Run at 6am to ensure data is available

# Export settings
CSV_DATE_FORMAT = "%Y-%m-%d"
EXPORT_FILENAME_TEMPLATE = "nsw_auction_results_{date}.csv"

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = BASE_DIR / "logs" / "scraper.log"

# NSW Regions for categorization
NSW_REGIONS = {
    "sydney_inner": ["2000", "2010", "2011", "2015", "2016", "2017", "2018", "2019", "2020", "2021"],
    "sydney_east": ["2022", "2023", "2024", "2025", "2026", "2027", "2028", "2029", "2030", "2031", "2032", "2033", "2034", "2035", "2036", "2037", "2038", "2039", "2040"],
    "sydney_inner_west": ["2041", "2042", "2043", "2044", "2045", "2046", "2047", "2048", "2049", "2050"],
    "sydney_north": ["2060", "2061", "2062", "2063", "2064", "2065", "2066", "2067", "2068", "2069", "2070", "2071", "2072", "2073", "2074", "2075", "2076", "2077", "2078", "2079", "2080"],
    "sydney_northern_beaches": ["2084", "2085", "2086", "2087", "2088", "2089", "2090", "2091", "2092", "2093", "2094", "2095", "2096", "2097", "2099", "2100", "2101", "2102", "2103", "2104", "2105", "2106", "2107", "2108"],
    "sydney_south": ["2205", "2206", "2207", "2208", "2209", "2210", "2211", "2212", "2213", "2214", "2215", "2216", "2217", "2218", "2219", "2220", "2221", "2222", "2223", "2224", "2225", "2226", "2227", "2228", "2229", "2230", "2231", "2232", "2233", "2234"],
    "sydney_west": ["2140", "2141", "2142", "2143", "2144", "2145", "2146", "2147", "2148", "2150", "2151", "2152", "2153", "2154", "2155", "2156", "2157", "2158", "2159", "2160"],
    "sydney_southwest": ["2163", "2164", "2165", "2166", "2167", "2168", "2170", "2171", "2172", "2173", "2174", "2175", "2176", "2177", "2178", "2179", "2190", "2191", "2192", "2193", "2194", "2195", "2196", "2197", "2198", "2199", "2200"],
    "central_coast": ["2250", "2251", "2256", "2257", "2258", "2259", "2260", "2261", "2262", "2263", "2264", "2265"],
    "newcastle": ["2280", "2281", "2282", "2283", "2284", "2285", "2286", "2287", "2289", "2290", "2291", "2292", "2293", "2294", "2295", "2296", "2297", "2298", "2299", "2300", "2302", "2303", "2304", "2305", "2306", "2307", "2308", "2309", "2310", "2311", "2312"],
    "wollongong": ["2500", "2502", "2505", "2506", "2508", "2515", "2516", "2517", "2518", "2519", "2520", "2525", "2526", "2527", "2528", "2529", "2530"],
    "regional_nsw": [],  # Catch-all for other postcodes
}

def get_region_for_postcode(postcode: str) -> str:
    """Get the region name for a given postcode."""
    for region, postcodes in NSW_REGIONS.items():
        if postcode in postcodes:
            return region
    return "regional_nsw"
