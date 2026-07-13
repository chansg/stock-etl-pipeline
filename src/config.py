"""
Central configuration.

Loads all settings from environment variables (.env file) so that
NO credentials are ever hard-coded in the source. This satisfies the
brief's "avoid hard-coding credentials" constraint.
"""

import os
import sys

from dotenv import load_dotenv

# Read .env into the environment
load_dotenv()

# --- Finnhub ---
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
FINNHUB_BASE_URL = "https://finnhub.io/api/v1"

# --- MongoDB ---
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "stockdb")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "companies")

# --- AWS S3 ---
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "eu-central-1")
S3_BUCKET = os.getenv("S3_BUCKET", "se-data-with-ai-etl-project")
S3_PREFIX = os.getenv("S3_PREFIX", "")

# --- The companies we track ---
# A fixed list of well-known tech tickers keeps the dataset predictable
# and recognisable, and stays within the free tier's rate limit.
TICKERS = [
    "AAPL",   # Apple
    "MSFT",   # Microsoft
    "GOOGL",  # Alphabet
    "AMZN",   # Amazon
    "NVDA",   # NVIDIA
    "META",   # Meta
    "TSLA",   # Tesla
    "NFLX",   # Netflix
    "AMD",    # AMD
    "INTC",   # Intel
    "CRM",    # Salesforce
    "ORCL",   # Oracle
]


def validate_config() -> None:
    """
    Fail fast with a clear message if anything required is missing,
    rather than crashing deep inside the pipeline.
    """
    required = {
        "FINNHUB_API_KEY": FINNHUB_API_KEY,
        "MONGO_URI": MONGO_URI,
        "AWS_ACCESS_KEY_ID": AWS_ACCESS_KEY_ID,
        "AWS_SECRET_ACCESS_KEY": AWS_SECRET_ACCESS_KEY,
    }

    missing = [name for name, value in required.items() if not value]

    if missing:
        print("ERROR: Missing required environment variables:")
        for name in missing:
            print(f"  - {name}")
        print("\nCopy .env.example to .env and fill in the values.")
        sys.exit(1)
