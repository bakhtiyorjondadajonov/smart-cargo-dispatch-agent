# Architecture

AI agent that matches auto-generated cargo transport **requests** to the best
available **vehicle**, using **Google Gemini** as the decision-making brain and
logging every recommendation with its latency for monitoring.

- **Stack:** FastAPI · SQLAlchemy 2.0 · Alembic · APScheduler · `google-genai` · PostgreSQL/SQLite
- **Core idea:** a cheap deterministic prefilter narrows the fleet → Gemini ranks/justifies among
  *real* candidates → result + latency is logged. If Gemini is unavailable, it falls back to the
  nearest candidate so the system never stalls.

---

## 1. Component architecture

```mermaid
flowchart TD
    subgraph APP["FastAPI app (app/main.py)"]
        LIFESPAN["lifespan:<br/>seed fleet + start scheduler"]
    end

    subgraph ENTRY["Two ways a request enters"]
        ROUTERS["HTTP Routers (app/routers)<br/>/requests /vehicles<br/>/suggestions /agent/run/:id /analytics"]
        SCHED["Scheduler (app/scheduler.py)<br/>APScheduler tick every 1–10 min<br/>emits a BATCH, matches concurrently"]
    end

    SEED["Auto-seed (app/seed.py)<br/>60 vehicles · named + GPS"]

    subgraph PIPE["Agent pipeline (app/agent/pipeline.py) — run_matching()"]
        P1["1. load request"]
        P2["2. select_candidates() — deterministic prefilter"]
        P3["3. rank_with_gemini() — LLM brain"]
        P4["4. write suggestion + latency"]
        P1 --> P2 --> P3 --> P4
    end

    CAND["app/agent/candidates.py<br/>+ app/geo.py<br/>(Haversine / region graph)"]
    GEM["app/agent/gemini_agent.py<br/>google-genai SDK"]

    DB[("Database<br/>SQLAlchemy + Alembic<br/>Postgres / SQLite")]

    LIFESPAN --> SEED
    LIFESPAN --> SCHED
    SEED --> DB
    ROUTERS --> PIPE
    SCHED --> PIPE
    P2 -. uses .-> CAND
    P3 -. uses .-> GEM
    GEM -. calls .-> GEMINI[["Google Gemini API"]]
    PIPE --> DB
    ROUTERS --> DB
```

---

## 2. Matching flow (per request)

```mermaid
flowchart TD
    START(["New request<br/>scheduler tick OR POST /requests"]) --> INS["Insert into zaproslar<br/>stamp created_at"]
    INS --> S1

    subgraph S1["STEP 1 — Candidate prefilter (deterministic, no LLM)"]
        direction TB
        MODE{location_type?}
        MODE -->|gps| HAV["Haversine distance to every vehicle<br/>→ nearest N within radius"]
        MODE -->|named| REG["Region-adjacency hops<br/>+ centroid distance tiebreak → top N"]
    end

    S1 --> S2

    subgraph S2["STEP 2 — Gemini ranking (the brain)"]
        direction TB
        PROMPT["Build prompt:<br/>persona + request + candidate list"]
        CALL["generate_content()<br/>structured output · thinking_budget=0 · retry+backoff"]
        PROMPT --> CALL
    end

    S2 --> OK{Gemini OK?}
    OK -->|yes| VERDICT["best_mashina_id + score + reasoning<br/>(validated: id must be in candidate set)"]
    OK -->|no key / API error / bad id| FALLBACK["FALLBACK:<br/>nearest deterministic candidate"]

    VERDICT --> S3
    FALLBACK --> S3

    subgraph S3["STEP 3 — Log recommendation"]
        direction TB
        LOG["Insert agent_takliflari:<br/>zapros_id, mashina_id,<br/>zapros_yaratilgan_vaqti, agent_taklif_bergan_vaqti,<br/>latency_ms = suggested − created, score, reasoning"]
    end

    S3 --> DONE(["Done — suggestion available via /suggestions, /analytics"])
```

---

## 3. Request lifecycle (sequence)

```mermaid
sequenceDiagram
    participant Sch as Scheduler / Client
    participant API as FastAPI
    participant Pipe as pipeline.run_matching
    participant Cand as candidates (geo)
    participant Gem as gemini_agent
    participant LLM as Gemini API
    participant DB as Database

    Sch->>API: create request (batch tick or POST /requests)
    API->>DB: INSERT zaproslar (created_at)
    API->>Pipe: run_matching(zapros_id)
    Pipe->>DB: load request
    Pipe->>Cand: select_candidates(top_n, radius)
    Cand->>DB: read malumotlar (fleet)
    Cand-->>Pipe: top-N nearest candidates
    Pipe->>Gem: rank_with_gemini(request, candidates)
    Gem->>LLM: generate_content (structured JSON, retry/backoff)
    alt success
        LLM-->>Gem: {best_mashina_id, score, reasoning}
        Gem-->>Pipe: verdict (validated in-set)
    else failure / no key
        Gem-->>Pipe: GeminiUnavailable → nearest candidate
    end
    Pipe->>DB: INSERT agent_takliflari (+ latency_ms)
    Pipe-->>API: suggestion
```

