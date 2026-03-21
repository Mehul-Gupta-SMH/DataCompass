# Poly-QL — System Architecture

High-level view of all major components and their relationships.

```mermaid
graph TB
    User["👤 User\n(Browser)"]

    subgraph Frontend ["Frontend — Vite + React (:5173)"]
        FE_Chat["ChatInterface\n+ SessionPane + ChatMessage"]
        FE_ERD["SchemaERD\n+ TableNode"]
        FE_Ingest["IngestTable\n(2-step wizard)"]
        FE_Lineage["JoinPathExplorer\n+ Derivative Tables"]
    end

    subgraph Backend ["Backend — FastAPI (:8000)"]
        BE_Chat["POST /api/chat\nPOST /api/chat/stream"]
        BE_Schema["GET /api/schema\nGET /api/joinpath\nGET /api/derivatives"]
        BE_Ingest["POST /api/ingest/preview\nPOST /api/ingest/commit"]
        BE_Execute["POST /api/execute"]
        BE_Auth["Auth: JWT + Google SSO"]
        BE_Metrics["GET /metrics (Prometheus)"]
        BE_Balance["GET /api/providers/balance"]
    end

    subgraph Logic ["Business Logic"]
        Main["main.py\ngatherRequirements()\ngenerateQuery()\ngenerateQueryStream()"]
        Ingestion["backend/ingestion.py\nparse_pipeline()\ngenerate_pipeline_dict()"]
        RAG["SQLBuilderComponents.py\nChromaDB → Kuzu → SQLite"]
    end

    subgraph LLM ["LLM Providers"]
        OAI["OpenAI\nGPT-4o / GPT-4.1"]
        Anthropic["Anthropic\nClaude 3.5 / 4"]
        Google["Google\nGemini 2.0 Flash"]
        Groq["GROQ\nLlama / Mixtral"]
        Codex["OpenAI Codex\no4-mini / o3"]
        CC["Claude Code CLI\n(subprocess)"]
    end

    subgraph Storage ["Storage Layer"]
        SQLite[("SQLite\ntableMetadata.db\n+ auth.db")]
        ChromaDB[("ChromaDB\nvector embeddings")]
        Kuzu[("Kuzu\nembedded graph DB\nJOIN relationships")]
        OutcomeStore[("Outcome Store\noutcomes.jsonl\n+ outcomes.db")]
    end

    User -->|"HTTP"| Frontend
    Frontend -->|"REST / SSE"| Backend
    Backend --> Logic
    Logic -->|"HTTP API / subprocess"| LLM
    Logic --> SQLite
    Logic --> ChromaDB
    Logic --> Kuzu
    BE_Execute --> OutcomeStore
```

## Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| `main.py` | Two-agent orchestration: requirement gathering loop + query generation |
| `SQLBuilderComponents.py` | RAG retrieval pipeline: ChromaDB search → Kuzu JOIN paths → SQLite column fetch |
| `backend/ingestion.py` | Pipeline SQL parsing + LLM-assisted data dictionary generation |
| `backend/balance.py` | Concurrent credit/availability checks for all LLM providers |
| `backend/auth.py` | JWT authentication, user accounts, Google SSO |
| `backend/metrics.py` | In-memory Prometheus counters; `GET /metrics` endpoint |
| `backend/logging_config.py` | JSON-structured log formatter; called once at FastAPI lifespan startup |
| `validation/outcome_store.py` | Appends execution outcomes to `outcomes.jsonl` + SQLite index |
