"""
RAG — ask the database questions in plain English.

Usage:
    python ask.py --demo                      # the presentation demo
    python ask.py "which companies make chips and how are they doing?"

Requires: embeddings generated first (`python embed_and_search.py --embed`)
          and ANTHROPIC_API_KEY set in .env
"""

import sys

from src.config import ANTHROPIC_API_KEY, validate_config
from src.embed import get_model
from src.rag import ask

# Questions for Thursday. Each needs BOTH halves of our data:
# the TEXT to find the right companies, and the NUMBERS to answer.
DEMO_QUESTIONS = [
    "Which companies make computer chips, and how are they performing today?",
    "Are any of the streaming or entertainment companies down today?",
    "Tell me about the electric vehicle company in the dataset.",
]


def run_demo() -> None:
    get_model()  # warm up the embedding model first, for clean output

    print("\n" + "#" * 62)
    print("#  RAG DEMO — Retrieval-Augmented Generation")
    print("#")
    print("#  Claude has NEVER seen our database.")
    print("#  We retrieve the data ourselves and hand it over in the prompt.")
    print("#" * 62)

    for question in DEMO_QUESTIONS:
        ask(question)


if __name__ == "__main__":
    validate_config()

    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY is not set in your .env file.")
        print("Get a key from https://console.anthropic.com")
        sys.exit(1)

    args = sys.argv[1:]

    if not args:
        print(__doc__)
        sys.exit(0)

    if "--demo" in args:
        run_demo()
    else:
        get_model()
        ask(" ".join(args))
