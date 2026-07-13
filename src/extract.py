"""
EXTRACT — pull data from the Finnhub API.

For each ticker we call two free-tier endpoints and merge the results
into one document:

  /quote          -> the numbers  (price, high, low, % change)
  /stock/profile2 -> the text     (company name, industry, exchange, country)

The text fields are what we will later embed for semantic search,
so they matter as much as the numbers.
"""

import time
from datetime import datetime, timezone

import requests

from src.config import FINNHUB_API_KEY, FINNHUB_BASE_URL, TICKERS

# Free tier allows 60 calls/minute. We make 2 calls per ticker, so a
# small pause keeps us comfortably inside the limit.
RATE_LIMIT_PAUSE = 1.1
REQUEST_TIMEOUT = 10


def _get(endpoint: str, symbol: str) -> dict:
    """Make a single GET request to Finnhub, with error handling."""
    try:
        response = requests.get(
            f"{FINNHUB_BASE_URL}/{endpoint}",
            params={"symbol": symbol, "token": FINNHUB_API_KEY},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    except requests.exceptions.HTTPError as e:
        # 403 = endpoint not available on the free tier
        # 429 = rate limited
        print(f"  ! HTTP error for {symbol} ({endpoint}): {e}")
        return {}
    except requests.exceptions.RequestException as e:
        print(f"  ! Request failed for {symbol} ({endpoint}): {e}")
        return {}
    except ValueError:
        print(f"  ! Invalid JSON returned for {symbol} ({endpoint})")
        return {}


def fetch_company(symbol: str) -> dict | None:
    """
    Fetch and merge quote + profile data for one ticker.

    Returns a single document, or None if the data is unusable.
    """
    quote = _get("quote", symbol)
    profile = _get("stock/profile2", symbol)

    # If the profile is empty the ticker is likely invalid — skip it
    # rather than storing a hollow record.
    if not profile or not profile.get("name"):
        print(f"  ! No profile data for {symbol} — skipping")
        return None

    return {
        # --- identity ---
        "ticker": symbol,
        "name": profile.get("name"),
        # --- text fields (used later for embeddings / semantic search) ---
        "industry": profile.get("finnhubIndustry"),
        "exchange": profile.get("exchange"),
        "country": profile.get("country"),
        "ipo_date": profile.get("ipo"),
        "website": profile.get("weburl"),
        "logo": profile.get("logo"),
        # --- numeric fields ---
        "currency": profile.get("currency"),
        "market_cap_millions": profile.get("marketCapitalization"),
        "shares_outstanding": profile.get("shareOutstanding"),
        "current_price": quote.get("c"),
        "change": quote.get("d"),
        "percent_change": quote.get("dp"),
        "day_high": quote.get("h"),
        "day_low": quote.get("l"),
        "day_open": quote.get("o"),
        "previous_close": quote.get("pc"),
        # --- metadata ---
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def extract_all(tickers: list[str] | None = None) -> list[dict]:
    """Fetch every ticker. Returns a list of company documents."""
    tickers = tickers or TICKERS
    companies = []

    print(f"Extracting {len(tickers)} companies from Finnhub...")

    for symbol in tickers:
        doc = fetch_company(symbol)
        if doc:
            companies.append(doc)
            price = doc.get("current_price")
            print(f"  ✓ {symbol:<6} {doc['name']:<28} ${price}")
        time.sleep(RATE_LIMIT_PAUSE)

    print(f"Extracted {len(companies)}/{len(tickers)} companies.\n")
    return companies
