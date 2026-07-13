"""
Stock Market ETL Pipeline
=========================

    Finnhub API --> Python --> MongoDB --> JSON Export --> AWS S3

Run:
    python main.py           # full pipeline
    python main.py --demo    # full pipeline + CRUD demonstration
"""

import sys

from src import export, extract, load, upload
from src.config import validate_config


def run_pipeline() -> bool:
    """Execute the four pipeline stages in order."""

    print("=" * 55)
    print("  STOCK MARKET ETL PIPELINE")
    print("=" * 55)

    # 1. EXTRACT — pull from the API
    print("\n[1/4] EXTRACT")
    companies = extract.extract_all()
    if not companies:
        print("Nothing extracted — aborting.")
        return False

    # 2. LOAD — store in MongoDB
    print("[2/4] LOAD")
    try:
        load.upsert_companies(companies)
        print(f"MongoDB now holds {load.count_documents()} companies.\n")
    except Exception as e:
        print(f"Load failed: {e}")
        return False

    # 3. EXPORT — read back from Mongo and serialize to JSON
    print("[3/4] EXPORT")
    try:
        stored = load.find_all()
        export_path = export.export_to_file(stored)

        if not export.verify_export(export_path, len(stored)):
            print("Export integrity check failed — aborting before upload.")
            return False
        print()
    except Exception as e:
        print(f"Export failed: {e}")
        return False

    # 4. UPLOAD — push the JSON to S3
    print("[4/4] UPLOAD")
    s3_key = upload.upload_file(export_path)
    if not s3_key:
        print("Upload failed.")
        return False

    print("\n" + "=" * 55)
    print("  PIPELINE COMPLETE")
    print("=" * 55)
    return True


def demo_crud() -> None:
    """
    Demonstrate all four CRUD operations explicitly.

    Useful for the presentation — it walks through Create, Read, Update
    and Delete one at a time so each is clearly visible.
    """
    print("\n" + "=" * 55)
    print("  CRUD DEMONSTRATION")
    print("=" * 55)

    # READ — all
    print("\n[READ] Total companies stored:")
    print(f"  {load.count_documents()}")

    # READ — one
    print("\n[READ] Find by ticker (AAPL):")
    apple = load.find_by_ticker("AAPL")
    if apple:
        print(f"  {apple['name']} — ${apple['current_price']} ({apple['industry']})")

    # READ — filtered
    print("\n[READ] Find by industry (Technology):")
    tech = load.find_by_industry("Technology")
    for company in tech[:5]:
        print(f"  {company['ticker']:<6} {company['name']}")

    # UPDATE
    print("\n[UPDATE] Set TSLA price to 999.99:")
    load.update_price("TSLA", 999.99)
    tesla = load.find_by_ticker("TSLA")
    if tesla:
        print(f"  Verified: {tesla['ticker']} is now ${tesla['current_price']}")

    # DELETE
    print("\n[DELETE] Remove INTC:")
    load.delete_by_ticker("INTC")
    print(f"  Companies remaining: {load.count_documents()}")

    print("\n(Re-run the pipeline to restore the original data.)")


if __name__ == "__main__":
    validate_config()

    success = run_pipeline()

    if success and "--demo" in sys.argv:
        demo_crud()

    sys.exit(0 if success else 1)
