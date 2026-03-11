# Developer Guide

Concise reference for contributors and developers extending Poly-QL.

---

## Dev Environment Setup

```bash
# 1. Clone & create virtualenv
git clone https://github.com/Mehul-Gupta-SMH/SQLCoder.git
cd SQLCoder
python -m venv venv && venv\Scripts\activate   # Windows
# source venv/bin/activate                      # macOS/Linux

# 2. Install all dependencies
pip install -r requirements.txt

# 3. Frontend
cd frontend && npm install && cd ..

# 4. Run tests (no API keys needed)
python -m pytest tests/ -v
```

**Start services:**
```bash
# Terminal 1 — backend (auto-reloads on file save)
venv/Scripts/uvicorn backend.app:app --reload --port 8000

# Terminal 2 — frontend (HMR)
cd frontend && npm run dev
```

---

## Architecture

```
Browser (React)
    │  HTTP (Vite proxy → localhost:8000)
    ▼
FastAPI  backend/app.py
    │  Depends(get_current_user)  ← JWT via backend/auth.py
    ▼
main.py
    ├── gatherRequirements()   Phase 1: agentic loop — asks clarifying Qs
    │       └── CallLLMApi     up to 5 get_schema tool calls
    └── generateQuery()        Phase 2: builds prompt, calls LLM, validates output
            ├── SQLBuilderSupport.getBuildComponents()   RAG retrieval
            ├── PromptBuilder.build()                    prompt assembly
            └── CallLLMApi.CallService()                 LLM call
```

### RAG retrieval pipeline (`SQLBuilderComponents.py`)

1. **Embed** query → ChromaDB semantic search → top-N candidate tables
2. **Graph traversal** → NetworkX shortest paths → JOIN bridge tables
3. **Cross-encoder reranker** → score and filter tables
4. **BM25 column scoring** → keep only relevant columns (PK/FK always kept)
5. **Format** → `PromptBuilder.format_schema()` → markdown schema block

### LLM response envelope

All LLM responses are expected (and normalised) to this JSON shape:

```json
{ "type": "sql|code|clarify", "content": "..." }
```

`_parse_llm_json()` in `main.py` handles plain-text fallbacks gracefully.

---

## Key Files

| File | Role |
|---|---|
| `main.py` | `generateQuery`, `gatherRequirements`, `generate_pipeline_dict`, validators |
| `backend/app.py` | FastAPI routes, Pydantic models, auth/session endpoints |
| `backend/auth.py` | PyJWT tokens, PBKDF2 passwords, Google OAuth2, SQLite user/session CRUD |
| `APIManager/AllAPICaller.py` | HTTP + subprocess LLM client; `model` override param |
| `APIManager/PromptBuilder.py` | Loads `.txt` prompt templates, injects variables, formats schema |
| `APIManager/model_access_config.YAML` | API keys + default model per provider (**gitignored**) |
| `APIManager/APIHeads/*.json` | Per-provider request templates (`<<api_key>>`, `<<model>>` placeholders) |
| `SQLBuilderComponents.py` | Orchestrates the retrieval pipeline |
| `Utilities/config.yaml` | Top-level config; paths to all sub-configs |
| `frontend/src/constants/providerLabels.js` | `PROVIDER_LABELS`, `PROVIDER_MODELS`, `defaultModel()` |
| `frontend/src/utils/api.js` | `apiFetch` — injects JWT header, fires `auth:logout` on 401 |
| `frontend/src/contexts/AuthContext.jsx` | Auth state, `login()`, `logout()`, Google SSO hash handling |
| `tests/conftest.py` | Mocks heavy ML deps; overrides `get_current_user` for test client |

---

## Adding a New LLM Provider

1. **Create a request template** `APIManager/APIHeads/MY_PROVIDER.json`:

```json
{
  "endpoint": "https://api.myprovider.com/v1/chat",
  "headers": { "Authorization": "Bearer <<api_key>>", "Content-Type": "application/json" },
  "payload": { "model": "<<model>>", "messages": [{"role": "user", "content": "<<input_text>>"}] }
}
```

2. **Add config** to `APIManager/model_access_config.YAML`:

```yaml
MY_PROVIDER:
  api_key: my-api-key
  model_name: my-default-model
  api_template: APIManager/APIHeads/MY_PROVIDER.json
```

3. **Wire up content injection and response parsing** in `AllAPICaller.CallService()`:

```python
# Content injection (after the existing open_ai / google blocks)
if self.llmService.lower() == "my_provider":
    self.api_temp_dict["payload"]["messages"][0]["content"] = prompt

# Response parsing
if self.llmService.lower() == "my_provider":
    return data["choices"][0]["message"]["content"]
```

4. **Register the provider** in `main.py`:

```python
_VALID_PROVIDERS = {"open_ai", "anthropic", "google", "groq", "codex", "claude_code", "my_provider"}
```

5. **Add frontend label and models** in `frontend/src/constants/providerLabels.js`:

```js
export const PROVIDER_LABELS = { ..., my_provider: 'My Provider' }
export const PROVIDER_MODELS = {
  ...,
  my_provider: [
    { value: 'my-default-model', label: 'My Default' },
    { value: 'my-fast-model',    label: 'My Fast' },
  ],
}
```

---

## Adding a New Prompt

