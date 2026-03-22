"""
test_glossary_retrieval.py — SL6: Tests for semantic search (SL1) and prompt injection (SL2)

All ChromaDB / SentenceTransformer calls are mocked — no real model or vector DB required.

Coverage:
  - index_term: calls embedding model + ChromaDB addData
  - get_business_context: threshold filtering, instance filtering, SQLite enrichment
  - get_business_context: graceful fallback on collection-not-found error
  - PromptBuilder.format_schema: renders ## Business Definitions block
  - PromptBuilder.format_schema: skips block when no glossary hits
  - main._get_business_context integration (SL2 wiring)
"""

import json
import sqlite3
from unittest.mock import MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Fixture: in-memory DB for glossary CRUD (same pattern as test_glossary_store)
# ---------------------------------------------------------------------------

@pytest.fixture()
def mem_db(monkeypatch):
    conn = sqlite3.connect(":memory:")
    from Utilities.base_utils import accessDB
    db_obj = accessDB.__new__(accessDB)
    db_obj.connection = conn
    db_obj.cursor = conn.cursor()

    import MetadataManager.GlossaryStore as GS
    db_obj.create_table(GS._TABLE_SCHEMA)
    monkeypatch.setattr(GS, "_get_db", lambda: db_obj)
    yield db_obj, GS
    conn.close()


# ---------------------------------------------------------------------------
# index_term (SL1)
# ---------------------------------------------------------------------------

class TestIndexTerm:
    # addData is imported lazily inside index_term — patch at source module

    def test_calls_encode_with_embed_document(self, mem_db):
        _, GS = mem_db
        from MetadataManager.GlossaryStore import add_term, index_term

        tid = add_term({
            "term_name": "AUM",
            "full_name": "Assets Under Management",
            "definition": "Total managed assets.",
            "synonyms": ["managed assets"],
            "instance_name": "prod",
            "domain": "finance",
        })
        term = GS.get_term(tid)

        mock_model = MagicMock()
        mock_model.encode.return_value = MagicMock(tolist=lambda: [0.1, 0.2, 0.3])

        with patch("MetadataManager.MetadataStore.vdb.Chroma.addData"):
            index_term(term, mock_model, MagicMock())

        mock_model.encode.assert_called_once()
        doc_arg = mock_model.encode.call_args[0][0]
        assert "AUM" in doc_arg
        assert "Assets Under Management" in doc_arg
        assert "managed assets" in doc_arg

    def test_calls_addData_with_correct_collection(self, mem_db):
        _, GS = mem_db
        from MetadataManager.GlossaryStore import add_term, index_term

        tid = add_term({"term_name": "Churn", "instance_name": "p"})
        term = GS.get_term(tid)

        mock_model = MagicMock()
        mock_model.encode.return_value = MagicMock(tolist=lambda: [0.5])

        with patch("MetadataManager.MetadataStore.vdb.Chroma.addData") as mock_add:
            index_term(term, mock_model, MagicMock())
            # addData(client, data, vdb_meta)
            vdb_meta = mock_add.call_args[0][2]
            assert vdb_meta["collection_name"] == "business_glossary"

    def test_skips_empty_document(self, mem_db):
        _, GS = mem_db
        from MetadataManager.GlossaryStore import index_term

        term = {"term_id": "x", "term_name": "", "synonyms": []}
        mock_model = MagicMock()

        with patch("MetadataManager.MetadataStore.vdb.Chroma.addData") as mock_add:
            index_term(term, mock_model, MagicMock())
            mock_add.assert_not_called()
        mock_model.encode.assert_not_called()


# ---------------------------------------------------------------------------
# get_business_context (SL1)
# ---------------------------------------------------------------------------

