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


if __name__ == "__main__":
    unittest.main()
