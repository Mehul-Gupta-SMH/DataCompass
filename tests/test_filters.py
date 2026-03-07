"""
Tests for the filter methods in SQLBuilderComponents.

Tests run without any ML models, ChromaDB, or live databases.
get_config_val() is mocked throughout.
"""

import unittest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Helpers — instantiate SQLBuilderSupport without real config/db
# ---------------------------------------------------------------------------

def _make_support(user_query="show me revenue by product"):
    """Return a SQLBuilderSupport instance with all external deps mocked."""
    with patch("SQLBuilderComponents.get_config_val", return_value={"name": "chroma", "path": "/tmp"}), \
         patch("SQLBuilderComponents.accessDB"):
        from SQLBuilderComponents import SQLBuilderSupport
        obj = SQLBuilderSupport.__new__(SQLBuilderSupport)
        obj.user_query = user_query
        obj.table_list = {"direct": {}, "intermediate": {}}
        obj.join_keys = None
        obj.table_metadata = {}
        obj.vdb_config = {}
        obj.tmddb_config = {}
        obj.DBObj = MagicMock()
        return obj


# ---------------------------------------------------------------------------
# __filterRelevantResults__ tests
# ---------------------------------------------------------------------------

class TestFilterRelevantResults(unittest.TestCase):

    def _scored_results(self, scores_map):
        """Build a fake results_w_scores dict from {table_name: reranker_score}."""
        return {
            f"uuid-{name}": {
                "data": f"{name} description",
                "metadata": {"TableName": name},
                "distance": 0.1,
                "scores": {"reranker": score, "keyword": 0.5}
            }
            for name, score in scores_map.items()
        }

    @patch("SQLBuilderComponents.get_config_val", return_value=0.0)
    def test_removes_results_below_threshold(self, _):
        obj = _make_support()
        results = self._scored_results({"orders": 1.5, "products": -0.5})
        filtered = obj.__filterRelevantResults__(results)
        self.assertIn("orders", filtered)
        self.assertNotIn("products", filtered)

    @patch("SQLBuilderComponents.get_config_val", return_value=0.0)
    def test_keeps_all_above_threshold(self, _):
        obj = _make_support()
        results = self._scored_results({"orders": 2.0, "products": 0.5, "customers": 1.0})
        filtered = obj.__filterRelevantResults__(results)
        self.assertEqual(set(filtered.keys()), {"orders", "products", "customers"})

    @patch("SQLBuilderComponents.get_config_val", return_value=0.0)
    def test_sorted_by_reranker_score_descending(self, _):
        obj = _make_support()
        results = self._scored_results({"a": 1.0, "b": 3.0, "c": 2.0})
        filtered = obj.__filterRelevantResults__(results)
        keys = list(filtered.keys())
        self.assertEqual(keys, ["b", "c", "a"])

    @patch("SQLBuilderComponents.get_config_val", return_value=5.0)
    def test_empty_when_all_below_high_threshold(self, _):
        obj = _make_support()
        results = self._scored_results({"orders": 1.0, "products": 2.0})
        filtered = obj.__filterRelevantResults__(results)
        self.assertEqual(filtered, {})

    @patch("SQLBuilderComponents.get_config_val", return_value=0.0)
    def test_output_has_description_and_columns_keys(self, _):
        obj = _make_support()
        results = self._scored_results({"orders": 1.0})
        filtered = obj.__filterRelevantResults__(results)
        self.assertIn("description", filtered["orders"])
        self.assertIn("columns", filtered["orders"])


# ---------------------------------------------------------------------------
# __filterAdditionalColumns__ tests
# ---------------------------------------------------------------------------

