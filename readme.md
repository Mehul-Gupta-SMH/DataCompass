# SQLCoder — RAG-Powered Text-to-SQL Generator

SQLCoder converts natural language questions into SQL queries by automatically retrieving the relevant database schema context and passing it to an LLM. It uses a multi-stage retrieval pipeline — vector similarity search, cross-encoder reranking, graph-based JOIN discovery, and BM25 column filtering — so the LLM receives a clean, focused schema rather than a full database dump.

---

## How It Works

```
Natural language question
        │
        ▼
1. Embed query → ChromaDB semantic search → top-N relevant tables
        │
        ▼
2. NetworkX graph traversal → shortest JOIN paths between tables
   (surfaces intermediate bridge tables automatically)
        │
        ▼
3. Cross-encoder reranker → filter & rank tables by relevance score
        │
        ▼
4. BM25 column scoring → keep only columns relevant to the query
   (PRIMARY KEY / FOREIGN KEY columns always retained for JOINs)
        │
        ▼
5. Format as structured markdown schema (PromptBuilder)
        │
        ▼
6. LLM call (OpenAI / Anthropic / Google / Groq) → SQL query
```

---

## Project Structure

```
SQLCoder/
├── main.py                          # Entry point
├── SQLBuilderComponents.py          # Orchestrates the retrieval pipeline
│
├── APIManager/
│   ├── AllAPICaller.py              # Multi-provider LLM client (OpenAI, Anthropic, Google, Groq)
│   ├── PromptBuilder.py             # Prompt templates + schema formatter
│   ├── Prompts/                     # .txt prompt templates
│   └── APIHeads/                    # Per-provider JSON request templates
│
├── MetadataManager/
│   ├── MetadataStore/
│   │   ├── RAGPipeline.py           # Embedding, retrieval, and reranker scoring
│   │   ├── ManageRelations.py       # Table relationship graph interface
│   │   ├── relationdb/
│   │   │   └── networkxDB.py        # NetworkX DiGraph — stores JOIN relationships
│   │   └── vdb/
│   │       ├── base.py              # BaseVectorStore ABC
│   │       └── Chroma.py            # ChromaDB implementation
│   └── MetadataBuilder/
│       └── importExisting/
│           ├── importData.py        # Ingest table data dictionaries (JSON → SQLite + ChromaDB)
│           └── importRelations.py   # Ingest table JOIN relationships → graph
│
├── Utilities/
│   ├── base_utils.py                # Config loader, accessDB (SQLite CRUD), cachefunc
│   ├── store_interface.py           # BaseMetadataStore ABC
│   ├── config.yaml                  # Top-level config (points to sub-configs)
│   ├── database_config.YAML         # SQLite storage paths
│   ├── retrieval_config.YAML        # VDB, models, scoring thresholds, relation DB paths
│   └── model_config.YAML            # LLM provider config path
│
└── tests/
    ├── test_prompt_builder.py        # PromptBuilder unit tests
    ├── test_filters.py               # Retrieval filter unit tests
    └── test_base_utils.py            # accessDB and cachefunc unit tests
```

---

## Setup

### Prerequisites

- Python 3.9+
- A supported LLM provider API key (OpenAI, Anthropic, Google, or Groq)
- Local HuggingFace model files for embedding and reranking (see Configuration)

### Install dependencies

```bash
git clone https://github.com/Mehul-Gupta-SMH/SQLCoder.git
cd SQLCoder
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

### Configure API keys

Create `APIManager/model_access_config.YAML` — this file is gitignored and never committed:

```yaml
OPEN_AI:
  api_key: sk-...
  model_name: gpt-4o
  api_template: APIManager/APIHeads/OPEN_AI.json

ANTHROPIC:
  api_key: sk-ant-...
  model_name: claude-sonnet-4-6
  api_template: APIManager/APIHeads/ANTHROPIC.json

GROQ:
  api_key: gsk_...
  model_name: llama3-70b-8192
  api_template: APIManager/APIHeads/GROQ.json

GOOGLE:
  api_key: AIza...
  model_name: gemini-pro
  api_template: APIManager/APIHeads/GOOGLE.json
```

### Configure paths

Update `Utilities/retrieval_config.YAML` with your local paths:

```yaml
models_repo:
  path: '/path/to/huggingface/models'   # parent dir containing model folders below

indexing:
  model: 'mixedbread-ai/mxbai-embed-large-v1'