class TestGetBusinessContext:
    # get_business_context uses lazy imports — patch at source modules, not GlossaryStore

    def _make_chroma_response(self, term_ids, distances):
        """Build a mock ChromaDB getData return value."""
        ids       = [[f"chroma-{i}" for i in range(len(term_ids))]]
        metadatas = [[{"term_id": tid} for tid in term_ids]]
        dists     = [distances]
        return {"ids": ids, "metadatas": metadatas, "distances": dists}

    def _cfg_side_effect(self, *args, **kwargs):
        """Return a config dict with all keys needed by get_business_context."""
        return {"path": "/mock", "name": "chroma", "model": "mock-model"}

    def test_returns_hits_below_threshold(self, mem_db):
        _, GS = mem_db
        from MetadataManager.GlossaryStore import add_term, get_business_context

        tid = add_term({
            "term_name": "AUM",
            "definition": "Total AUM",
            "instance_name": "prod",
        })

        chroma_resp = self._make_chroma_response([tid], [0.3])

        with patch("Utilities.base_utils.get_config_val", side_effect=self._cfg_side_effect), \
             patch("sentence_transformers.SentenceTransformer") as MockST, \
             patch("MetadataManager.MetadataStore.vdb.Chroma.getclient"), \
             patch("MetadataManager.MetadataStore.vdb.Chroma.getData", return_value=chroma_resp):

            MockST.return_value.encode.return_value = MagicMock(tolist=lambda: [0.1])
            hits = get_business_context("assets under management", instance_name="prod")

        assert len(hits) == 1
        assert hits[0]["term_name"] == "AUM"
        assert hits[0]["_distance"] == 0.3

    def test_excludes_hits_above_threshold(self, mem_db):
        _, GS = mem_db
        from MetadataManager.GlossaryStore import add_term, get_business_context

        tid = add_term({"term_name": "Churn", "instance_name": "p"})
        chroma_resp = self._make_chroma_response([tid], [0.9])  # above default 0.6

        with patch("Utilities.base_utils.get_config_val", side_effect=self._cfg_side_effect), \
             patch("sentence_transformers.SentenceTransformer") as MockST, \
             patch("MetadataManager.MetadataStore.vdb.Chroma.getclient"), \
             patch("MetadataManager.MetadataStore.vdb.Chroma.getData", return_value=chroma_resp):

            MockST.return_value.encode.return_value = MagicMock(tolist=lambda: [0.1])
            hits = get_business_context("delivery lag", max_distance=0.6)

        assert hits == []

    def test_returns_empty_on_collection_not_found(self, mem_db):
        _, GS = mem_db
        from MetadataManager.GlossaryStore import get_business_context

        with patch("Utilities.base_utils.get_config_val", side_effect=self._cfg_side_effect), \
             patch("sentence_transformers.SentenceTransformer") as MockST, \
             patch("MetadataManager.MetadataStore.vdb.Chroma.getclient"), \
             patch("MetadataManager.MetadataStore.vdb.Chroma.getData",
                   side_effect=ValueError("Collection doesn't exists")):

            MockST.return_value.encode.return_value = MagicMock(tolist=lambda: [0.1])
            hits = get_business_context("anything")

        assert hits == []

    def test_returns_empty_on_config_failure(self, mem_db):
        _, GS = mem_db
        from MetadataManager.GlossaryStore import get_business_context

        with patch("Utilities.base_utils.get_config_val", side_effect=KeyError("models_repo")):
            hits = get_business_context("anything")

        assert hits == []

    def test_results_ordered_by_distance(self, mem_db):
        _, GS = mem_db
        from MetadataManager.GlossaryStore import add_term, get_business_context

        tid1 = add_term({"term_name": "AUM",   "instance_name": "p"})
        tid2 = add_term({"term_name": "Churn", "instance_name": "p"})
        # Churn is closer (lower distance)
        chroma_resp = self._make_chroma_response([tid1, tid2], [0.5, 0.2])

        with patch("Utilities.base_utils.get_config_val", side_effect=self._cfg_side_effect), \
             patch("sentence_transformers.SentenceTransformer") as MockST, \
             patch("MetadataManager.MetadataStore.vdb.Chroma.getclient"), \
             patch("MetadataManager.MetadataStore.vdb.Chroma.getData", return_value=chroma_resp):

            MockST.return_value.encode.return_value = MagicMock(tolist=lambda: [0.1])
            hits = get_business_context("q", max_distance=0.9)

        assert hits[0]["term_name"] == "Churn"   # distance 0.2 first
        assert hits[1]["term_name"] == "AUM"     # distance 0.5 second

    def test_unknown_term_id_in_chroma_skipped(self, mem_db):
        _, GS = mem_db
        from MetadataManager.GlossaryStore import get_business_context

        # Chroma returns a term_id that does not exist in SQLite
        chroma_resp = self._make_chroma_response(["ghost-id-not-in-sqlite"], [0.1])

        with patch("Utilities.base_utils.get_config_val", side_effect=self._cfg_side_effect), \
             patch("sentence_transformers.SentenceTransformer") as MockST, \
             patch("MetadataManager.MetadataStore.vdb.Chroma.getclient"), \
             patch("MetadataManager.MetadataStore.vdb.Chroma.getData", return_value=chroma_resp):

            MockST.return_value.encode.return_value = MagicMock(tolist=lambda: [0.1])
            hits = get_business_context("q", max_distance=0.9)

        assert hits == []


