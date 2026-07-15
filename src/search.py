"""
SEARCH — find companies by MEANING, not by matching letters.

THE COMPARISON WE'RE DEMONSTRATING
----------------------------------
    Query: "companies that make computer chips"

    keyword_search()  -> []                    (nothing contains "chip")
    semantic_search() -> [NVDA, AMD, INTC]     (they MEAN chips)

HOW SEMANTIC SEARCH WORKS HERE
------------------------------
1. Every company already has an embedding — 384 numbers describing its meaning
   (see embed.py).
2. We embed the QUESTION using the exact same model, giving 384 numbers.
3. We measure how "close" the question's numbers are to each company's numbers.
4. Closest = most similar in meaning. Return the top few.

The closeness measure is COSINE SIMILARITY. Don't be put off by the name —
it just measures whether two vectors point in the same direction:

    1.0  = identical meaning
    0.0  = unrelated
   -1.0  = opposite

Picture each company as a pin on a map. Similar companies get pinned near
each other. We drop a pin for the question and return the nearest pins.

Note: self-hosted MongoDB has no built-in vector search (that's a MongoDB
Atlas feature), so we do the maths in Python. With 12 companies this is
instant — and it means we can actually SHOW the similarity scores, which is
better for explaining it than a black-box index.
"""

import numpy as np

from src.embed import embed_text
from src.load import get_collection


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    How similar are two vectors? Returns roughly -1 to 1 (higher = closer).

    The maths: the dot product of the two vectors, divided by the product
    of their lengths. That cancels out magnitude and leaves only DIRECTION —
    which is what we care about, since direction is what encodes meaning.
    """
    vec_a = np.array(a)
    vec_b = np.array(b)

    denominator = np.linalg.norm(vec_a) * np.linalg.norm(vec_b)
    if denominator == 0:
        return 0.0

    return float(np.dot(vec_a, vec_b) / denominator)


# --------------------------------------------------------------- SEMANTIC

def semantic_search(query: str, top_k: int = 3) -> list[dict]:
    """
    Find the companies whose MEANING is closest to the query.

    Returns the top_k matches, each with a similarity score.
    """
    collection = get_collection()

    # Only companies that have been embedded can be searched
    companies = list(collection.find({"embedding": {"$exists": True}}))

    if not companies:
        print("No embeddings found — run `python embed_and_search.py --embed` first.")
        return []

    # Step 1: turn the QUESTION into a vector, using the same model
    query_vector = embed_text(query)

    # Step 2: score every company against the question
    scored = []
    for company in companies:
        score = cosine_similarity(query_vector, company["embedding"])
        scored.append(
            {
                "ticker": company["ticker"],
                "name": company["name"],
                "industry": company.get("industry"),
                "current_price": company.get("current_price"),
                "percent_change": company.get("percent_change"),
                "change": company.get("change"),
                "day_high": company.get("day_high"),
                "day_low": company.get("day_low"),
                "market_cap_millions": company.get("market_cap_millions"),
                "matched_text": company.get("embedding_text"),
                "score": round(score, 4),
            }
        )

    # Step 3: sort by score, highest (closest in meaning) first
    scored.sort(key=lambda c: c["score"], reverse=True)

    return scored[:top_k]


# ---------------------------------------------------------------- KEYWORD

def keyword_search(query: str) -> list[dict]:
    """
    Traditional search — looks for the literal WORDS.

    This exists purely to show what semantic search improves on. It's a
    normal MongoDB regex query across the text fields. If the exact word
    isn't present, it finds nothing — however obvious the answer is to a human.
    """
    collection = get_collection()

    results = list(
        collection.find(
            {
                "$or": [
                    {"name": {"$regex": query, "$options": "i"}},
                    {"industry": {"$regex": query, "$options": "i"}},
                ]
            }
        )
    )

    return [
        {
            "ticker": r["ticker"],
            "name": r["name"],
            "industry": r.get("industry"),
        }
        for r in results
    ]


# ------------------------------------------------------------ THE COMPARISON

def compare(query: str, top_k: int = 3) -> None:
    """
    Run both searches side by side and print the result.

    This is the presentation demo.
    """
    print("\n" + "=" * 60)
    print(f'  QUERY: "{query}"')
    print("=" * 60)

    # --- keyword ---
    print("\n  KEYWORD SEARCH (matches letters)")
    keyword_results = keyword_search(query)

    if keyword_results:
        for r in keyword_results:
            print(f"    • {r['ticker']:<6} {r['name']}")
    else:
        print("    ✗ No results — none of the companies contain that exact text.")

    # --- semantic ---
    print("\n  SEMANTIC SEARCH (matches meaning)")
    semantic_results = semantic_search(query, top_k=top_k)

    for r in semantic_results:
        bar = "█" * int(r["score"] * 20)  # visual similarity bar
        print(
            f"    ✓ {r['ticker']:<6} {r['name']:<28} "
            f"{r['score']:.3f} {bar}"
        )
        print(f"        matched on: \"{r['matched_text']}\"")

    print()
