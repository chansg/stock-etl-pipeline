"""
RAG — Retrieval-Augmented Generation.

Semantic search FINDS the right companies. RAG makes an LLM ANSWER the
question using them.

THE THREE STEPS (this is the whole idea)
----------------------------------------
1. RETRIEVE  — semantic search pulls the most relevant companies from MongoDB
2. AUGMENT   — we paste those companies into the prompt as context
3. GENERATE  — Claude reads that context and writes a natural-language answer

THE KEY POINT, AND THE THING TO SAY OUT LOUD ON THURSDAY:
Claude has NEVER seen our database. It doesn't know our stock prices. We look
the data up ourselves and hand it over in the prompt. The model's job is only
to READ and EXPLAIN what we gave it.

That's what "augmented" means — we're augmenting the model's knowledge with
our own retrieved data at question time.

WHY THIS MATTERS: it's how you get an LLM to answer questions about private,
real-time, or proprietary data it was never trained on — without retraining it.

Note on grounding: the prompt explicitly tells Claude to use ONLY the supplied
data and to say so if the answer isn't there. That's what stops it inventing
plausible-sounding numbers (hallucinating).
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from anthropic import Anthropic, APIError

from src.config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from src.search import semantic_search

# Cached answers — our safety net if the network fails during the presentation
CACHE_FILE = Path("rag_cache.json")

SYSTEM_PROMPT = """You are a financial data assistant.

You will be given data about companies retrieved from a database, followed by
a user's question.

Rules:
- Answer using ONLY the company data provided. Do not use outside knowledge.
- If the data doesn't contain the answer, say so plainly.
- Quote specific figures (prices, percentage changes) from the data.
- Be concise — 2-4 sentences. This is a spoken demo, not a report.
- Never invent numbers."""


def format_context(companies: list[dict]) -> str:
    """
    AUGMENT — turn the retrieved companies into text for the prompt.

    Note we include the NUMBERS here (price, change), even though we only
    embedded the TEXT. That's the neat part: semantic search uses the text to
    FIND the companies, then the LLM uses the numbers to ANSWER the question.
    Both halves of our dataset finally do work together.
    """
    lines = []

    for c in companies:
        lines.append(
            f"- {c['name']} ({c['ticker']})\n"
            f"    Industry: {c.get('industry')}\n"
            f"    Current price: ${c.get('current_price')}\n"
            f"    Change today: {c.get('percent_change')}%\n"
            f"    Relevance score: {c.get('score')}"
        )

    return "\n".join(lines)


def load_cache() -> dict:
    """Load previously generated answers (the offline fallback)."""
    if not CACHE_FILE.exists():
        return {}
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_to_cache(question: str, answer: str, companies: list[dict]) -> None:
    """
    Save an answer so it can be replayed if the API is unreachable.

    This is deliberate demo insurance: if the office wifi dies on Thursday,
    we can still show a real answer rather than an error message.
    """
    cache = load_cache()

    cache[question] = {
        "answer": answer,
        "sources": [c["ticker"] for c in companies],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def ask(
    question: str,
    top_k: int = 3,
    use_cache_on_failure: bool = True,
    quiet: bool = False,
) -> str | None:
    """
    Ask a question in plain English. Returns the generated answer.

    This is the full RAG loop: retrieve -> augment -> generate.

    quiet=True suppresses the plain-text output — used by demo.py, which
    renders its own formatted version of the same steps.
    """
    def say(*a, **kw):
        if not quiet:
            say(*a, **kw)

    say(f'\n{"=" * 62}')
    say(f'  QUESTION: "{question}"')
    say("=" * 62)

    # ---------------------------------------------------------- 1. RETRIEVE
    say("\n  [1/3] RETRIEVE — semantic search over MongoDB")

    companies = semantic_search(question, top_k=top_k)

    if not companies:
        say("        No companies found. Have you run --embed?")
        return None

    for c in companies:
        say(f"        • {c['ticker']:<6} {c['name']:<28} (score {c['score']:.3f})")

    # ----------------------------------------------------------- 2. AUGMENT
    say("\n  [2/3] AUGMENT — adding that data to the prompt as context")

    context = format_context(companies)
    prompt = (
        f"Here is the company data retrieved from our database:\n\n"
        f"{context}\n\n"
        f"Question: {question}"
    )

    say(f"        {len(companies)} companies -> {len(prompt)} characters of context")

    # ---------------------------------------------------------- 3. GENERATE
    say("\n  [3/3] GENERATE — Claude answers using only that context\n")

    try:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)

        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        answer = message.content[0].text

        # Cache it so we can replay this answer offline if we have to
        save_to_cache(question, answer, companies)

    except APIError as e:
        say(f"        ! Claude API error: {e}")

        # Fall back to a cached answer rather than dying in front of an audience
        if use_cache_on_failure:
            cached = load_cache().get(question)
            if cached:
                say("        (using cached answer — API unavailable)\n")
                answer = cached["answer"]
            else:
                say("        No cached answer available for this question.")
                return None
        else:
            return None

    except Exception as e:
        say(f"        ! Unexpected error: {e}")
        return None

    # --- print the answer ---
    say("  " + "-" * 60)
    for line in answer.split("\n"):
        say(f"  {line}")
    say("  " + "-" * 60)
    say(f"\n  Sources: {', '.join(c['ticker'] for c in companies)}\n")

    return answer