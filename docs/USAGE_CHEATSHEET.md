# Application Commands — Cheatsheet

*Every command to run the app, by what you want to do.*

---

## Run the whole thing

```bash
python demo.py
```

The menu-driven presentation CLI. Pick pipeline / semantic search / RAG / ask-your-own from the menu. **This is the one for Thursday.**

Jump straight to a section:

```bash
python demo.py --pipeline     # ETL pipeline only
python demo.py --search       # semantic search only
python demo.py --rag          # RAG only
python demo.py --ask          # live "ask your own question" mode
```

---

## The ETL pipeline

```bash
python main.py                # extract → load → export → upload
python main.py --demo         # the above, then a CRUD walkthrough
```

---

## Semantic search

```bash
python embed_and_search.py --embed        # generate embeddings — RUN ONCE
python embed_and_search.py --demo         # the 4-query demo
python embed_and_search.py "electric cars"    # your own query
```

Examples that land well:
```bash
python embed_and_search.py "companies that make computer chips"
python embed_and_search.py "streaming services"
python embed_and_search.py "cloud software"
```

---

## RAG (ask in plain English)

```bash
python ask.py --demo                                   # the demo questions
python ask.py "which companies make chips and how are they doing?"
python ask.py "is any streaming company down today?"
python ask.py "tell me about the EV company"
```

---

## Tests

```bash
pytest -v                     # all 24
pytest tests/test_search.py -v    # just semantic search
pytest tests/test_rag.py -v       # just RAG
```

---

## Inspect the data (mongosh)

```bash
mongosh "mongodb://etladmin:<pw>@<EC2_IP>:27017/?authSource=admin"
```

```javascript
use stockdb
db.companies.countDocuments({})                          // total companies
db.companies.countDocuments({ embedding: {$exists:1} })  // how many embedded (want 12)
db.companies.findOne()                                   // one full document
db.companies.find({ industry: "Semiconductors" })        // filter by industry
```

---

## The typical order, start to finish

```bash
python main.py                          # 1. pull data → Mongo → S3
python embed_and_search.py --embed      # 2. add embeddings (once)
python ask.py --demo                    # 3. warm the RAG cache
python demo.py                          # 4. present
```

---

## Two things that must be done ONCE, ahead of time

```bash
python embed_and_search.py --embed      # downloads the model (~90MB), then offline forever
python ask.py --demo                    # populates rag_cache.json (offline fallback)
```

Do both on a network you trust — **not** five minutes before presenting.

---

**Pipeline:** `Finnhub → Python → MongoDB (EC2) → JSON → S3 → Semantic Search → RAG`
