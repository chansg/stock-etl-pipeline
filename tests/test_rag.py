"""
Tests for the RAG layer.

These test the logic that we control — how we build the context and handle the
cache — WITHOUT calling the Claude API (no key needed, no cost, no network).

Run with:  pytest -v
"""

import json

import pytest

from src.rag import SYSTEM_PROMPT, format_context


@pytest.fixture
def retrieved_companies():
    """What semantic_search() hands to the RAG layer."""
    return [
        {
            "ticker": "NVDA",
            "name": "NVIDIA Corp",
            "industry": "Semiconductors",
            "current_price": 208.61,
            "percent_change": -1.11,
            "score": 0.612,
        },
        {
            "ticker": "AMD",
            "name": "Advanced Micro Devices Inc",
            "industry": "Semiconductors",
            "current_price": 533.37,
            "percent_change": 2.04,
            "score": 0.598,
        },
    ]


class TestFormatContext:
    """AUGMENT — the retrieved data must reach the prompt intact."""

    def test_includes_company_names_and_tickers(self, retrieved_companies):
        context = format_context(retrieved_companies)

        assert "NVIDIA Corp" in context
        assert "NVDA" in context
        assert "Advanced Micro Devices Inc" in context

    def test_includes_the_numbers(self, retrieved_companies):
        """
        The KEY design point: we embed only TEXT, but we pass the NUMBERS to
        the LLM. Semantic search uses text to FIND; the LLM uses numbers to
        ANSWER. If the prices don't make it into the context, RAG can't work.
        """
        context = format_context(retrieved_companies)

        assert "208.61" in context
        assert "533.37" in context
        assert "-1.11" in context

    def test_includes_industry(self, retrieved_companies):
        context = format_context(retrieved_companies)
        assert "Semiconductors" in context

    def test_handles_missing_fields_without_crashing(self):
        """A company with gaps shouldn't blow up the whole answer."""
        sparse = [{"ticker": "XYZ", "name": "Unknown Corp"}]

        context = format_context(sparse)

        assert "Unknown Corp" in context  # no KeyError raised


class TestSystemPrompt:
    """The prompt is what stops Claude inventing numbers."""

    def test_instructs_model_to_use_only_provided_data(self):
        assert "ONLY" in SYSTEM_PROMPT

    def test_forbids_inventing_numbers(self):
        """Grounding — the guard against hallucination."""
        assert "invent" in SYSTEM_PROMPT.lower()

    def test_tells_model_to_admit_when_it_cannot_answer(self):
        assert "say so" in SYSTEM_PROMPT.lower()


class TestCacheFormat:
    """The offline fallback must be valid, replayable JSON."""

    def test_cache_entry_is_json_serializable(self):
        entry = {
            "some question": {
                "answer": "NVIDIA is trading at $208.61, down 1.11% today.",
                "sources": ["NVDA", "AMD"],
                "generated_at": "2026-07-13T14:00:00+00:00",
            }
        }

        round_tripped = json.loads(json.dumps(entry))

        assert round_tripped["some question"]["sources"] == ["NVDA", "AMD"]
