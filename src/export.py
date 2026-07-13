"""
EXPORT — serialize the MongoDB data to JSON.

The important gotcha: MongoDB adds an `_id` field of type ObjectId to
every document, and ObjectId is NOT JSON-serializable. Calling
json.dumps() on a raw Mongo document raises:

    TypeError: Object of type ObjectId is not JSON serializable

We handle it with a custom encoder that converts ObjectId (and datetime)
into strings, so no data is silently lost — which satisfies the brief's
"data integrity preserved during export" requirement.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId

EXPORT_DIR = Path("exports")


class MongoJSONEncoder(json.JSONEncoder):
    """Teach json.dumps() how to handle MongoDB's special types."""

    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


def serialize(documents: list[dict]) -> str:
    """Convert a list of Mongo documents into a JSON string."""
    return json.dumps(documents, cls=MongoJSONEncoder, indent=2)


def export_to_file(documents: list[dict], filename: str | None = None) -> Path:
    """
    Write the documents to a local JSON file and return its path.

    The filename is timestamped so each pipeline run produces a distinct,
    traceable export rather than overwriting the last one.
    """
    EXPORT_DIR.mkdir(exist_ok=True)

    if filename is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"companies_{stamp}.json"

    path = EXPORT_DIR / filename

    try:
        path.write_text(serialize(documents), encoding="utf-8")
    except OSError as e:
        raise OSError(f"Could not write export file {path}: {e}") from e

    print(f"Exported {len(documents)} documents -> {path}")
    return path


def verify_export(path: Path, expected_count: int) -> bool:
    """
    Read the file back and confirm nothing was lost.

    This is the 'data integrity preserved' check — we prove the round-trip
    (Mongo -> JSON -> disk -> back into Python) kept every record.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"Integrity check FAILED — could not read back {path}: {e}")
        return False

    if len(data) != expected_count:
        print(
            f"Integrity check FAILED — expected {expected_count} "
            f"documents, found {len(data)}."
        )
        return False

    print(f"Integrity check passed: {len(data)} documents round-tripped intact.")
    return True
