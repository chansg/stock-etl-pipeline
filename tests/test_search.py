"""
Tests for the semantic search layer.

These test the LOGIC (cosine similarity, text building) without needing the
embedding model downloaded or MongoDB running — so they're fast and run
anywhere.

Run with:  pytest -v
"""

import pytest

from src.embed import build_text
from src.search import cosine_similarity


class TestCosineSimilarity:
    """The maths that decides which companies are 'closest' in meaning."""

    def test_identical_vectors_score_one(self):
        assert cosine_similarity([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)

    def test_magnitude_does_not_matter_only_direction(self):
        """[1,2,3] and [2,4,6] point the same way — same meaning, different 'loudness'."""
        assert cosine_similarity([1, 2, 3], [2, 4, 6]) == pytest.approx(1.0)

    def test_unrelated_vectors_score_zero(self):
        assert cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)

    def test_opposite_vectors_score_minus_one(self):
        assert cosine_similarity([1, 2, 3], [-1, -2, -3]) == pytest.approx(-1.0)

    def test_zero_vector_does_not_crash(self):
        """Guard against divide-by-zero rather than blowing up mid-search."""
        assert cosine_similarity([0, 0, 0], [1, 2, 3]) == 0.0

    def test_more_similar_scores_higher(self):
        """The property the whole search depends on."""
        query = [1, 1, 0]
        close = [1, 1, 0.1]
        far = [0, 0, 1]

        assert cosine_similarity(query, close) > cosine_similarity(query, far)


class TestBuildText:
    """What we embed matters more than how we embed it."""

    def test_combines_the_text_fields(self):
        company = {
            "name": "NVIDIA Corp",
            "industry": "Semiconductors",
            "exchange": "NASDAQ",
            "country": "US",
        }

        text = build_text(company)

        assert "NVIDIA Corp" in text
        assert "Semiconductors" in text

    def test_excludes_numeric_fields(self):
        """
        Numbers carry no semantic meaning — '$315.32' isn't ABOUT anything —
        so they must not pollute the embedding.
        """
        company = {
            "name": "Apple Inc",
            "industry": "Technology",
            "current_price": 315.32,
            "market_cap_millions": 4631217,
        }

        text = build_text(company)

        assert "315.32" not in text
        assert "4631217" not in text

    def test_skips_missing_fields_gracefully(self):
        company = {"name": "Apple Inc", "industry": None, "country": "US"}

        text = build_text(company)

        assert "Apple Inc" in text
        assert "US" in text
        assert "None" not in text