class TestFilterAdditionalColumns(unittest.TestCase):

    # col tuple format: (ColumnName, DataType, Constraints, Desc)
    COLS = [
        ("order_id",    "INT",     "PRIMARY KEY", "Unique order identifier"),
        ("customer_id", "INT",     "FOREIGN KEY", "FK to customers table"),
        ("created_at",  "DATE",    "",            "Timestamp of order creation"),
        ("revenue",     "DECIMAL", "",            "Total revenue for the order"),
        ("color",       "TEXT",    "",            "Packaging colour code"),
    ]

    @patch("SQLBuilderComponents.get_config_val", return_value=0.0)
    def test_primary_key_always_kept(self, _):
        obj = _make_support("unrelated query xyz")
        result = obj.__filterAdditionalColumns__(self.COLS)
        names = [c[0] for c in result]
        self.assertIn("order_id", names)

    @patch("SQLBuilderComponents.get_config_val", return_value=0.0)
    def test_foreign_key_always_kept(self, _):
        obj = _make_support("unrelated query xyz")
        result = obj.__filterAdditionalColumns__(self.COLS)
        names = [c[0] for c in result]
        self.assertIn("customer_id", names)

    @patch("SQLBuilderComponents.get_config_val", return_value=0.0)
    def test_relevant_column_kept_by_bm25(self, _):
        obj = _make_support("show me total revenue for each order")
        result = obj.__filterAdditionalColumns__(self.COLS)
        names = [c[0] for c in result]
        self.assertIn("revenue", names)

    @patch("SQLBuilderComponents.get_config_val", return_value=0.0)
    def test_empty_input_returns_empty(self, _):
        obj = _make_support()
        self.assertEqual(obj.__filterAdditionalColumns__([]), [])

    @patch("SQLBuilderComponents.get_config_val", return_value=999.0)
    def test_fallback_to_all_when_nothing_passes(self, _):
        """With an impossibly high threshold and no keys, all columns returned."""
        cols = [
            ("created_at", "DATE", "", "Creation timestamp"),
            ("color",      "TEXT", "", "Colour code"),
        ]
        obj = _make_support("revenue product sales")
        result = obj.__filterAdditionalColumns__(cols)
        self.assertEqual(result, cols)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestFilterEdgeCases(unittest.TestCase):

    @patch("SQLBuilderComponents.get_config_val", return_value=0.0)
    def test_columns_with_none_fields_do_not_crash(self, _):
        cols = [
            (None,       "INT",  "PRIMARY KEY", None),
            ("some_col", "TEXT", None,          None),
        ]
        obj = _make_support("find something")
        result = obj.__filterAdditionalColumns__(cols)
        self.assertIsInstance(result, list)


# ---------------------------------------------------------------------------
# BM25 caching
# ---------------------------------------------------------------------------

class TestBM25Cache(unittest.TestCase):

    def test_same_corpus_reuses_cached_index(self):
        """_build_bm25 should return the identical object for the same corpus_key."""
        from SQLBuilderComponents import _build_bm25
        _build_bm25.cache_clear()

        key = (("order", "id"), ("customer", "name"))
        first  = _build_bm25(key)
        second = _build_bm25(key)

        self.assertIs(first, second)
        self.assertEqual(_build_bm25.cache_info().hits, 1)

    def test_different_corpus_builds_new_index(self):
        """Different column sets should produce distinct BM25 objects."""
        from SQLBuilderComponents import _build_bm25
        _build_bm25.cache_clear()

        key_a = (("order", "id"),)
        key_b = (("product", "name"),)

        self.assertIsNot(_build_bm25(key_a), _build_bm25(key_b))

    @patch("SQLBuilderComponents.get_config_val", return_value=0.0)
    def test_filter_columns_hits_cache_on_second_call(self, _):
        """Calling __filterAdditionalColumns__ twice with identical columns
        should result in exactly one cache miss and one cache hit."""
        from SQLBuilderComponents import _build_bm25
        _build_bm25.cache_clear()

        cols = [
            ("order_id",  "INT",  "PRIMARY KEY", "Unique order identifier"),
            ("revenue",   "DECIMAL", "",         "Total revenue"),
        ]
        obj = _make_support("show revenue")
        obj.__filterAdditionalColumns__(cols)  # miss
        obj.__filterAdditionalColumns__(cols)  # hit

        self.assertEqual(_build_bm25.cache_info().hits, 1)
        self.assertEqual(_build_bm25.cache_info().misses, 1)


# ---------------------------------------------------------------------------
# __getTableRelations__ — intermediate table bookkeeping
# ---------------------------------------------------------------------------

