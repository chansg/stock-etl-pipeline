# Stock Market ETL Pipeline

A Python data pipeline that extracts stock market data from a public API, stores it in MongoDB, serializes it to JSON, and uploads it to AWS S3.

```
Finnhub API  →  Python  →  MongoDB (EC2)  →  JSON Export  →  AWS S3
```

## Dataset

Live market data for a fixed list of well-known technology companies (AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA, NFLX, AMD, INTC, CRM, ORCL), pulled from the [Finnhub API](https://finnhub.io).

Each document combines two endpoints:

| Endpoint | Provides | Used for |
|---|---|---|
| `/quote` | price, day high/low, % change | numeric analysis |
| `/stock/profile2` | company name, industry, exchange, country | **text fields for semantic search** |

The text fields matter: they're what the upcoming semantic search / RAG layer will embed.

## Project Structure

```
.
├── main.py              # orchestrates the pipeline
├── src/
│   ├── config.py        # loads credentials from .env (nothing hard-coded)
│   ├── extract.py       # Finnhub API → Python
│   ├── load.py          # PyMongo CRUD (Create, Read, Update, Delete)
│   ├── export.py        # JSON serialization + integrity check
│   └── upload.py        # Boto3 → S3
├── tests/               # pytest suite
├── .env.example         # template — copy to .env
└── requirements.txt
```

## Setup

**1. Clone and install**

```bash
git clone <repo-url>
cd etl-pipeline
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**2. Configure credentials**

```bash
cp .env.example .env
```

Then edit `.env` with your real values:

| Variable | Where to get it |
|---|---|
| `FINNHUB_API_KEY` | Free key from [finnhub.io/register](https://finnhub.io/register) |
| `MONGO_URI` | The EC2-hosted MongoDB connection string |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Your AWS IAM credentials |
| `S3_PREFIX` | Your team's folder inside the shared bucket |

> ⚠️ **`.env` is gitignored and must never be committed.** No credentials appear anywhere in the source code — everything is loaded from environment variables.

**3. Run**

```bash
python main.py            # full pipeline
python main.py --demo     # pipeline + CRUD demonstration
pytest -v                 # run the tests
```

## What Each Stage Does

**Extract** — calls Finnhub for each ticker, merging quote + profile into a single document. Rate-limited to stay inside the free tier (60 calls/min). Skips tickers that return no data rather than storing hollow records.

**Load** — writes to MongoDB with PyMongo using **upsert** (keyed on `ticker`), so re-running the pipeline refreshes existing records instead of creating duplicates. All four CRUD operations are implemented in `src/load.py`.

**Export** — reads the data back from MongoDB and serializes it to JSON.

> **The ObjectId gotcha:** MongoDB adds an `_id` field of type `ObjectId` to every document, and `ObjectId` is not JSON-serializable — `json.dumps()` raises `TypeError`. We solve this with a custom `MongoJSONEncoder` that converts `ObjectId` and `datetime` to strings. The export is then read back and row-counted to prove **data integrity was preserved**.

**Upload** — pushes the JSON file to the S3 bucket via Boto3, under the team's prefix so it doesn't collide with other groups. Timestamped filenames mean each run is traceable.

## CRUD Operations

| Operation | Function | Description |
|---|---|---|
| **Create** | `upsert_companies()` | Bulk insert/update, keyed on ticker |
| **Read** | `find_all()`, `find_by_ticker()`, `find_by_industry()` | Retrieve all, one, or filtered |
| **Update** | `update_price()` | Targeted single-field update |
| **Delete** | `delete_by_ticker()`, `delete_all()` | Remove one or clear the collection |

Run `python main.py --demo` to see each one execute in turn.

## Error Handling

- **API:** timeouts, HTTP errors (incl. 403 free-tier limits and 429 rate limits), and malformed JSON are caught per-request — one bad ticker never kills the run.
- **MongoDB:** connection failures fail fast (5s timeout) with a message pointing at the likely cause (`.env` config or EC2 security group).
- **S3:** distinguishes missing credentials, access denied, and missing bucket, so the fix is obvious.
- **Config:** `validate_config()` fails at startup with a list of any missing variables, rather than crashing mid-pipeline.

## MongoDB on EC2 (bonus)

MongoDB is hosted on an EC2 instance so the whole team shares one database.

Setup notes:
- MongoDB configured with `bindIp: 0.0.0.0` and authentication enabled.
- Port `27017` opened in the security group **to team members' IPs only** — never `0.0.0.0/0`. An internet-exposed MongoDB is one of the most-exploited misconfigurations there is.
- Each team member puts the shared `MONGO_URI` in their own local `.env`.

## Testing (bonus)

```bash
pytest -v
```

Covers JSON serialization (including proving the `ObjectId` fix is necessary), round-trip data integrity, and the document structure the semantic-search layer will depend on. Runs without needing a live database or API key.

## Team Workflow

- Feature branches: `feat/`, `fix/`, `docs/`
- PRs into `main` rather than direct commits
- `.env` and `*.pem` are gitignored — **check `git status` before every commit**

## Next Steps

Semantic search (embeddings + vector search + RAG) over the company text fields — e.g. *"find me companies working in semiconductors"* returning results by meaning rather than exact keyword match.
