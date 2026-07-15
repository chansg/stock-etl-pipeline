# Stock Market ETL Pipeline — Project Documentation

**Repo:** `github.com/chansg/stock-etl-pipeline`
**Team:** Chan, Mo
**Course:** Sparta Education — Data Engineering

---

## Contents

1. [What this project is](#1-what-this-project-is)
2. [The architecture](#2-the-architecture)
3. [Design decisions — and why](#3-design-decisions--and-why)
4. [The codebase, module by module](#4-the-codebase-module-by-module)
5. [The concepts, properly explained](#5-the-concepts-properly-explained)
6. [Infrastructure](#6-infrastructure)
7. [Security — an honest account](#7-security--an-honest-account)
8. [Testing](#8-testing)
9. [Bugs we hit, and what they taught us](#9-bugs-we-hit-and-what-they-taught-us)
10. [How to run everything](#10-how-to-run-everything)
11. [Glossary](#11-glossary)
12. [Questions we should be able to answer](#12-questions-we-should-be-able-to-answer)

---

## 1. What this project is

A backend data service that pulls live stock market data from a public API, stores it in a database, exports it to JSON, backs it up to cloud storage — and then lets you **search that data by meaning** and **ask it questions in plain English**.

```
Finnhub API  →  Python  →  MongoDB (EC2)  →  JSON  →  AWS S3
                              ↓
                      Semantic Search  →  RAG
```

The first four stages are the brief. The last two are ours.

**The dataset:** twelve well-known technology companies — AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA, NFLX, AMD, INTC, CRM, ORCL.

**Why those twelve?** Recognisable to everyone, no domain knowledge required, and small enough to stay comfortably inside the API's free-tier rate limit while four people test simultaneously.

---

## 2. The architecture

### The principle: one file per stage

The codebase mirrors the pipeline exactly. If you own one stage, you only need to understand one file.

```
stock-etl-pipeline/
├── main.py                # runs the ETL pipeline
├── embed_and_search.py    # generates embeddings, runs semantic search
├── ask.py                 # RAG — ask questions in plain English
├── demo.py                # the presentation CLI (rich)
│
├── src/
│   ├── config.py          # loads every credential from .env
│   ├── extract.py         # Finnhub API  → Python
│   ├── load.py            # Python       → MongoDB   (all CRUD lives here)
│   ├── export.py          # MongoDB      → JSON
│   ├── upload.py          # JSON         → AWS S3
│   ├── embed.py           # text         → vectors
│   ├── search.py          # query        → ranked results
│   └── rag.py             # retrieve → augment → generate
│
├── tests/                 # 24 tests
├── .env                   # credentials — GITIGNORED, never committed
├── .env.example           # the template: shows WHAT you need, never the values
└── requirements.txt
```

### The data flow, precisely

**1. Extract.** For each of the twelve tickers, we call *two* Finnhub endpoints and merge the results into one document:

| Endpoint | Returns | Purpose |
|---|---|---|
| `/quote` | current price, day high/low, % change, previous close | **the numbers** |
| `/stock/profile2` | company name, industry, exchange, country, IPO date | **the text** |

Both halves matter. Hold that thought — it's the spine of the whole project.

**2. Load.** Write to MongoDB using PyMongo, with an **upsert** keyed on `ticker`.

**3. Export.** Read back from MongoDB, serialize to JSON, verify nothing was lost.

**4. Upload.** Push the JSON to S3 via Boto3, under our team prefix, with a timestamped filename.

**5. Embed** *(added later).* Convert each company's text into a 384-number vector, store it back in the same MongoDB document.

**6. Search / RAG** *(added later).* Find companies by meaning; optionally hand them to an LLM to write an answer.

---

## 3. Design decisions — and why

*These are the "why did you do it that way?" answers. Know them.*

### 3.1 The dataset: company profiles, not raw prices

**The most consequential decision in the project.**

We knew semantic search was coming later in the week. Semantic search works by converting text into vectors that capture *meaning*. So the dataset needed **text worth embedding**.

Consider the two halves of a company record:

```
"NVIDIA Corp, Semiconductors, NASDAQ, US"   ← has meaning. Can be embedded.
208.61, 4925426, 2.30                        ← has no meaning. Cannot.
```

A price isn't *about* anything. `$208.61` doesn't mean semiconductors, or America, or technology. It's just a magnitude. You cannot search it by meaning because there is no meaning there to search.

Had we chosen pure price data (the obvious first instinct for "stock market API"), we'd have arrived at Wednesday with a semantic search feature that had nothing meaningful to search over.

**And here's the payoff:** in RAG, both halves finally work together — *the text finds the right companies; the numbers answer the question.*

### 3.2 Upsert, not insert

`load.py` uses `UpdateOne(..., upsert=True)` keyed on `ticker`, not `insert_many()`.

**Why:** four people share one database. With a plain insert, every test run by every person would add twelve more documents. By lunchtime the collection would be a swamp of duplicates.

With upsert, re-running the pipeline **refreshes** existing records instead of duplicating them. You can see it working in the output:

```
Loaded into MongoDB: 0 inserted, 12 updated.
```

First run: `12 inserted, 0 updated`. Every run after: `0 inserted, 12 updated`. That single line is proof the pipeline is safely repeatable — which is exactly what you'd need to schedule it daily.

### 3.3 Credentials in `.env`, never in code

The brief says "avoid hard-coding credentials." Everything — API keys, the MongoDB URI, AWS keys — loads from environment variables via `python-dotenv`, centralised in `config.py`.

`.env` is gitignored. `.env.example` is committed, showing *which* variables are needed without ever exposing *the values*.

**Why it matters:** GitHub is continuously scraped by bots hunting for leaked credentials. An exposed AWS key can be found and abused within minutes. This isn't paranoia — it's the single most common way student projects cause real damage.

### 3.4 A local embedding model, not an API

We use `sentence-transformers` with `all-MiniLM-L6-v2`, which runs **on your machine**.

**Why not an embeddings API?**
- Free — no key, no cost, no rate limits
- Downloads once (~90MB), then works **fully offline**
- Nothing external can fail mid-demo

That last point is the real reason. On presentation day, every external dependency is a way for the demo to die in front of an audience.

### 3.5 Cosine similarity in Python, not in MongoDB

**Self-hosted MongoDB has no vector search.** That's a feature of MongoDB **Atlas** (their managed cloud service), not the open-source server we installed on EC2.

So we compute similarity ourselves in `search.py`. With twelve companies this is instant — and it's arguably *better* for explaining the concept, because we can show the actual similarity scores rather than gesturing at a black-box index.

**If we scaled up:** thousands of documents would make brute-force comparison slow, and you'd want a real vector index — MongoDB Atlas Vector Search, or a dedicated vector database like Pinecone, Weaviate, or FAISS.

### 3.6 An API model for generation, with a cache

RAG uses the Anthropic API (`claude-opus-4-8` by default, configurable).

**Why an API here but a local model for embeddings?** Because generation *quality* is visible. A weak local LLM produces waffly, unconvincing answers, and the whole demo lands flat. Embeddings, by contrast, are invisible plumbing — a small local model is entirely good enough.

**The safety net:** every generated answer is cached to `rag_cache.json`. If the API is unreachable on the day, we replay the cached answer rather than showing an error. That file is gitignored (it's a generated artifact, not source).

---

## 4. The codebase, module by module

### `config.py` — the single source of credentials

Loads everything from `.env`. Also holds `validate_config()`, which **fails fast at startup** with a list of any missing variables — rather than letting the pipeline run for thirty seconds and then crash on stage four.

### `extract.py` — API → Python

- Calls `/quote` and `/stock/profile2` per ticker, merges them into one document.
- Pauses ~1.1s between tickers to stay inside the free tier (60 calls/min; we make 2 calls per company).
- **Error handling is per-request:** a timeout, HTTP error, or malformed JSON on one ticker is caught, logged, and skipped. One bad ticker never kills the run.
- If a profile comes back empty, the ticker is skipped rather than storing a hollow record.

### `load.py` — Python → MongoDB (all CRUD)

The brief requires all four CRUD operations, so each has an explicit function:

| Operation | Function | Notes |
|---|---|---|
| **Create** | `upsert_companies()` | Bulk `UpdateOne` with `upsert=True`, keyed on ticker |
| **Read** | `find_all()`, `find_by_ticker()`, `find_by_industry()` | All, one, or filtered (regex, case-insensitive) |
| **Update** | `update_price()` | Targeted `update_one` on a single field |
| **Delete** | `delete_by_ticker()`, `delete_all()` | Remove one, or clear the collection |

`get_collection()` uses a **5-second server-selection timeout**, so a bad connection fails quickly with a message pointing at the likely cause (`.env` config, or the EC2 security group) rather than hanging.

`python main.py --demo` runs each CRUD operation in turn — useful for showing them working.

### `export.py` — MongoDB → JSON

Contains the project's most instructive gotcha (see §9.1) and the integrity check:

```python
def verify_export(path, expected_count):
    """Read the file back and confirm nothing was lost."""
```

This is what satisfies the brief's *"data integrity preserved during export"*. We don't just claim it — we prove the round trip (MongoDB → JSON → disk → back into Python) preserved every record, and the pipeline **stops before upload** if it didn't.

### `upload.py` — JSON → AWS S3

Boto3, credentials from the environment. Error handling distinguishes the failure modes, because each has a different fix:

- `NoCredentialsError` → keys missing from `.env`
- `AccessDenied` → the IAM user lacks `s3:PutObject`
- `NoSuchBucket` → wrong bucket name

Filenames are timestamped (`companies_20260713_132023.json`) so each run produces a distinct, traceable file rather than overwriting the last. You get a history of every export for free.

### `embed.py` — text → vectors

The most important function in the file is `build_text()`:

```python
def build_text(company):
    parts = [
        company.get("name"),
        company.get("industry"),
        company.get("exchange"),
        company.get("country"),
    ]
    return ", ".join(p for p in parts if p)
```

**It embeds only the text. Never the numbers.** There's a test asserting prices and market caps do *not* appear in the embedded string. Including them would pollute the vectors with meaningless magnitudes.

`embed_all()` writes two new fields back into each MongoDB document:
- `embedding_text` — the string that was embedded (useful for debugging and demoing)
- `embedding` — the 384 numbers

Note how easy that was: **adding new fields to existing records with no schema migration.** That's a genuine advantage of a document database, and worth naming.

### `search.py` — query → ranked results

Two functions, deliberately side by side:

- `keyword_search()` — a normal MongoDB regex query. Exists purely to *fail*, and thereby demonstrate the problem.
- `semantic_search()` — embeds the query, scores every company by cosine similarity, returns the top matches.

`compare()` runs both and prints them together. That's the demo.

### `rag.py` — retrieve → augment → generate

The full RAG loop, plus:
- `SYSTEM_PROMPT` — the grounding instructions that stop the model inventing figures
- `format_context()` — turns retrieved companies into prompt text (**and this is where the numbers get included**)
- Answer caching to `rag_cache.json` for offline fallback

### `demo.py` — the presentation CLI

A `rich`-based front-end. **It changes no logic** — it calls exactly the same functions as `main.py`, `embed_and_search.py`, and `ask.py`, and only presents the output more clearly. Deliberately so: a pretty front-end shouldn't introduce new ways for the demo to break.

---

## 5. The concepts, properly explained

*If you understand this section, you can answer anything they ask.*

### 5.1 What an embedding actually is

A computer cannot compare "meanings" directly. So we convert text into **numbers** — specifically, a list of 384 of them, called a **vector** or **embedding**:

```
"NVIDIA Corp, Semiconductors, NASDAQ, US"  →  [0.12, -0.83, 0.44, ... ]
"Netflix Inc, Media, NASDAQ, US"           →  [0.91,  0.05, -0.22, ... ]
```

The crucial property: **text that means similar things produces similar numbers.**

The model learned this from vast amounts of text. It has seen "semiconductor" and "chip" used in the same contexts thousands of times, so it places them near each other in this numeric space.

**Why 384?** That's simply the output size this particular model was trained to produce. Think of it as 384 different "aspects of meaning" being measured. Bigger models use 768, 1536, or more — more dimensions, more nuance, more compute.

### 5.2 Cosine similarity — the maths, demystified

Once everything is a vector, "how similar are these two things?" becomes a geometry question.

**Cosine similarity** measures whether two vectors point in the same **direction**:

```
 1.0  →  identical meaning
 0.0  →  unrelated
-1.0  →  opposite
```

The formula:

```
similarity = (A · B) / (|A| × |B|)
```

The dot product of the two vectors, divided by the product of their lengths. Dividing by the lengths cancels out **magnitude**, leaving only **direction** — which is what we want, because direction is what carries the meaning.

**The intuition that actually helps:**

> Picture every company as a pin on a map. Similar companies get pinned near each other — NVIDIA and AMD are neighbours; Netflix is across town. Ask a question, and we drop a pin for the question, then return whatever's nearest.
>
> **Semantic search is a map of meaning, and you're finding the nearest pins.**

### 5.3 Reading the scores honestly

Real output from our system:

```
QUERY: "electric car companies"

  TSLA  Tesla Inc      0.606  ████████████
  NVDA  NVIDIA Corp    0.381  ███████
  AAPL  Apple Inc      0.362  ███████
```

Tesla wins decisively at **0.606**, matched purely on the word *"Automobiles"* in its profile. The model has never seen "electric" or "car" in Tesla's record — it understands they *mean* the same thing.

NVIDIA and Apple score ~0.36. **That's the model saying "vaguely tech-adjacent, but not really."**

**0.6 is a match. 0.36 is noise. The gap between them is the evidence it's working.** Don't be thrown by the runners-up looking arbitrary — that's expected. Semantic search always returns *something*; the score tells you whether to believe it.

### 5.4 RAG — Retrieval-Augmented Generation

Semantic search **finds** things. RAG makes an LLM **answer** using them.

**The three steps:**

1. **Retrieve** — semantic search pulls the relevant companies out of MongoDB.
2. **Augment** — we paste those companies into the prompt as context.
3. **Generate** — the LLM reads that context and writes an answer.

**The single most important point, and the thing to say out loud:**

> **Claude has never seen our database.** It doesn't know our stock prices. We look the data up ourselves and hand it over inside the prompt. The model's only job is to *read* and *explain* what we gave it.

That's what "augmented" means — we are augmenting the model's knowledge with our own retrieved data, at question time.

**Why this matters in the real world:** it's how you get an LLM to answer questions about **private, proprietary, or real-time data it was never trained on** — without retraining anything. Your company's internal wiki, last night's sales figures, a customer's support history. Retrieve, augment, generate.

### 5.5 Grounding — the guard against hallucination

The system prompt explicitly instructs the model:

> *Answer using ONLY the company data provided. Do not use outside knowledge. If the data doesn't contain the answer, say so plainly. Never invent numbers.*

This is called **grounding** — tethering the model's answer to supplied facts rather than letting it improvise from training data.

**We have live proof it works** (see §9.2). When a bug meant the price-change data never reached the prompt, the model said:

> *"…the data shows the change today as 'None' for all three, so I can't tell you how they're performing today."*

It **refused to invent a number.** It could trivially have produced a plausible "NVIDIA is up 2.3% today" and we'd never have known. That's the guard holding.

---

## 6. Infrastructure

### 6.1 MongoDB on EC2

One of the project's bonus objectives, and what makes this a genuine team project rather than four people each running their own local database.

| | |
|---|---|
| **Instance** | EC2 `t3.micro`, Ubuntu 24.04 LTS |
| **Region** | `eu-central-1` (Frankfurt) |
| **Database** | MongoDB 8.0 |
| **Auth user** | `etladmin`, role `root` on `admin` |
| **Database name** | `stockdb` |
| **Collection** | `companies` |

**Configuration changes made** (in `/etc/mongod.conf`):

```yaml
net:
  port: 27017
  bindIp: 0.0.0.0          # listen on all interfaces, not just localhost

security:
  authorization: enabled    # require username + password
```

⚠️ **The YAML trap:** `security:` must be flush to the left margin and uncommented, with `authorization` indented exactly two spaces beneath it. Get the indentation wrong and MongoDB refuses to start with `Unrecognized option`. YAML nesting is defined *purely by indentation* — spaces, never tabs.

**Connection string** (shared over Teams, never committed):

```
mongodb://etladmin:<password>@<ec2-public-ip>:27017/?authSource=admin
```

`authSource=admin` tells MongoDB *which database holds the user account* — a common source of confusion, since the user lives in `admin` but we're reading from `stockdb`.

### 6.2 AWS S3

- **Bucket:** `se-data-with-ai-etl-project` (shared across all teams)
- **Prefix:** our team's folder within it — this is what keeps our exports separate from other groups'

**Note the distinction**, because it caused a real error: the **bucket** is fixed and shared; the **prefix** is ours to name. Only the prefix should ever change.

S3 "folders" aren't real folders — they're just prefixes on the object key. That's why the trailing slash matters.

---

## 7. Security — an honest account

### What we did right

- **Authentication enabled** on MongoDB — username and password required.
- **No credentials in the repo.** Everything from `.env`, which is gitignored. `.env.example` documents what's needed without leaking values.
- **`.pem` keys gitignored.** SSH private keys never enter version control.
- **`git status` before every commit** as a standing habit. This isn't theoretical — it caught a private key that had been accidentally staged, *before* it was pushed.

### What we deliberately compromised

**Port 27017 is open to `0.0.0.0/0`** — the whole internet can reach the database port.

**Be able to explain this properly:**

- We needed the team to connect from home *and* from the office on presentation day. Home IPs are dynamic and the office IP was unknown, so IP allowlisting would have broken at the worst possible moment.
- **Authentication is still on.** An open port with auth is very different from an open, unauthenticated database — the latter is one of the most-exploited misconfigurations in existence.
- The data is public stock prices. The instance is disposable and gets **terminated after the presentation**.

**What we'd do in production:**

1. **IP allowlisting** — restrict the security group to known addresses.
2. **SSH tunnel** — better still: keep MongoDB bound to localhost and forward the port over SSH (`ssh -L 27017:127.0.0.1:27017 ...`). The database is then never internet-facing at all.
3. **VPC / private subnet** — the database has no public IP whatsoever; only the application server can reach it.

**Why say this out loud?** Because a knowing tradeoff and an oversight look identical from the outside — until you explain which one it was. Volunteering it first turns a weakness into evidence of judgement.

---

## 8. Testing

**24 tests, all passing.** Run with `pytest -v`.

Crucially, **they need no live database, no API key, and no downloaded model.** They test pure logic. That means they isolate *"is my Python setup right?"* from *"are my credentials right?"* — which saved a lot of debugging when onboarding teammates.

| File | Covers |
|---|---|
| `test_pipeline.py` | JSON serialization, the ObjectId fix, round-trip integrity, document structure |
| `test_search.py` | Cosine similarity maths, and that `build_text()` excludes numeric fields |
| `test_rag.py` | Context formatting, the grounding prompt, cache format |

**Two tests worth knowing individually**, because they encode design decisions rather than just checking behaviour:

**`test_plain_encoder_would_fail_without_our_fix`** — deliberately calls `json.dumps()` *without* our custom encoder and asserts it raises `TypeError`. It proves the fix is genuinely necessary, so nobody removes it thinking it's redundant.

**`test_excludes_numeric_fields`** — asserts prices do *not* appear in the embedded text. It guards the single most important design decision in the project.

---

## 9. Bugs we hit, and what they taught us

### 9.1 The ObjectId gotcha

**The problem:** MongoDB stamps every document with an `_id` field of type `ObjectId`. `ObjectId` is **not JSON-serializable**. Calling `json.dumps()` on a raw MongoDB document raises:

```
TypeError: Object of type ObjectId is not JSON serializable
```

**The fix:** a custom encoder in `export.py` that converts `ObjectId` (and `datetime`) to strings.

```python
class MongoJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)
```

**The lesson:** the boundary between two systems is where the bugs live. MongoDB's types and JSON's types don't perfectly overlap, and the seam is where things break.

### 9.2 The bug that unit tests missed — the important one

**The symptom:** RAG answers kept saying the price-change data was missing, even though MongoDB clearly showed `percent_change: 2.3043`.

**The cause:** `semantic_search()` builds a *new* dictionary from each MongoDB document, copying across only selected fields. `percent_change` wasn't in the list. So `format_context()` in `rag.py` looked for it, found nothing, and passed `None` to the model.

The data was in the database. It just never survived the journey between two modules.

**Why the tests didn't catch it:** `test_rag.py` fed `format_context()` a fixture that *did* contain `percent_change`. And `test_search.py` tested cosine similarity, not the shape of the returned dictionary. **Both modules worked perfectly in isolation. The bug lived in the seam between them.**

**The lesson — and this is a genuinely good one to have learned:**

> **Unit tests verify components. They cannot verify the contract between components.** That's what integration tests are for. All 24 tests passed while real data was being silently dropped.

### 9.3 The near-miss: a private key in git history

Running `git add .` from the wrong directory staged an SSH private key (`.pem`) and committed it locally.

**Caught at `git status`, before pushing.** The fix was to delete the local `.git` directory entirely and re-initialise cleanly in the correct folder, staging files explicitly.

**The habits that came out of it, and that we've kept:**
1. **Never `git add .` blindly.** Name the files.
2. **Always read `git status` before committing.**
3. **`.gitignore` is the first file in the repo, not the second.**

A leaked AWS or API key gets scraped by bots within minutes. This is the single most likely way a student project causes real-world damage.

### 9.4 Smaller ones worth remembering

**`ModuleNotFoundError: No module named 'src'`** — pytest run from `tests/` couldn't see the project root. Fixed with `pytest.ini`:
```ini
[pytest]
pythonpath = .
```

**`NoSuchBucket`** — the `S3_BUCKET` variable had been changed to the *repo* name instead of the bucket name. The error handling caught it precisely, which is the whole argument for distinguishing failure modes rather than catching a generic exception.

**MongoDB YAML indentation** — see §6.1. Cost us more time than it should have.

---

## 10. How to run everything

### First-time setup

```bash
git clone https://github.com/chansg/stock-etl-pipeline.git
cd stock-etl-pipeline

python -m venv venv
venv\Scripts\activate            # Windows
source venv/bin/activate         # Mac/Linux

pip install -r requirements.txt

cp .env.example .env             # then fill it in
```

**What goes in `.env`:**

| Variable | Where from |
|---|---|
| `FINNHUB_API_KEY` | **Your own** free key — finnhub.io/register |
| `MONGO_URI` | Shared over Teams |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Shared over Teams |
| `S3_BUCKET` | `se-data-with-ai-etl-project` — **don't change this** |
| `S3_PREFIX` | Our team's folder |
| `ANTHROPIC_API_KEY` | Shared over Teams |

> Everyone uses their **own** Finnhub key — it's free and takes two minutes, and it means nobody blows the shared rate limit.

### Commands

```bash
pytest -v                                  # 24 tests — needs no credentials
python main.py                             # the ETL pipeline
python main.py --demo                      # pipeline + CRUD demonstration

python embed_and_search.py --embed         # generate embeddings (run ONCE)
python embed_and_search.py --demo          # semantic search demo
python embed_and_search.py "your query"

python ask.py --demo                       # RAG demo
python ask.py "which companies make chips?"

python demo.py                             # the presentation CLI
```

### ⚠️ Run `--embed` well before you need it

The embedding model downloads (~90MB) on first use, then caches locally and works offline forever after. **Do this on a network you trust**, not five minutes before presenting.

### Git workflow

```bash
git checkout -b feat/your-thing
# ... work ...
git add <specific files>        # NOT `git add .`
git status                      # check no .env, no .pem
git commit -m "what you did"
git push -u origin feat/your-thing
```

Then open a **Pull Request** — no direct commits to `main`.

---

## 11. Glossary

| Term | Meaning |
|---|---|
| **ETL** | Extract, Transform, Load — the classic data pipeline shape |
| **Ticker** | A company's short code. `AAPL` = Apple |
| **Market cap** | A company's total value (share price × shares outstanding) |
| **Document database** | Stores flexible JSON-like documents rather than fixed table rows. MongoDB is one |
| **Collection** | MongoDB's equivalent of a table |
| **ObjectId** | MongoDB's automatic unique ID. Not JSON-serializable — hence our custom encoder |
| **Upsert** | Update if it exists, insert if it doesn't |
| **PyMongo** | The official Python driver for MongoDB |
| **Boto3** | The official AWS SDK for Python |
| **Bucket / prefix** | An S3 container / a "folder" path inside it |
| **Embedding** | Text converted into a list of numbers that captures its meaning |
| **Vector** | That list of numbers. Ours are 384 long |
| **Cosine similarity** | A measure of how closely two vectors point in the same direction. 1.0 = identical meaning |
| **Semantic search** | Search by meaning rather than by exact keyword |
| **RAG** | Retrieval-Augmented Generation — retrieve relevant data, put it in the prompt, let an LLM answer from it |
| **Grounding** | Instructing a model to answer only from supplied data, to prevent hallucination |
| **Hallucination** | An LLM confidently inventing plausible-sounding but false information |
| **Security group** | AWS's firewall — controls which IPs can reach which ports |
| **`bindIp`** | Which network interfaces a service listens on. `0.0.0.0` = all of them |

---

## 12. Questions we should be able to answer

**"Why MongoDB rather than SQL?"**
The API returns nested JSON. A document database stores that natively without flattening it into relational tables. And the flexible schema meant we could add 384-dimension embedding vectors to existing records later with **no migration** — try that in SQL.

**"Why is the database port open to the internet?"**
Deliberate demo tradeoff. Authentication is enabled, the data is public, the instance is disposable and gets terminated today. In production: IP allowlisting, or an SSH tunnel so the database is never internet-facing. *(See §7.)*

**"What happens if the API fails?"**
Per-request error handling — timeouts, HTTP errors, rate limits, malformed JSON. A failing ticker is logged and skipped; the run continues. One bad company never kills the pipeline.

**"How do you know no data was lost?"**
The export is read back from disk and row-counted against what came out of MongoDB. If a single document went missing in serialization, the pipeline **stops before upload** rather than shipping bad data.

**"What if you ran this every day?"**
The upsert makes re-running safe — it refreshes rather than duplicates. You'd schedule it (cron, or Airflow), and the timestamped S3 exports give you a historical record automatically.

**"How does semantic search actually work?"**
Each company's text becomes a 384-number vector capturing its meaning. The query becomes a vector too. We return whichever companies are numerically closest, measured by cosine similarity. *(See §5.)*

**"Doesn't the LLM just make things up?"**
It can — which is why we ground it. The system prompt instructs the model to use only the supplied data and never invent figures. We have live evidence it holds: when a bug meant the price data never reached the prompt, it said the data was missing rather than fabricating a number. *(See §9.2.)*

**"Why compute similarity in Python instead of the database?"**
Self-hosted MongoDB has no vector search — that's a MongoDB Atlas feature. With twelve documents, brute-force comparison is instant. At scale you'd want a proper vector index.

**"How did you split the work?"**
*(Answer honestly. Mention feature branches and pull requests — collaborative Git was an explicit bonus objective.)*

**"What would you do differently?"**
Integration tests across module boundaries — all 24 unit tests passed while real data was silently dropped between two modules. Restrict the database port properly. And use a managed vector store if we scaled beyond a handful of documents.

---

*Last updated: July 2026*
