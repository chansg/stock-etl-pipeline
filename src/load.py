"""
LOAD — store the data in MongoDB using PyMongo.

The brief requires all four CRUD operations, so each one has an explicit
function here:

  CREATE  -> upsert_companies()
  READ    -> find_all() / find_by_ticker() / find_by_industry()
  UPDATE  -> update_price()
  DELETE  -> delete_by_ticker()
"""

from pymongo import MongoClient, UpdateOne
from pymongo.errors import ConnectionFailure, OperationFailure

from src.config import MONGO_COLLECTION, MONGO_DB, MONGO_URI


def get_collection():
    """
    Connect to MongoDB and return the collection.

    Uses a short server-selection timeout so a bad connection fails
    quickly with a clear message, rather than hanging.
    """
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")  # forces an actual connection check
        return client[MONGO_DB][MONGO_COLLECTION]

    except ConnectionFailure as e:
        raise ConnectionFailure(
            f"Could not connect to MongoDB: {e}\n"
            "Check MONGO_URI in .env, and that the EC2 security group "
            "allows your IP on port 27017."
        ) from e


# ---------------------------------------------------------------- CREATE

def upsert_companies(companies: list[dict]) -> int:
    """
    Insert companies into MongoDB.

    Uses upsert (update-or-insert) keyed on `ticker`, so re-running the
    pipeline refreshes existing records instead of creating duplicates.
    This makes the pipeline safely repeatable.
    """
    if not companies:
        print("No companies to load.")
        return 0

    collection = get_collection()

    try:
        operations = [
            UpdateOne(
                {"ticker": doc["ticker"]},   # match on ticker
                {"$set": doc},               # overwrite with fresh data
                upsert=True,                 # insert if not present
            )
            for doc in companies
        ]

        result = collection.bulk_write(operations)
        total = result.upserted_count + result.modified_count

        print(
            f"Loaded into MongoDB: "
            f"{result.upserted_count} inserted, "
            f"{result.modified_count} updated."
        )
        return total

    except OperationFailure as e:
        print(f"MongoDB write failed: {e}")
        return 0


# ------------------------------------------------------------------ READ

def find_all() -> list[dict]:
    """Return every company document."""
    return list(get_collection().find())


def find_by_ticker(ticker: str) -> dict | None:
    """Return a single company by its ticker symbol."""
    return get_collection().find_one({"ticker": ticker.upper()})


def find_by_industry(industry: str) -> list[dict]:
    """Return all companies in a given industry (case-insensitive)."""
    return list(
        get_collection().find(
            {"industry": {"$regex": industry, "$options": "i"}}
        )
    )


def count_documents() -> int:
    """How many companies are currently stored."""
    return get_collection().count_documents({})


# ---------------------------------------------------------------- UPDATE

def update_price(ticker: str, new_price: float) -> bool:
    """
    Update a single company's current price.

    Demonstrates a targeted UPDATE operation (as opposed to the bulk
    upsert used during loading).
    """
    result = get_collection().update_one(
        {"ticker": ticker.upper()},
        {"$set": {"current_price": new_price}},
    )

    if result.matched_count == 0:
        print(f"No company found with ticker {ticker}")
        return False

    print(f"Updated {ticker}: current_price -> {new_price}")
    return True


# ---------------------------------------------------------------- DELETE

def delete_by_ticker(ticker: str) -> bool:
    """Delete a single company by ticker."""
    result = get_collection().delete_one({"ticker": ticker.upper()})

    if result.deleted_count == 0:
        print(f"No company found with ticker {ticker}")
        return False

    print(f"Deleted {ticker} from MongoDB.")
    return True


def delete_all() -> int:
    """Clear the collection. Useful when resetting between test runs."""
    result = get_collection().delete_many({})
    print(f"Deleted {result.deleted_count} documents.")
    return result.deleted_count
