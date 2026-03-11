# Data Compass

**Data Compass** is an AI-powered data assistant that turns plain-English questions into SQL, Spark SQL, or PySpark code — and keeps track of your database schema so you don't have to paste it every time.

Ask *"Which customers placed the most orders last quarter?"* and get a ready-to-run query in seconds.

---

## Features

| | |
|---|---|
| **Multi-turn chat** | The assistant asks clarifying questions before generating a query, so you always get something correct rather than something fast |
| **Schema-aware** | Automatically retrieves relevant tables, JOIN paths, and column descriptions from your stored schema |
| **Multi-provider** | OpenAI (GPT-4o), Anthropic (Claude 3.5 / 4), Google (Gemini 2.0), Groq, OpenAI Codex, Claude Code CLI |
| **Model selection** | Pick the specific model per request — switch between GPT-4o and GPT-4o-mini in the toolbar |
| **Multiple output modes** | SQL · Spark SQL · PySpark DataFrame API · Pandas |
| **Schema / ERD viewer** | Interactive entity-relationship diagram of your entire schema |
| **Ingest Table** | Paste a pipeline SQL (`INSERT INTO … SELECT` or CTAS) and let the LLM auto-document the output table |
| **Multi-database instances** | Tag tables with a database type (Snowflake, Databricks, MS SQL, etc.) and a named instance — query each instance independently |
| **Join Path explorer** | Select any two tables and instantly see the shortest JOIN route, with join keys and cardinality annotations |
| **Derivative Tables** | See which tables were built from a source table via pipeline SQL, and which tables a derived table originates from |
| **User accounts** | Login / register with username + password, or **Sign in with Google** |
| **Session history** | Conversations are saved per user and accessible across sessions |

---

## Quick Start

### 1. Clone & install

```bash
git clone https://github.com/Mehul-Gupta-SMH/SQLCoder.git
cd SQLCoder

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

pip install -r requirements.txt
```

### 2. Set your API keys

The API key file is gitignored — create it locally:

**`APIManager/model_access_config.YAML`**

Add only the providers you have keys for:

```yaml
OPEN_AI:
  api_key: sk-...
  model_name: gpt-4o-mini
  api_template: APIManager/APIHeads/OPEN_AI.json

ANTHROPIC:
  api_key: sk-ant-...
  model_name: claude-3-5-haiku-20241022
  api_template: APIManager/APIHeads/ANTHROPIC.json

GOOGLE:
  api_key: AIza...
  model_name: gemini-2.0-flash
  api_template: APIManager/APIHeads/GOOGLE.json

GROQ:
  api_key: gsk_...
  model_name: gemma-7b-it
  api_template: APIManager/APIHeads/GROQ.json

CODEX:
  api_key: sk-...           # OpenAI key (Codex uses the OpenAI endpoint)
  model_name: o4-mini
  api_template: APIManager/APIHeads/CODEX.json

CLAUDE_CODE:
  api_key: ""               # No key needed — uses the local claude CLI
  model_name: claude-sonnet-4-5
  api_template: APIManager/APIHeads/CLAUDE_CODE.json
```

### 3. Load your schema

Before the assistant can generate queries it needs to know your database structure.

