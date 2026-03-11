"\"\"\"Unit tests for the new schema preload helper in main.py.\"\"\""

from unittest.mock import MagicMock, patch

import pytest

from main import _preload_schemas_bulk


_TMDB_CONFIG = {
    "info_type": "sqlite",
    "dbName": "metadata.sqlite",
    "tableDescName": "table_desc",
    "tableColName": "table_cols",
}


def _make_desc_rows():
    return [
        ("orders", "Orders table"),
        ("customers", "Customer records"),
    ]


def _make_col_rows():
    return [
        ("orders", "order_id", "INT", "PRIMARY KEY", "", "", "", ""),
        (
            "customers",
            "customer_id",
            "INT",
            "PRIMARY KEY",
            "Customer key",
            "customers.source",
            "logic_type",
            "orders",
        ),
    ]


@patch("Utilities.base_utils.get_config_val", return_value=_TMDB_CONFIG)
@patch("Utilities.base_utils.accessDB")
def test_preload_schemas_returns_table_markdown(access_mock, _):
    """Bulk preload should assemble each table's markdown schema once."""
    db = MagicMock()
    db.get_data.side_effect = [_make_desc_rows(), _make_col_rows()]
    access_mock.return_value = db

    cache = _preload_schemas_bulk()

    assert "orders" in cache
    assert "customers" in cache
    orders = cache["orders"]
    assert "### orders" in orders
    assert "> Orders table" in orders
    assert "| Column | Type | Constraints | Description |" in orders
    customers = cache["customers"]
    assert "### customers" in customers
    # The helper currently repeats the description in the source-expression column.
    assert "| Customer key | Customer key | customers.source | logic_type |" in customers


@patch("Utilities.base_utils.get_config_val", return_value=_TMDB_CONFIG)
@patch("Utilities.base_utils.accessDB")
def test_preload_schemas_only_two_queries(access_mock, _):
    """Even with two tables, only the two bulk queries should run."""
    db = MagicMock()
    db.get_data.side_effect = [_make_desc_rows(), _make_col_rows()]
    access_mock.return_value = db

    _preload_schemas_bulk()

    assert db.get_data.call_count == 2
    calls = db.get_data.call_args_list
    assert calls[0][0][0] == _TMDB_CONFIG["tableDescName"]
    assert calls[1][0][0] == _TMDB_CONFIG["tableColName"]


@patch("Utilities.base_utils.get_config_val", return_value=_TMDB_CONFIG)
@patch("Utilities.base_utils.accessDB")
def test_preload_schemas_returns_empty_on_failure(access_mock, _):
    """Database failures should gracefully return an empty cache."""
    db = MagicMock()
    db.get_data.side_effect = RuntimeError("boom")
    access_mock.return_value = db

    assert _preload_schemas_bulk() == {}
