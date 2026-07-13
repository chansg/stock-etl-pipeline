"""
EMBED — turn each company's text into a vector.

THE IDEA
--------
A computer can't compare "meanings" directly. So we convert text into a
list of numbers (a "vector" / "embedding") where similar meanings produce
similar numbers.

    "NVIDIA Corp, Semiconductors"  ->  [0.12, -0.83, 0.44, ... ]  (384 numbers)
    "Netflix Inc, Media"           ->  [0.91,  0.05, -0.22, ... ]

Companies that do similar things end up with vectors that are numerically
close together. That's the whole trick — meaning becomes geometry.

We use a LOCAL model (sentence-transformers), so:
  - it's free, with no API key and no rate limits
  - it works offline once downloaded (~90MB, first run only)
  - nothing can rate-limit us mid-demo

The model turns text into 384 numbers. Why 384? That's just the size this
particular model was trained to output — think of it as 384 different
"aspects of meaning" it measures.
"""

from sentence_transformers import SentenceTransformer

from src.load import get_collection

# all-MiniLM-L6-v2: small, fast, and good enough for short text like ours.
MODEL_NAME = "all-MiniLM-L6-v2"

# Loading the model takes a few seconds, so we do it once and reuse it.
_model = None


def get_model() -> SentenceTransformer:
    """Load the embedding model (once), then reuse it."""
    global _model
    if _model is None:
        print(f"Loading embedding model ({MODEL_NAME})...")
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def build_text(company: dict) -> str:
    """
    Combine a company's text fields into one string to embed.

    THIS IS THE MOST IMPORTANT FUNCTION IN THE FILE.

    We only embed the TEXT — name, industry, exchange, country. We do NOT
    embed the price or market cap, because numbers have no semantic meaning:
    "$315.32" isn't *about* anything, so it can't be searched by meaning.

    This is exactly why we chose company profiles over raw price data.
    """
    parts = [
        company.get("name", ""),
        company.get("industry", ""),
        company.get("exchange", ""),
        company.get("country", ""),
    ]
    # Drop any empty fields, join the rest
    return ", ".join(p for p in parts if p)


def embed_text(text: str) -> list[float]:
    """Convert a single piece of text into a vector."""
    vector = get_model().encode(text)
    return vector.tolist()  # numpy array -> plain list, so MongoDB can store it


def embed_all() -> int:
    """
    Generate an embedding for every company and save it back to MongoDB.

    Each document gains two new fields:
      embedding_text -> the text we embedded (useful for debugging/demoing)
      embedding      -> the 384 numbers

    This is why a document database is handy: we're adding new fields to
    existing records with no schema migration.
    """
    collection = get_collection()
    companies = list(collection.find())

    if not companies:
        print("No companies in MongoDB — run the pipeline first.")
        return 0

    print(f"Embedding {len(companies)} companies...")

    updated = 0
    for company in companies:
        text = build_text(company)
        vector = embed_text(text)

        collection.update_one(
            {"_id": company["_id"]},
            {"$set": {"embedding_text": text, "embedding": vector}},
        )

        updated += 1
        print(f"  ✓ {company['ticker']:<6} \"{text}\"")

    print(f"\nEmbedded {updated} companies ({len(vector)} dimensions each).\n")
    return updated