class TestGetTableRelations(unittest.TestCase):
    """Regression tests for the overwrite bug in __getTableRelations__.

    Previously the code did:
        self.table_list["intermediate"] = {table: ...}
    which replaced the entire dict on each iteration, so only the last
    intermediate table survived.  The fix uses:
        self.table_list["intermediate"][table] = ...
    """

    def _make_support_with_direct(self, direct_tables):
        obj = _make_support()
        obj.table_list["direct"] = {t: {"description": "", "columns": {}} for t in direct_tables}
        return obj

    @patch("SQLBuilderComponents.ManageRelations.Relations")
    def test_single_intermediate_table_is_stored(self, MockRelations):
        MockRelations.return_value.getRelation.return_value = [
            {"source": "customers", "target": "orders", "edge_attributes": {}}
        ]
        obj = self._make_support_with_direct(["orders"])
        obj.__getTableRelations__()
        self.assertIn("customers", obj.table_list["intermediate"])

    @patch("SQLBuilderComponents.ManageRelations.Relations")
    def test_multiple_intermediate_tables_all_stored(self, MockRelations):
        """All intermediate tables from multiple JOINs must be present — not just the last."""
        MockRelations.return_value.getRelation.return_value = [
            {"source": "customers", "target": "orders",   "edge_attributes": {}},
            {"source": "products",  "target": "orders",   "edge_attributes": {}},
            {"source": "regions",   "target": "customers","edge_attributes": {}},
        ]
        obj = self._make_support_with_direct(["orders"])
        obj.__getTableRelations__()

        inter = obj.table_list["intermediate"]
        self.assertIn("customers", inter, "customers missing from intermediate")
        self.assertIn("products",  inter, "products missing from intermediate")
        self.assertIn("regions",   inter, "regions missing from intermediate")

    @patch("SQLBuilderComponents.ManageRelations.Relations")
    def test_direct_tables_not_duplicated_in_intermediate(self, MockRelations):
        MockRelations.return_value.getRelation.return_value = [
            {"source": "orders", "target": "customers", "edge_attributes": {}}
        ]
        obj = self._make_support_with_direct(["orders", "customers"])
        obj.__getTableRelations__()
        self.assertNotIn("orders",    obj.table_list["intermediate"])
        self.assertNotIn("customers", obj.table_list["intermediate"])

    @patch("SQLBuilderComponents.ManageRelations.Relations")
    def test_intermediate_table_not_added_twice(self, MockRelations):
        """Same intermediate table referenced by two JOINs should appear only once."""
        MockRelations.return_value.getRelation.return_value = [
            {"source": "shared", "target": "orders",    "edge_attributes": {}},
            {"source": "shared", "target": "customers", "edge_attributes": {}},
        ]
        obj = self._make_support_with_direct(["orders", "customers"])
        obj.__getTableRelations__()
        # Ensure it appears exactly once (dict key uniqueness guarantees this, but
        # previous overwrite would silently drop tables — count is always 1 by dict key)
        self.assertIn("shared", obj.table_list["intermediate"])
        self.assertEqual(len(obj.table_list["intermediate"]), 1)


# ---------------------------------------------------------------------------
# __getInterTablesDesc__ — description unwrapping
# ---------------------------------------------------------------------------

class TestGetInterTablesDesc(unittest.TestCase):
    """Verify that intermediate table descriptions are stored as plain strings."""

    def test_description_is_unwrapped_from_tuple(self):
        obj = _make_support()
        obj.table_list["intermediate"]["customers"] = {"description": "", "columns": {}}
        obj.tmddb_config = {"tableDescName": "tableDesc"}
        obj.DBObj.get_data.return_value = ("Customer information",)

        obj.__getInterTablesDesc__()

        result = obj.table_list["intermediate"]["customers"]["description"]
        self.assertEqual(result, "Customer information")
        self.assertIsInstance(result, str)

    def test_missing_description_falls_back_to_empty_string(self):
        obj = _make_support()
        obj.table_list["intermediate"]["unknown_table"] = {"description": "", "columns": {}}
        obj.tmddb_config = {"tableDescName": "tableDesc"}
        obj.DBObj.get_data.return_value = None

        obj.__getInterTablesDesc__()

        result = obj.table_list["intermediate"]["unknown_table"]["description"]
        self.assertEqual(result, "")

    def test_description_renders_as_prose_in_format_schema(self):
        """After the fix, format_schema should output the description as plain prose."""
        from APIManager.PromptBuilder import PromptBuilder

        context = {
            "user_query": "show orders with customer names",
            "table_list": {
                "direct": {},
                "intermediate": {
                    "customers": {
                        "description": "Stores all customer records",
                        "columns": [("customer_id", "INT", "PRIMARY KEY", "Customer PK")],
                    }
                },
            },
            "join_keys": [],
        }
        result = PromptBuilder.format_schema(context)
        self.assertIn("Stores all customer records", result)
        # Must not contain a tuple repr like "('Stores all customer records',)"
        self.assertNotIn("('Stores all customer records',)", result)


if __name__ == "__main__":
    unittest.main()