# ---------------------------------------------------------------------------
# SL2 — PromptBuilder.format_schema with glossary_hits
# ---------------------------------------------------------------------------

class TestFormatSchemaGlossaryBlock:

    def _empty_context(self, query="test query"):
        return {
            "user_query": query,
            "table_list": {"direct": {}, "intermediate": {}},
            "join_keys": [],
        }

    def test_no_glossary_key_renders_no_business_definitions(self):
        from APIManager.PromptBuilder import PromptBuilder
        ctx = self._empty_context()
        result = PromptBuilder.format_schema(ctx)
        assert "## Business Definitions" not in result

    def test_empty_glossary_hits_renders_no_block(self):
        from APIManager.PromptBuilder import PromptBuilder
        ctx = self._empty_context()
        ctx["glossary_hits"] = []
        result = PromptBuilder.format_schema(ctx)
        assert "## Business Definitions" not in result

    def test_glossary_hit_renders_term_name(self):
        from APIManager.PromptBuilder import PromptBuilder
        ctx = self._empty_context()
        ctx["glossary_hits"] = [{
            "term_name": "AUM",
            "full_name": "Assets Under Management",
            "definition": "Total managed value.",
            "formula": "SUM(market_value)",
            "formula_type": "sql_expression",
            "table_deps": ["positions"],
            "example_value": "$4.2B",
            "_distance": 0.2,
        }]
        result = PromptBuilder.format_schema(ctx)
        assert "## Business Definitions" in result
        assert "AUM" in result
        assert "Assets Under Management" in result

    def test_glossary_hit_renders_formula(self):
        from APIManager.PromptBuilder import PromptBuilder
        ctx = self._empty_context()
        ctx["glossary_hits"] = [{
            "term_name": "AUM",
            "formula": "SUM(market_value)",
            "formula_type": "sql_expression",
            "table_deps": [],
            "_distance": 0.2,
        }]
        result = PromptBuilder.format_schema(ctx)
        assert "SUM(market_value)" in result

    def test_glossary_hit_renders_table_deps(self):
        from APIManager.PromptBuilder import PromptBuilder
        ctx = self._empty_context()
        ctx["glossary_hits"] = [{
            "term_name": "AUM",
            "table_deps": ["positions", "accounts"],
            "_distance": 0.2,
        }]
        result = PromptBuilder.format_schema(ctx)
        assert "positions" in result
        assert "accounts" in result

    def test_multiple_hits_all_rendered(self):
        from APIManager.PromptBuilder import PromptBuilder
        ctx = self._empty_context()
        ctx["glossary_hits"] = [
            {"term_name": "AUM",   "table_deps": [], "_distance": 0.1},
            {"term_name": "Churn", "table_deps": [], "_distance": 0.3},
        ]
        result = PromptBuilder.format_schema(ctx)
        assert "AUM" in result
        assert "Churn" in result

    def test_business_definitions_appears_before_database_schema(self):
        from APIManager.PromptBuilder import PromptBuilder
        ctx = self._empty_context()
        ctx["glossary_hits"] = [{"term_name": "AUM", "table_deps": [], "_distance": 0.1}]
        result = PromptBuilder.format_schema(ctx)
        biz_pos = result.index("## Business Definitions")
        schema_pos = result.index("## Database Schema")
        assert biz_pos < schema_pos