---

## 4. Data model

```mermaid
erDiagram
    zaproslar ||--o{ agent_takliflari : "zapros_id (FK)"
    malumotlar ||--o{ agent_takliflari : "mashina_id (FK)"

    zaproslar {
        int id PK
        string yuk_ortish_joyi "pickup (spec)"
        string yuk_tushirish_joyi "dropoff (spec)"
        date yuklash_sanasi "load date (spec)"
        float ortish_lat "additive: GPS"
        float ortish_lng "additive: GPS"
        string location_type "additive: named|gps"
        datetime created_at
        datetime updated_at
    }

    malumotlar {
        int id PK
        string mashina_raqami "plate, unique (spec)"
        string joriy_lokatsiya "current location (spec)"
        float lat "additive: GPS"
        float lng "additive: GPS"
        string location_type "additive: named|gps"
        datetime created_at
        datetime updated_at
    }

    agent_takliflari {
        int id PK
        int zapros_id FK
        int mashina_id FK
        datetime zapros_yaratilgan_vaqti "request created (spec)"
        datetime agent_taklif_bergan_vaqti "agent suggested (spec)"
        int latency_ms "additive: monitoring"
        float score "additive: gemini confidence"
        string reasoning "additive: gemini justification"
        datetime created_at
        datetime updated_at
    }
```

> Table & column names are kept verbatim in Uzbek to match the assignment spec.
> Columns marked **additive** are extras enabling GPS matching and latency/quality analytics.

---

## 5. Directory map → responsibility

```
app/
├── main.py             FastAPI app; lifespan seeds fleet + starts scheduler
├── config.py           pydantic-settings (DB, Gemini key/model/thinking, concurrency…)
├── database.py         SQLAlchemy engine, SessionLocal, get_db dependency
├── models.py           3 ORM models (the tables above)
├── schemas.py          Pydantic I/O — English JSON ↔ Uzbek columns via aliases
├── geo.py              Uzbekistan regions, centroids, adjacency graph, Haversine
├── seed.py             sample fleet generator (idempotent)
├── scheduler.py        APScheduler: batch generator + concurrent matching
├── agent/
│   ├── candidates.py   STEP 1 — deterministic prefilter
│   ├── gemini_agent.py STEP 2 — Gemini ranking + retry + fallback signal
│   └── pipeline.py     orchestrates STEP 1→2→3 (run_matching)
└── routers/
    ├── zaproslar.py    POST/GET /requests  (POST → background match)
    ├── malumotlar.py   POST/GET /vehicles
    ├── takliflari.py   GET /suggestions, POST /agent/run/{id}
    └── analytics.py    GET /analytics (latency avg/p95, match rate, gemini vs fallback)

alembic/versions/       001 zaproslar · 002 malumotlar · 003 agent_takliflari
tests/                  candidates · pipeline · gemini retry · API integration (14 tests)
Dockerfile · docker-compose.yml   one-command app + Postgres
```

---

## 6. Key design decisions

1. **Deterministic prefilter + LLM ranking (hybrid).** Cheap geo math narrows the fleet to ~10
   grounded candidates; Gemini only *ranks and justifies* among real vehicles. This keeps the
   prompt small/cheap, prevents hallucinated vehicles, and still makes the LLM the decision-maker.

2. **Resilience + observability.** Every request always produces a logged suggestion with a
   measured `latency_ms` — via Gemini or the deterministic fallback — so the system never stalls
   and the "agent efficiency monitoring" requirement is satisfied with real data.

3. **Spec fidelity with a clean API.** DB tables/columns stay in Uzbek exactly as specified;
   the HTTP API is English, mapped through Pydantic aliases.

4. **Throughput vs. cadence.** A uniform 1–10 min interval averages 5.5 min → ~262 requests/day,
   *below* the required 400. The generator emits a small **batch per tick** (default 2) →
   ~524/day, satisfying ≥400/day while keeping the 1–10 min cadence. Batches are matched
   **concurrently** (one DB session per match) so wall-clock ≈ a single Gemini call.

5. **Latency-aware Gemini usage.** `thinking_budget=0` on `gemini-2.5-flash` (~3.0s → ~1.5s/call,
   measured) plus retry-with-backoff before falling back.
```