scoring:
  crossencoder: 'mixedbread-ai/mxbai-rerank-base-v1'
  reranker_threshold: 0.0      # raise to filter more aggressively
  column_score_threshold: 0.0  # raise to keep fewer columns per table

vectordb:
  name: 'chroma'
  path: 'MetadataManager/MetadataStore/MetadataStorage/vdb'

relationdb:
  path: 'MetadataManager/MetadataStore/MetadataStorage/relationsdb/Relations.pickle'
  viz:  'MetadataManager/MetadataStore/MetadataStorage/relationsdb/DataMap.html'

tableMDdb:
  info_type: "table"
  dbName: "tableMetadata"
  tableDescName: "tableDesc"
  tableColName: "tableColMetadata"
```

Update `Utilities/database_config.YAML`:
```yaml
database:
  base_path: 'MetadataManager/MetadataStore/MetadataStorage/db'
```

---

## Ingesting Your Schema

Before generating queries, load your database schema into the metadata stores.

### 1. Prepare data dictionary JSON files

One JSON file per table:

```json
{
  "tableName": "orders",
  "tableDesc": "Records of all customer orders placed through the platform.",
  "records": [
    {
      "TableName": "orders",
      "ColumnName": "order_id",
      "DataType": "INT",
      "Constraints": "PRIMARY KEY",
      "logic": "order_id",
      "type_of_logic": "direct",
      "base_table": "orders",
      "Desc": "Unique identifier for each order."
    },
    {
      "TableName": "orders",
      "ColumnName": "customer_id",
      "DataType": "INT",
      "Constraints": "FOREIGN KEY",
      "logic": "customer_id",
      "type_of_logic": "direct",
      "base_table": "orders",
      "Desc": "References the customer who placed the order."
    }
  ]
}
```

### 2. Import table metadata

```python
from MetadataManager.MetadataBuilder.importExisting.importData import importDD

importer = importDD()
importer.importData("path/to/orders.json")
importer.importData("path/to/customers.json")
# repeat for all tables
```

### 3. Import table relationships

```python
from MetadataManager.MetadataStore.ManageRelations import Relations

rel = Relations(strgType="networkx")
rel.addRelation([
    ("orders", "customers", ["orders.customer_id = customers.customer_id"]),
    ("orders", "order_details", ["orders.order_id = order_details.order_id"]),
])
```

---

## Generating a Query

```python
from main import generateQuery

sql = generateQuery(
    userQuery="Which products have the highest sales revenue over the past year?",
    LLMservice="open_ai"   # or "anthropic", "google", "groq"
)
print(sql)
```

---

## Configuration Reference

### Scoring thresholds (`retrieval_config.YAML`)

| Key | Default | Effect |
|-----|---------|--------|
| `reranker_threshold` | `0.0` | Tables with a cross-encoder score below this are dropped. Raise to filter more aggressively. |
| `column_score_threshold` | `0.0` | Columns with a BM25 score below this are dropped (key columns always kept). Raise to reduce prompt size. |

### Prompt types (`PromptBuilder`)

| Type | Parameters | Description |
|------|-----------|-------------|
| `generate sql` | `SCHEMA` | Main SQL generation prompt. Schema formatted by `PromptBuilder.format_schema()`. |
| `extract relations` | `SQLQuery` | Extracts JOIN relationships from an existing SQL query. |
| `create data dict` | — | Generates table descriptions. |
| `generate data dict` | `DDLQUERY`, `INSERETQUERY` | Generates full data dictionaries from DDL. |

---

## Running Tests

```bash
python -m pytest tests/ -v
```

All 30 tests run without ML models, ChromaDB, or API keys — all external dependencies are mocked.

---

## Extending

### Adding a new vector store
1. Subclass `BaseVectorStore` from `MetadataManager/MetadataStore/vdb/base.py`
2. Implement `connect()`, `add_data()`, `get_data()`
3. Instantiate your class in `RAGPipeline.ManageInformation.initialize_client()`

### Adding a new metadata store backend
1. Subclass `BaseMetadataStore` from `Utilities/store_interface.py`
2. Implement all five CRUD methods
3. Pass your implementation wherever `accessDB` is currently used

### Adding a new LLM provider
1. Add a JSON request template to `APIManager/APIHeads/`
2. Add the provider config block to `APIManager/model_access_config.YAML`
3. Add response parsing for the new provider in `AllAPICaller.CallService()`

---

## License

MIT License. See [LICENSE](LICENSE) for details.
