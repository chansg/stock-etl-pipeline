"""
Semantic Search — embed the data, then search it by meaning.

Usage:
    python embed_and_search.py --embed          # generate embeddings (run once)
    python embed_and_search.py --demo           # the presentation demo
    python embed_and_search.py "your question"  # ask anything

Run --embed first. Then --demo.
"""

import sys

from src.config import validate_config
from src.embed import embed_all, get_model
from src.search import compare

# The queries for Thursday. Each one proves keyword search can't do it.
DEMO_QUERIES = [
    "companies that make computer chips",
    "streaming and entertainment",
    "electric cars",
    "cloud software for businesses",
]


def run_demo() -> None:
    get_model()

    print("\n" + "#" * 60)
    print("#  SEMANTIC SEARCH DEMO")
    print("#  Keyword search matches LETTERS. Semantic search matches MEANING.")
    print("#" * 60)

    for query in DEMO_QUERIES:
        compare(query)


if __name__ == "__main__":
    validate_config()

    args = sys.argv[1:]

    if not args:
        print(__doc__)
        sys.exit(0)

    if "--embed" in args:
        embed_all()

    elif "--demo" in args:
        run_demo()

    else:
        # Anything else is treated as a search query
        compare(" ".join(args))