1. Create `APIManager/Prompts/my_prompt.txt` with `<<VARIABLE>>` placeholders:

```
You are a data analyst.

Schema:
<<SCHEMA>>

Question: <<QUESTION>>

Return only SQL.
```

2. Register it in `PromptBuilder.__init__` (or the prompt map dict) — check `PromptBuilder.py` for the exact pattern used.

3. Call it:

```python
prompt = PromptBuilder('my_prompt').build({'SCHEMA': schema_str, 'QUESTION': user_q})
```

---

## Auth System

- **Tokens:** PyJWT HS256, 7-day expiry, signed with `JWT_SECRET` env var (random secret if unset — tokens invalidated on restart)
- **Passwords:** PBKDF2-SHA256, 260 000 iterations, random 16-byte salt
- **Storage:** SQLite at `backend/data/app.db` — tables `users` and `sessions`
- **FastAPI dependency:** `get_current_user` extracts and verifies the Bearer token; injected into every protected endpoint
- **Google SSO flow:**
  `GET /auth/google` → redirect to Google → `GET /auth/google/callback?code=...` → verify ID token → upsert user → issue JWT → redirect to `FRONTEND_URL/#sso_token=<jwt>`
  `AuthContext.jsx` reads the hash on mount and stores the token

**Environment variables for Google SSO:**

| Variable | Default |
|---|---|
| `GOOGLE_CLIENT_ID` | _(required)_ |
| `GOOGLE_CLIENT_SECRET` | _(required)_ |
| `GOOGLE_REDIRECT_URI` | `http://localhost:8000/auth/google/callback` |
| `FRONTEND_URL` | `http://localhost:5173` |
| `JWT_SECRET` | random (tokens expire on restart) |

---

## API Endpoints

### Public
| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/register` | Create account `{username, password}` |
| `POST` | `/auth/login` | Get JWT `{username, password}` |
| `GET` | `/auth/google` | Start Google SSO flow |
| `GET` | `/auth/google/callback` | Google OAuth2 callback |
| `GET` | `/auth/google/enabled` | `{enabled: bool}` — whether Google SSO is configured |
| `GET` | `/api/providers` | List available providers |
| `GET` | `/api/providers/balance` | Per-provider balance / availability |
| `GET` | `/api/schema` | Full schema (tables + relations) |
| `GET` | `/api/lineage/{table}` | Lineage subgraph for a table |

### Protected (Bearer token required)
| Method | Path | Description |
|---|---|---|
| `GET` | `/auth/me` | Current user info |
| `POST` | `/api/chat` | Two-phase chat: gather requirements → generate query |
| `POST` | `/api/query` | Direct query generation (no requirement gathering) |
| `POST` | `/api/execute` | Run SQL against a live database |
| `POST` | `/api/ingest/preview` | Analyse pipeline SQL, return data dictionary preview |
| `POST` | `/api/ingest/commit` | Save reviewed table metadata to schema stores |
| `GET` | `/api/sessions` | List user's saved sessions |
| `POST` | `/api/sessions` | Upsert a session |
| `DELETE` | `/api/sessions/{id}` | Delete a session |

---

## Testing

```bash
python -m pytest tests/ -v          # all 94 tests
python -m pytest tests/test_api.py  # API / integration tests only
python -m pytest tests/test_filters.py -v  # retrieval pipeline unit tests
```

**How tests work without ML models:**
- `tests/conftest.py` stubs out `torch`, `chromadb`, `sentence_transformers`, `FlagEmbedding` before any imports
- `get_current_user` FastAPI dependency is overridden to return a fake user, so protected endpoints work without a JWT
- CI uses `requirements-ci.txt` (no heavy packages)

**Adding tests:** follow the existing pattern — mock `CallLLMApi` or `generateQuery` at import location (`backend.app.generateQuery`), not the source module.

---

## Frontend Overview

```
frontend/src/
├── App.jsx                    # Tabs: Query | Schema/ERD | Ingest Table | Data Lineage
├── contexts/
│   └── AuthContext.jsx        # user, token, login(), logout(), ssoError
├── utils/
│   └── api.js                 # apiFetch — auto-injects Authorization header
├── constants/
│   └── providerLabels.js      # PROVIDER_LABELS, PROVIDER_MODELS, defaultModel()
└── components/
    ├── LoginPage.jsx           # Sign-in / register form + Google SSO button
    ├── ChatInterface.jsx       # Main chat UI, session pane, toolbar
    ├── ChatMessage.jsx         # Message bubbles, RunQueryPanel
    ├── SchemaERD.jsx           # React Flow ERD diagram
    ├── IngestTable.jsx         # Pipeline SQL ingestion wizard
    └── DataLineage.jsx         # Lineage graph viewer
```

**State flow for a chat turn:**

```
handleSend()
  → apiFetch POST /api/chat  { messages, provider, query_type, model }
  → gatherRequirements()     Phase 1 — may return { type: "clarify" }
  → generateQuery()          Phase 2 — returns { type: "sql", sql: "..." }
  → pushMsg()                adds message bubble to state
  → useEffect[messages]      auto-saves session to server
```

---

## Git Workflow

- `master` — stable, deployed branch
- `Claude/Playground/Dev` — active development branch
- Never push directly to `master`; open a PR from the dev branch
- CI runs `python -m pytest tests/` on pushes to `master`
