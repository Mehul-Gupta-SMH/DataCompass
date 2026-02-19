"""
Tests for Utilities.base_utils.

Tests run against an in-memory SQLite database — no file system writes needed.
get_config_val() is mocked wherever accessDB would call it.
cachefunc is tested with a patched accessDB.
"""

import sqlite3
import unittest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# accessDB tests (in-memory SQLite)
# ---------------------------------------------------------------------------

class TestAccessDB(unittest.TestCase):

    def _make_db(self):
        """Return an accessDB instance wired to an in-memory SQLite database."""
        with patch("Utilities.base_utils.get_config_val", return_value=":memory:"), \
             patch("Utilities.base_utils.os.path.exists", return_value=True), \
             patch("Utilities.base_utils.os.makedirs"), \
             patch("Utilities.base_utils.os.path.join", side_effect=lambda *a: ":memory:"):
            from Utilities.base_utils import accessDB
            db = accessDB.__new__(accessDB)
            db.connection = sqlite3.connect(":memory:")
            db.cursor = db.connection.cursor()
            return db

    def test_create_table_and_get_returns_none_when_empty(self):
        db = self._make_db()
        db.create_table({
            "tableName": "test_tbl",
            "columns": {"id": ["TEXT", "PRIMARY KEY"], "val": ["TEXT", ""]}
        })
        result = db.get_data("test_tbl", {}, ["id", "val"])
        self.assertIsNone(result)

    def test_post_data_and_get_data_one(self):
        db = self._make_db()
        db.create_table({
            "tableName": "test_tbl",
            "columns": {"id": ["TEXT", "PRIMARY KEY"], "val": ["TEXT", ""]}
        })
        db.post_data("test_tbl", [{"id": "k1", "val": "hello"}])
        result = db.get_data("test_tbl", {"id": "k1"}, ["val"])
        self.assertEqual(result, ("hello",))

    def test_post_data_and_get_data_all(self):
        db = self._make_db()
        db.create_table({
            "tableName": "test_tbl",
            "columns": {"id": ["TEXT", "PRIMARY KEY"], "val": ["TEXT", ""]}
        })
        db.post_data("test_tbl", [
            {"id": "k1", "val": "a"},
            {"id": "k2", "val": "b"},
        ])
        result = db.get_data("test_tbl", {}, ["id", "val"], fetchtype="All")
        self.assertEqual(len(result), 2)

    def test_delete_data_removes_row(self):
        db = self._make_db()
        db.create_table({
            "tableName": "test_tbl",
            "columns": {"id": ["TEXT", "PRIMARY KEY"], "val": ["TEXT", ""]}
        })
        db.post_data("test_tbl", [{"id": "k1", "val": "hello"}])
        db.delete_data("test_tbl", {"id": "k1"})
        result = db.get_data("test_tbl", {"id": "k1"}, ["val"])
        self.assertIsNone(result)

    def test_get_data_without_filter_returns_all(self):
        db = self._make_db()
        db.create_table({
            "tableName": "test_tbl",
            "columns": {"id": ["TEXT", "PRIMARY KEY"], "val": ["TEXT", ""]}
        })
        db.post_data("test_tbl", [{"id": "a", "val": "1"}, {"id": "b", "val": "2"}])
        result = db.get_data("test_tbl", {}, [], fetchtype="All")
        self.assertEqual(len(result), 2)


# ---------------------------------------------------------------------------
# cachefunc.close() bug fix test (F4)
# ---------------------------------------------------------------------------

class TestCachefuncClose(unittest.TestCase):

    def test_close_delegates_to_dbobj_connection(self):
        with patch("Utilities.base_utils.get_config_val", return_value=":memory:"), \
             patch("Utilities.base_utils.os.path.exists", return_value=True), \
             patch("Utilities.base_utils.os.makedirs"), \
             patch("Utilities.base_utils.os.path.join", side_effect=lambda *a: ":memory:"):
            from Utilities.base_utils import cachefunc, accessDB

            mock_db = MagicMock(spec=accessDB)
            mock_db.connection = MagicMock()

            cf = cachefunc.__new__(cachefunc)
            cf.DBObj = mock_db

            cf.close()
            mock_db.connection.close.assert_called_once()

    def test_close_does_not_reference_self_connection(self):
        """cachefunc should not have a self.connection attribute."""
        with patch("Utilities.base_utils.get_config_val", return_value=":memory:"), \
             patch("Utilities.base_utils.os.path.exists", return_value=True), \
             patch("Utilities.base_utils.os.makedirs"), \
             patch("Utilities.base_utils.os.path.join", side_effect=lambda *a: ":memory:"):
            from Utilities.base_utils import cachefunc

            cf = cachefunc.__new__(cachefunc)
            self.assertFalse(hasattr(cf, "connection"))


# ---------------------------------------------------------------------------
# store_interface contract test
# ---------------------------------------------------------------------------

class TestStoreInterface(unittest.TestCase):

    def test_accessdb_implements_base_metadata_store(self):
        from Utilities.store_interface import BaseMetadataStore
        from Utilities.base_utils import accessDB
        self.assertTrue(issubclass(accessDB, BaseMetadataStore))


if __name__ == "__main__":
    unittest.main()
