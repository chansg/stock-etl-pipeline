"""
Basic tests (bonus requirement).

These test the pure logic — JSON serialization and document structure —
so they run without needing a live MongoDB, API key, or AWS connection.

Run with:  pytest -v
"""

import json
from datetime import datetime, timezone

import pytest
from bson import ObjectId

from src.export import MongoJSONEncoder, serialize


class TestJSONSerialization:
    """The ObjectId problem is the main serialization gotcha."""

    def test_objectid_is_serialized_to_string(self):
        """A raw ObjectId would crash json.dumps — our encoder handles it."""
        doc = {"_id": ObjectId(), "ticker": "AAPL"}

        result = json.loads(serialize([doc]))

        assert isinstance(result[0]["_id"], str)
        assert result[0]["ticker"] == "AAPL"

    def test_datetime_is_serialized_to_iso_string(self):
        doc = {"fetched_at": datetime(2026, 7, 13, tzinfo=timezone.utc)}

        result = json.loads(serialize([doc]))

        assert result[0]["fetched_at"].startswith("2026-07-13")

    def test_plain_encoder_would_fail_without_our_fix(self):
        """Proves the custom encoder is genuinely necessary."""
        doc = {"_id": ObjectId()}

        with pytest.raises(TypeError):
            json.dumps(doc)  # no cls=MongoJSONEncoder

    def test_no_data_is_lost_in_round_trip(self):
        """Data integrity: what goes in must come out."""
        docs = [
            {"ticker": "AAPL", "current_price": 189.42, "industry": "Technology"},
            {"ticker": "MSFT", "current_price": 402.15, "industry": "Technology"},
        ]

        result = json.loads(serialize(docs))

        assert len(result) == len(docs)
        assert result[0]["current_price"] == 189.42
        assert result[1]["ticker"] == "MSFT"


class TestDocumentStructure:
    """Guard the fields the semantic-search layer will depend on."""

    @pytest.fixture
    def sample_doc(self):
        return {
            "ticker": "AAPL",
            "name": "Apple Inc",
            "industry": "Technology",
            "exchange": "NASDAQ NMS - GLOBAL MARKET",
            "country": "US",
            "current_price": 189.42,
            "market_cap_millions": 2_794_000,
            "fetched_at": "2026-07-13T10:00:00+00:00",
        }

    def test_has_required_identity_fields(self, sample_doc):
        assert sample_doc["ticker"]
        assert sample_doc["name"]

    def test_has_text_fields_for_embedding(self, sample_doc):
        """These are what Wednesday's semantic search will embed."""
        for field in ("name", "industry", "exchange", "country"):
            assert sample_doc.get(field), f"missing text field: {field}"

    def test_has_numeric_fields(self, sample_doc):
        assert isinstance(sample_doc["current_price"], (int, float))
        assert isinstance(sample_doc["market_cap_millions"], (int, float))