**a) Import table metadata** (one JSON file per table — see [Schema Format](#schema-format)):

```python
from MetadataManager.MetadataBuilder.importExisting.importData import importDD

imp = importDD()
imp.importData("path/to/orders.json")
imp.importData("path/to/customers.json")
```

**b) Define JOIN relationships:**

```python
from MetadataManager.MetadataStore.ManageRelations import Relations

rel = Relations(strgType="networkx")
rel.addRelation([
    ("orders", "customers",   ["orders.customer_id = customers.customer_id"]),
    ("orders", "order_items", ["orders.order_id = order_items.order_id"]),
])
```

### 4. Start the app

**Backend** (FastAPI, port 8000):
```bash
venv/Scripts/uvicorn backend.app:app --reload --port 8000
```

**Frontend** (Vite + React, port 5173):
```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**, register an account, and start querying.

---

## Providers & Models

Use the toolbar dropdowns in the Chat tab to choose a provider and model per session.

| Provider | Available models |
|---|---|
| OpenAI | GPT-4o mini · GPT-4o · GPT-4.1 · GPT-3.5 Turbo |
| OpenAI Codex | o4-mini · o3-mini · o3 · o1 |
| Anthropic | Claude 3.5 Haiku · Claude 3.5 Sonnet · Claude Sonnet 4.6 · Claude Opus 4.6 |
| Google Gemini | Gemini 2.0 Flash · Gemini 2.0 Flash Lite · Gemini 1.5 Pro · Gemini 1.5 Flash |
| GROQ | Gemma 7B · Llama 3.3 70B · Llama 3.1 8B · Mixtral 8x7B |
| Claude Code | Claude Sonnet 4.5 · Claude Sonnet 4.6 · Claude Opus 4.6 · Claude Haiku 4.5 |

> **Claude Code** requires the [Claude Code CLI](https://claude.ai/code) installed and authenticated locally:
> ```bash
> npm install -g @anthropic-ai/claude-code
> claude login
> ```

---

## Google SSO (optional)

1. Create an OAuth 2.0 client in [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Add `http://localhost:8000/auth/google/callback` as an authorised redirect URI
3. Set environment variables before starting the backend:

```bash
export GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
export GOOGLE_CLIENT_SECRET=your-client-secret
```

The **Sign in with Google** button appears on the login page automatically when these variables are set.

---

## Schema Format

One JSON file per table:

```json
{
  "tableName": "orders",
  "tableDesc": "Records every customer order placed through the platform.",
  "records": [
    {
      "TableName":     "orders",
      "ColumnName":    "order_id",
      "DataType":      "INT",
      "Constraints":   "PRIMARY KEY",
      "Desc":          "Unique identifier for each order.",
      "logic":         "",
      "type_of_logic": "",
      "base_table":    ""
    },
    {
      "TableName":     "orders",
      "ColumnName":    "customer_id",
      "DataType":      "INT",
      "Constraints":   "FOREIGN KEY",
      "Desc":          "References the customer who placed the order.",
      "logic":         "",
      "type_of_logic": "",
      "base_table":    ""
    }
  ]
}
```

> **Tip:** For pipeline / derived tables, use the **Ingest Table** tab in the UI instead. Paste an `INSERT INTO … SELECT` statement and the assistant will auto-generate the data dictionary for you.

---

## Running Tests

```bash
python -m pytest tests/ -v
```

94 tests, no API keys or ML models required — all external dependencies are mocked in `tests/conftest.py`.

---

## Project Layout

```
SQLCoder/
├── main.py                    # Core logic: generateQuery, gatherRequirements
├── SQLBuilderComponents.py    # RAG retrieval pipeline orchestration
├── backend/
│   ├── app.py                 # FastAPI application + all endpoints
│   └── auth.py                # JWT auth, user accounts, sessions (SQLite)
├── frontend/
│   └── src/
│       ├── App.jsx
│       ├── components/        # ChatInterface, SchemaERD, IngestTable, DataLineage, LoginPage
│       ├── contexts/          # AuthContext (JWT + Google SSO)
│       └── constants/         # providerLabels.js (provider & model catalog)
├── APIManager/
│   ├── AllAPICaller.py        # Multi-provider HTTP + subprocess LLM client
│   ├── PromptBuilder.py       # Prompt templates + schema formatter
│   └── APIHeads/              # Per-provider JSON request templates
├── MetadataManager/           # ChromaDB (vector store) + NetworkX (relation graph)
├── Utilities/                 # Config loader, SQLite CRUD, YAML configs
└── tests/                     # pytest suite (94 tests)
```

For architecture deep-dives and extension guides see **[DEVELOPER.md](DEVELOPER.md)**.

---

## License

MIT — see [LICENSE](LICENSE) for details.