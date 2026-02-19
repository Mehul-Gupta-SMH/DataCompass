# SQLCoder — Task Book

Tasks ordered by impact tier, then complexity within each tier.
Status: `[ ]` pending · `[~]` in progress · `[x]` done

---

## Tier 1 — Security

| ID | Status | Task | Files |
|----|--------|------|-------|
| S1 | [x] | Replace `eval()` with `json.loads()` for API template loading | `APIManager/AllAPICaller.py:68` |
| S2 | [x] | Replace `eval()` with `ast.literal_eval()` for cache deserialization | `Utilities/base_utils.py:308` |
| S3 | [x] | Verify `model_access_config.YAML` was never committed to git history | confirmed clean — no commits found |

---

## Tier 2 — High Impact, Low Complexity

| ID | Status | Task | Files |
|----|--------|------|-------|
| Q1 | [x] | Remove hardcoded absolute paths — move to env vars or relative paths | `Utilities/base_utils.py:33`, all `Utilities/*.YAML` |
| Q2 | [x] | Remove double `__set_apidict__()` call — called in both `__init__` and `CallService` | `APIManager/AllAPICaller.py` |
| Q3 | [x] | Fix `.gitignore` — replace `/__pycache__` with `**/__pycache__` to catch nested dirs | `.gitignore` |
| Q4 | [x] | Replace all `print()` debug statements with `logging` | `SQLBuilderComponents.py`, `MetadataBuilder/importExisting/importData.py` |

---

## Tier 3 — High Impact, High Complexity

| ID | Status | Task | Files |
|----|--------|------|-------|
| C1 | [x] | Build structured prompt template — format context as DDL/markdown, not raw dict repr | `main.py`, `APIManager/PromptBuilder.py`, `APIManager/Prompts/taskGenerateSQL.txt` |
| C2 | [x] | Wire reranker scores into actual filtering — threshold or top-k cut on scored results | `SQLBuilderComponents.py`, `Utilities/retrieval_config.YAML` |
| C3 | [x] | Implement `__filterAdditionalColumns__()` — filter columns by relevance to user query | `SQLBuilderComponents.py` |

---

## Tier 4 — Medium Impact, Medium Complexity

| ID | Status | Task | Files |
|----|--------|------|-------|
| M1 | [x] | Switch `nx.Graph` to `nx.DiGraph` for directional JOIN relationships | `MetadataManager/MetadataStore/relationdb/networkxDB.py` |
| M2 | [x] | Fix silent error swallowing in `importData.py` — preserve original exception | `MetadataManager/MetadataBuilder/importExisting/importData.py` |
| M3 | [x] | Move module-level config/model loading in `RAGPipeline.py` into class `__init__` | `MetadataManager/MetadataStore/RAGPipeline.py` |
| M4 | [x] | Add retry/fallback logic to `CallLLMApi.CallService()` | `APIManager/AllAPICaller.py` |

---

## Tier 5 — Maintainability & Future-Proofing

| ID | Status | Task | Files |
|----|--------|------|-------|
| F1 | [x] | Introduce `VectorStore` interface to abstract ChromaDB — prep for Pinecone/QDrant | `MetadataManager/MetadataStore/vdb/base.py`, `vdb/Chroma.py`, `RAGPipeline.py` |
| F2 | [x] | Introduce metadata store interface to abstract SQLite — prep for other backends | `Utilities/store_interface.py`, `Utilities/base_utils.py` |
| F3 | [x] | Add a test suite | `tests/test_prompt_builder.py`, `tests/test_filters.py`, `tests/test_base_utils.py` |
| F4 | [x] | Fix `cachefunc.close()` — references `self.connection` which doesn't exist on the class | `Utilities/base_utils.py` |
