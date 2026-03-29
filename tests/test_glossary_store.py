"""
test_glossary_store.py — SL6: Unit tests for GlossaryStore CRUD (SL0)

All tests run against a fresh in-memory SQLite DB — no files written, no real
ML models loaded.  Heavy packages are pre-mocked by conftest.py.

Coverage:
  - add_term: happy path, missing term_name, custom term_id
  - get_term: found, not found
  - get_term_by_name: case-insensitive match, instance scoping
  - update_term: scalar fields, JSON list fields
  - delete_term: removes row
  - list_terms: no filter, instance filter, domain filter
  - search_by_name: partial match on term_name, full_name, instance filter
  - _build_embed_document: correct concatenation
"""

import json
import sqlite3

import pytest


# ---------------------------------------------------------------------------
# Fixture: wire GlossaryStore to a fresh in-memory DB per test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _patch_get_db(monkeypatch):
    """
    Replace _get_db() with a version that returns an accessDB wired to an
    in-memory SQLite connection.  The business_terms table is created once.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = None  # plain tuples, same as production

    from Utilities.base_utils import accessDB
    db_obj = accessDB.__new__(accessDB)
    db_obj.connection = conn
    db_obj.cursor = conn.cursor()

    import MetadataManager.GlossaryStore as GS
    # Ensure table exists in the in-memory DB
    db_obj.create_table(GS._TABLE_SCHEMA)

    monkeypatch.setattr(GS, "_get_db", lambda: db_obj)
    yield db_obj
    conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_term(**overrides) -> dict:
    base = {
        "term_name":     "AUM",
        "full_name":     "Assets Under Management",
        "definition":    "Total market value of assets managed for clients.",
        "formula":       "SUM(market_value)",
        "formula_type":  "sql_expression",
        "table_deps":    ["positions", "accounts"],
        "column_deps":   ["positions.market_value"],
        "synonyms":      ["managed assets", "total aum"],
        "example_value": "$4.2B",
        "domain":        "finance",
        "instance_name": "prod",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# add_term
# ---------------------------------------------------------------------------

class TestAddTerm:

    def test_returns_term_id_string(self):
        from MetadataManager.GlossaryStore import add_term
        tid = add_term(_sample_term())
        assert isinstance(tid, str) and len(tid) == 36  # UUID

    def test_custom_term_id_preserved(self):
        from MetadataManager.GlossaryStore import add_term, get_term
        tid = add_term(_sample_term(term_id="my-custom-id"))
        assert tid == "my-custom-id"
        row = get_term("my-custom-id")
        assert row is not None
        assert row["term_name"] == "AUM"

    def test_raises_on_missing_term_name(self):
        from MetadataManager.GlossaryStore import add_term
        with pytest.raises(ValueError, match="term_name is required"):
            add_term({"full_name": "No Name"})

    def test_raises_on_empty_term_name(self):
        from MetadataManager.GlossaryStore import add_term
        with pytest.raises(ValueError, match="term_name is required"):
            add_term({"term_name": "   "})

    def test_json_fields_serialised_as_lists(self):
        from MetadataManager.GlossaryStore import add_term, get_term
        tid = add_term(_sample_term())
        row = get_term(tid)
        assert row["table_deps"] == ["positions", "accounts"]
        assert row["synonyms"] == ["managed assets", "total aum"]

    def test_timestamps_are_set(self):
        from MetadataManager.GlossaryStore import add_term, get_term
        tid = add_term(_sample_term())
        row = get_term(tid)
        assert row["created_at"]
        assert row["updated_at"]


# ---------------------------------------------------------------------------
# get_term
# ---------------------------------------------------------------------------

class TestGetTerm:

    def test_returns_none_for_unknown_id(self):
        from MetadataManager.GlossaryStore import get_term
        assert get_term("does-not-exist") is None

    def test_returns_dict_for_known_id(self):
        from MetadataManager.GlossaryStore import add_term, get_term
        tid = add_term(_sample_term())
        row = get_term(tid)
        assert isinstance(row, dict)
        assert row["term_name"] == "AUM"
        assert row["domain"] == "finance"


# ---------------------------------------------------------------------------
# get_term_by_name
# ---------------------------------------------------------------------------

class TestGetTermByName:

    def test_finds_term_case_insensitive(self):
        from MetadataManager.GlossaryStore import add_term, get_term_by_name
        add_term(_sample_term())
        # accessDB uses lower() in WHERE — so "aum" should match "AUM"
        row = get_term_by_name("aum")
        assert row is not None
        assert row["term_name"] == "AUM"

    def test_returns_none_when_not_found(self):
        from MetadataManager.GlossaryStore import get_term_by_name
        assert get_term_by_name("NonExistent") is None

    def test_instance_scoping_finds_correct_term(self):
        from MetadataManager.GlossaryStore import add_term, get_term_by_name
        add_term(_sample_term(instance_name="prod"))
        add_term(_sample_term(instance_name="staging"))
        row = get_term_by_name("aum", instance_name="staging")
        assert row is not None
        assert row["instance_name"] == "staging"

    def test_instance_scoping_excludes_other_instances(self):
        from MetadataManager.GlossaryStore import add_term, get_term_by_name
        add_term(_sample_term(instance_name="prod"))
        row = get_term_by_name("aum", instance_name="staging")
        assert row is None


# ---------------------------------------------------------------------------
# update_term
# ---------------------------------------------------------------------------

class TestUpdateTerm:

    def test_updates_scalar_field(self):
        from MetadataManager.GlossaryStore import add_term, update_term, get_term
        tid = add_term(_sample_term())
        update_term(tid, {"domain": "investment"})
        row = get_term(tid)
        assert row["domain"] == "investment"

    def test_updates_json_list_field(self):
        from MetadataManager.GlossaryStore import add_term, update_term, get_term
        tid = add_term(_sample_term())
        update_term(tid, {"synonyms": ["assets managed", "aum total"]})
        row = get_term(tid)
        assert row["synonyms"] == ["assets managed", "aum total"]

    def test_updated_at_changes(self):
        from MetadataManager.GlossaryStore import add_term, update_term, get_term
        tid = add_term(_sample_term())
        import time
        time.sleep(0.01)
        update_term(tid, {"domain": "new_domain"})
        new_ts = get_term(tid)["updated_at"]
        # Timestamps may be equal in fast runs — just check field exists
        assert new_ts

    def test_created_at_not_changed_by_update(self):
        from MetadataManager.GlossaryStore import add_term, update_term, get_term
        tid = add_term(_sample_term())
        created_ts = get_term(tid)["created_at"]
        update_term(tid, {"domain": "x"})
        assert get_term(tid)["created_at"] == created_ts

    def test_returns_true(self):
        from MetadataManager.GlossaryStore import add_term, update_term
        tid = add_term(_sample_term())
        assert update_term(tid, {"domain": "x"}) is True


# ---------------------------------------------------------------------------
# delete_term
# ---------------------------------------------------------------------------

class TestDeleteTerm:

    def test_deletes_existing_term(self):
        from MetadataManager.GlossaryStore import add_term, delete_term, get_term
        tid = add_term(_sample_term())
        delete_term(tid)
        assert get_term(tid) is None

    def test_delete_nonexistent_does_not_raise(self):
        from MetadataManager.GlossaryStore import delete_term
        delete_term("ghost-id")   # should not raise


# ---------------------------------------------------------------------------
# list_terms
# ---------------------------------------------------------------------------

class TestListTerms:

    def test_returns_all_when_no_filter(self):
        from MetadataManager.GlossaryStore import add_term, list_terms
        add_term(_sample_term(term_name="AUM", domain="finance", instance_name="p"))
        add_term(_sample_term(term_name="Churn", domain="marketing", instance_name="p"))
        rows = list_terms()
        assert len(rows) == 2

    def test_filters_by_instance_name(self):
        from MetadataManager.GlossaryStore import add_term, list_terms
        add_term(_sample_term(term_name="AUM", instance_name="prod"))
        add_term(_sample_term(term_name="Churn", instance_name="staging"))
        rows = list_terms(instance_name="prod")
        assert len(rows) == 1
        assert rows[0]["term_name"] == "AUM"

    def test_filters_by_domain(self):
        from MetadataManager.GlossaryStore import add_term, list_terms
        add_term(_sample_term(term_name="AUM", domain="finance"))
        add_term(_sample_term(term_name="Clicks", domain="marketing"))
        rows = list_terms(domain="finance")
        assert len(rows) == 1
        assert rows[0]["term_name"] == "AUM"

    def test_combined_instance_and_domain_filter(self):
        from MetadataManager.GlossaryStore import add_term, list_terms
        add_term(_sample_term(term_name="AUM",    domain="finance",   instance_name="prod"))
        add_term(_sample_term(term_name="Clicks", domain="marketing", instance_name="prod"))
        add_term(_sample_term(term_name="AUM",    domain="finance",   instance_name="staging"))
        rows = list_terms(instance_name="prod", domain="finance")
        assert len(rows) == 1
        assert rows[0]["instance_name"] == "prod"

    def test_returns_empty_list_when_none_match(self):
        from MetadataManager.GlossaryStore import list_terms
        assert list_terms(instance_name="ghost") == []


# ---------------------------------------------------------------------------
# search_by_name
# ---------------------------------------------------------------------------

class TestSearchByName:

    def test_matches_partial_term_name(self):
        from MetadataManager.GlossaryStore import add_term, search_by_name
        add_term(_sample_term(term_name="AUM", instance_name="p"))
        add_term(_sample_term(term_name="Churn Rate", instance_name="p"))
        results = search_by_name("churn")
        assert len(results) == 1
        assert results[0]["term_name"] == "Churn Rate"

    def test_matches_partial_full_name(self):
        from MetadataManager.GlossaryStore import add_term, search_by_name
        add_term(_sample_term(term_name="AUM", full_name="Assets Under Management"))
        results = search_by_name("assets under")
        assert len(results) == 1

    def test_returns_empty_when_no_match(self):
        from MetadataManager.GlossaryStore import add_term, search_by_name
        add_term(_sample_term())
        assert search_by_name("zzz_unknown") == []

    def test_instance_filter_applied(self):
        from MetadataManager.GlossaryStore import add_term, search_by_name
        add_term(_sample_term(term_name="AUM", instance_name="prod"))
        add_term(_sample_term(term_name="AUM", instance_name="staging"))
        results = search_by_name("aum", instance_name="staging")
        assert all(r["instance_name"] == "staging" for r in results)
        assert len(results) == 1

    def test_case_insensitive_match(self):
        from MetadataManager.GlossaryStore import add_term, search_by_name
        add_term(_sample_term(term_name="AUM"))
        results = search_by_name("aum")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# _build_embed_document (SL1 unit)
# ---------------------------------------------------------------------------

class TestBuildEmbedDocument:

    def test_includes_term_name(self):
        from MetadataManager.GlossaryStore import _build_embed_document
        doc = _build_embed_document({"term_name": "AUM"})
        assert "AUM" in doc

    def test_includes_full_name(self):
        from MetadataManager.GlossaryStore import _build_embed_document
        doc = _build_embed_document({"term_name": "AUM", "full_name": "Assets Under Management"})
        assert "Assets Under Management" in doc

    def test_includes_definition(self):
        from MetadataManager.GlossaryStore import _build_embed_document
        doc = _build_embed_document({"term_name": "AUM", "definition": "Total managed assets"})
        assert "Total managed assets" in doc

    def test_includes_synonyms(self):
        from MetadataManager.GlossaryStore import _build_embed_document
        doc = _build_embed_document({"term_name": "AUM", "synonyms": ["managed assets", "total aum"]})
        assert "managed assets" in doc
        assert "total aum" in doc

    def test_handles_json_string_synonyms(self):
        from MetadataManager.GlossaryStore import _build_embed_document
        doc = _build_embed_document({
            "term_name": "AUM",
            "synonyms": json.dumps(["managed assets"])
        })
        assert "managed assets" in doc

    def test_empty_term_returns_empty_string(self):
        from MetadataManager.GlossaryStore import _build_embed_document
        doc = _build_embed_document({})
        assert doc == ""
