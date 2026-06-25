# AI Agent — Avtomatik Yuk Tashish Matching Tizimi

An AI agent that automatically matches auto-generated cargo transport **requests**
to the best available **vehicle**, using **Google Gemini** as the decision-making
brain, and logs every recommendation with its latency for monitoring/analytics.

## What it does

1. A scheduler auto-generates transport requests at a random **1–10 minute** interval
   (**≥400/day** — see [the 400/day note](#why-batches) below).
2. For each new request the agent:
   - reads the pickup location (`yuk_ortish_joyi`),
   - **prefilters** the fleet down to the nearest candidate vehicles (deterministic:
     Haversine distance for GPS, region-adjacency for named locations),
   - asks **Gemini** to pick and justify the single best vehicle,
   - writes the recommendation + timestamps + **latency** to `agent_takliflari`.
3. `/analytics` exposes latency and throughput stats for later accuracy analysis.

> **Why a deterministic prefilter + LLM?** The prefilter keeps the Gemini prompt
> small/cheap and *grounds* the model so it can only choose among real, nearby
> vehicles (no hallucinated plates). Gemini does the actual ranking/justification —
> it is the agent's brain, not a hardcoded sort. If the API key is missing or the
> call fails, the pipeline **falls back** to the nearest candidate so it never stalls.

## Tech stack

FastAPI · SQLAlchemy 2.0 · Alembic (migrations) · APScheduler · Google Gemini
(`google-genai`) · PostgreSQL (or SQLite for a zero-setup local run).

## Database (3 migrations, spec columns kept verbatim)

| Table | Spec columns | Additive (extras) |
|-------|--------------|-------------------|
| `zaproslar` | `id, yuk_ortish_joyi, yuk_tushirish_joyi, yuklash_sanasi, created_at, updated_at` | `ortish_lat, ortish_lng, location_type` |
| `malumotlar` | `id, mashina_raqami, joriy_lokatsiya, created_at, updated_at` | `lat, lng, location_type` |
| `agent_takliflari` | `id, zapros_id (FK), mashina_id (FK), zapros_yaratilgan_vaqti, agent_taklif_bergan_vaqti, created_at, updated_at` | `latency_ms, score, reasoning` |

## Location: two modes

- **named** — region/city/address text; matched by region + a small adjacency graph
  (`app/geo.py`), tiebroken by centroid distance.
- **gps** — latitude/longitude; matched by Haversine distance.

`LOCATION_MODE=mixed` (default) makes the generator randomly produce both kinds.

## Quick start

Requires **Python 3.11+**.

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then set GEMINI_API_KEY (optional — fallback works without it)
```

### Option A — Everything in Docker (one command)

Brings up Postgres **and** the app (runs migrations on boot, seeds the fleet, starts the generator):

```bash
cp .env.example .env          # set GEMINI_API_KEY
docker compose up --build     # API on http://localhost:8000
```

### Option B — App locally, Postgres in Docker

```bash
docker compose up -d db                    # just Postgres on :5432
# .env DATABASE_URL already points at it
alembic upgrade head                       # create the 3 tables
uvicorn app.main:app --reload              # auto-seeds fleet + starts the generator
```

### Option C — SQLite (no DB server)

```bash
export DATABASE_URL="sqlite:///./dev.db"
alembic upgrade head
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs for the interactive API.

## API (English routes; DB columns stay Uzbek)

| Method | Route | Purpose |
|--------|-------|---------|
| POST | `/requests` | Create a request (triggers the agent in the background) |
| GET  | `/requests` | List recent requests |
| POST | `/vehicles` | Register a vehicle |
| GET  | `/vehicles` | List vehicles |
| GET  | `/suggestions` | Agent recommendations (with latency + reasoning) |
| POST | `/agent/run/{request_id}` | Manually (re-)run the agent for one request |
| GET  | `/analytics` | Latency (avg/p95), match rate, gemini vs fallback, 24h counts |
| GET  | `/health` | Status + whether Gemini is configured |

## Configuration (`.env`)

| Var | Default | Meaning |
|-----|---------|---------|
| `DATABASE_URL` | `sqlite:///./dev.db` | DB connection |
| `GEMINI_API_KEY` | _(empty)_ | Gemini key; empty → deterministic fallback |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Model id |
| `GEMINI_THINKING_BUDGET` | `0` | `0` disables thinking (~2× faster); raise for harder ranking |
| `GEMINI_MAX_RETRIES` | `2` | Transient-error retries before fallback |
| `MATCH_CONCURRENCY` | `4` | Threadpool size for matching a batch concurrently |
| `LOCATION_MODE` | `mixed` | `named` \| `gps` \| `mixed` |
| `CANDIDATE_TOP_N` | `10` | Candidates sent to Gemini |
| `MAX_RADIUS_KM` | `600` | GPS candidate cutoff |
| `GENERATOR_BATCH_SIZE` | `2` | Requests per tick |
| `GENERATOR_MIN/MAX_MINUTES` | `1` / `10` | Tick interval bounds |
| `ENABLE_SCHEDULER` | `true` | Toggle the generator |
| `AUTO_SEED` | `true` | Seed fleet on startup if empty |

## <a name="why-batches"></a>Design note: how "1–10 min interval" meets "≥400/day"

A uniform 1–10 min interval averages 5.5 min → ~262 ticks/day, which is **below**
the required 400. The generator therefore emits a small **batch per tick**
(`GENERATOR_BATCH_SIZE`, default 2): ~262 × 2 ≈ **524 requests/day**, comfortably
above 400, while preserving the requested 1–10 min cadence.

## Performance

The agent is latency-sensitive (it should recommend the moment a request arrives):

- **Thinking disabled** (`GEMINI_THINKING_BUDGET=0`) on `gemini-2.5-flash` → ~3.0s → **~1.5s** per call
  with no quality loss for this pick-nearest task (measured live).
- **Concurrent batch matching** — each request in a batch is matched in its own DB session via a
  threadpool, so a batch of 4 completes in **~1.7s** instead of ~6s sequential.
- **Retry with exponential backoff** around the Gemini call; on exhaustion it falls back to the
  nearest deterministic candidate so the system never stalls.

## Tests

```bash
pytest        # 14 tests: prefilter (Haversine/region) + pipeline + Gemini retry + API integration
```

All tests run offline (Gemini is mocked).

## Out of scope (future work)

- Accuracy/feedback metrics beyond latency (spec lists analytics as a *future* capability).
- Vehicle reservation/locking; multi-vehicle suggestions per request.
- PostGIS (plain lat/lng + Haversine is sufficient at this scale).