# ---------------------------------------------------------------------------
# SL2 — main._get_business_context injection
# ---------------------------------------------------------------------------

class TestMainGlossaryInjection:
    """Verify generateQuery passes glossary_hits into the context dict."""

    def test_generateQuery_format_schema_receives_glossary_hits(self):
        """
        format_schema is called with context['glossary_hits'] populated from
        _get_business_context when a match is found.
        """
        fake_context = {
            "user_query": "what is AUM",
            "table_list": {"direct": {}, "intermediate": {}},
            "join_keys": [],
        }
        fake_hit = {"term_name": "AUM", "table_deps": [], "_distance": 0.1}
        captured_ctx: dict = {}

        def capturing_format_schema(ctx):
            captured_ctx.update(ctx)
            return "## User Question\nwhat is AUM\n\n## Database Schema\n"

        with patch("main._adaptive_retrieval", return_value=fake_context), \
             patch("main._get_business_context", return_value=[fake_hit]), \
             patch("main.PromptBuilder") as MockPB, \
             patch("main.CallLLMApi") as MockLLM:

            MockPB.format_schema.side_effect = capturing_format_schema
            MockPB.return_value.build.return_value = "prompt"
            MockLLM.return_value.CallService.return_value = '{"type":"sql","content":"SELECT 1"}'

            from main import generateQuery
            generateQuery("what is AUM", "open_ai")

        assert "glossary_hits" in captured_ctx
        assert captured_ctx["glossary_hits"] == [fake_hit]

    def test_generateQuery_glossary_hits_in_context_before_format_schema(self):
        """
        Structural test: after _adaptive_retrieval and _get_business_context,
        context['glossary_hits'] is set. We verify the mutation directly.
        """
        fake_context = {
            "user_query": "what is AUM",
            "table_list": {"direct": {}, "intermediate": {}},
            "join_keys": [],
        }
        fake_hit = {"term_name": "AUM", "table_deps": [], "_distance": 0.1}

        with patch("main._adaptive_retrieval", return_value=fake_context), \
             patch("main._get_business_context", return_value=[fake_hit]), \
             patch("main.PromptBuilder") as MockPB, \
             patch("main.CallLLMApi") as MockLLM:

            MockPB.format_schema.return_value = "schema-str"
            MockPB.return_value.build.return_value = "prompt"
            MockLLM.return_value.CallService.return_value = '{"type":"sql","content":"SELECT 1"}'

            from main import generateQuery
            generateQuery("what is AUM", "open_ai")

        # After the call, fake_context should have glossary_hits attached
        assert "glossary_hits" in fake_context
        assert fake_context["glossary_hits"] == [fake_hit]

    def test_generateQuery_fallback_when_glossary_unavailable(self):
        """If GlossaryStore.get_business_context raises, _get_business_context returns []."""
        fake_context = {
            "user_query": "sales",
            "table_list": {"direct": {}, "intermediate": {}},
            "join_keys": [],
        }

        # Patch the inner import inside _get_business_context to raise
        with patch("main._adaptive_retrieval", return_value=fake_context), \
             patch("MetadataManager.GlossaryStore.get_business_context",
                   side_effect=RuntimeError("model unavailable")), \
             patch("main.PromptBuilder") as MockPB, \
             patch("main.CallLLMApi") as MockLLM:

            MockPB.format_schema.return_value = "schema-str"
            MockPB.return_value.build.return_value = "prompt"
            MockLLM.return_value.CallService.return_value = '{"type":"sql","content":"SELECT 1"}'

            from main import generateQuery
            generateQuery("sales", "open_ai")   # must not raise

        # glossary_hits falls back to []
        assert fake_context.get("glossary_hits") == []
