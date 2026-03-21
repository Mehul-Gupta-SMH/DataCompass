"""
tests/test_ingestion.py — C4: database.schema.table qualified name support

Covers parse_pipeline() for:
  - Bare table names (regression: existing behaviour unchanged)
  - Two-part names  (schema.table)
  - Three-part names (database.schema.table)
  - Backtick-quoted qualified names
  - Double-quoted qualified names
  - Bracket-quoted qualified names  (SQL Server style)
  - Mixed-case qualified names
  - Source tables in FROM + JOIN clauses with qualified names
  - CTAS (CREATE TABLE AS SELECT) with qualified target
"""

import pytest
from backend.ingestion import parse_pipeline


# ---------------------------------------------------------------------------
# INSERT INTO … SELECT  — target table
# ---------------------------------------------------------------------------

class TestInsertIntoTarget:

    def test_bare_name(self):
        sql = "INSERT INTO orders (id, total) SELECT id, total FROM raw_orders"
        result = parse_pipeline(sql)
        assert result["target_table"] == "orders"

    def test_two_part_name(self):
        sql = "INSERT INTO sales.orders (id, total) SELECT id, total FROM raw_orders"
        result = parse_pipeline(sql)
        assert result["target_table"] == "sales.orders"

    def test_three_part_name(self):
        sql = "INSERT INTO prod.sales.orders (id, total) SELECT id, total FROM raw_orders"
        result = parse_pipeline(sql)
        assert result["target_table"] == "prod.sales.orders"

    def test_backtick_quoted(self):
        sql = "INSERT INTO `prod.sales.orders` (id, total) SELECT id, total FROM raw_orders"
        result = parse_pipeline(sql)
        assert result["target_table"] == "prod.sales.orders"

    def test_double_quoted(self):
        sql = 'INSERT INTO "prod.sales.orders" (id, total) SELECT id, total FROM raw_orders'
        result = parse_pipeline(sql)
        assert result["target_table"] == "prod.sales.orders"

    def test_bracket_quoted(self):
        sql = "INSERT INTO [prod.sales.orders] (id, total) SELECT id, total FROM raw_orders"
        result = parse_pipeline(sql)
        assert result["target_table"] == "prod.sales.orders"

    def test_mixed_case_preserved(self):
        sql = "INSERT INTO Prod.Sales.Orders (id) SELECT id FROM src"
        result = parse_pipeline(sql)
        assert result["target_table"] == "Prod.Sales.Orders"

    def test_column_mappings_still_parsed(self):
        sql = "INSERT INTO db.schema.tgt (a, b) SELECT x, y FROM db.schema.src"
        result = parse_pipeline(sql)
        assert len(result["column_mappings"]) == 2
        assert result["column_mappings"][0]["target"] == "a"
        assert result["column_mappings"][1]["target"] == "b"


# ---------------------------------------------------------------------------
# CREATE TABLE AS SELECT  — target table
# ---------------------------------------------------------------------------

class TestCTASTarget:

    def test_bare_name(self):
        sql = "CREATE TABLE summary AS SELECT id, total FROM orders"
        result = parse_pipeline(sql)
        assert result["target_table"] == "summary"

    def test_two_part_name(self):
        sql = "CREATE TABLE analytics.summary AS SELECT id FROM orders"
        result = parse_pipeline(sql)
        assert result["target_table"] == "analytics.summary"

    def test_three_part_name(self):
        sql = "CREATE TABLE prod.analytics.summary AS SELECT id FROM prod.sales.orders"
        result = parse_pipeline(sql)
        assert result["target_table"] == "prod.analytics.summary"

    def test_if_not_exists(self):
        sql = "CREATE TABLE IF NOT EXISTS dw.marts.summary AS SELECT id FROM src"
        result = parse_pipeline(sql)
        assert result["target_table"] == "dw.marts.summary"

    def test_backtick_quoted(self):
        sql = "CREATE TABLE `dw.marts.summary` AS SELECT id FROM src"
        result = parse_pipeline(sql)
        assert result["target_table"] == "dw.marts.summary"


# ---------------------------------------------------------------------------
# Source tables in FROM / JOIN clauses
# ---------------------------------------------------------------------------

class TestSourceTables:

    def test_bare_source(self):
        sql = "INSERT INTO tgt (id) SELECT id FROM src"
        result = parse_pipeline(sql)
        assert result["source_tables"] == ["src"]

    def test_two_part_source(self):
        sql = "INSERT INTO tgt (id) SELECT id FROM raw.orders"
        result = parse_pipeline(sql)
        assert "raw.orders" in result["source_tables"]

    def test_three_part_source(self):
        sql = "INSERT INTO tgt (id) SELECT id FROM prod.raw.orders"
        result = parse_pipeline(sql)
        assert "prod.raw.orders" in result["source_tables"]

    def test_multiple_qualified_sources_via_join(self):
        sql = (
            "INSERT INTO tgt (a, b) "
            "SELECT o.a, c.b "
            "FROM prod.sales.orders o "
            "JOIN prod.crm.customers c ON o.cust_id = c.id"
        )
        result = parse_pipeline(sql)
        sources = result["source_tables"]
        assert "prod.sales.orders" in sources
        assert "prod.crm.customers" in sources

    def test_source_names_lowercased(self):
        """Source table names are normalised to lowercase."""
        sql = "INSERT INTO tgt (id) SELECT id FROM Prod.Sales.Orders"
        result = parse_pipeline(sql)
        assert "prod.sales.orders" in result["source_tables"]

    def test_backtick_quoted_source(self):
        sql = "INSERT INTO tgt (id) SELECT id FROM `prod.sales.orders`"
        result = parse_pipeline(sql)
        assert "prod.sales.orders" in result["source_tables"]

    def test_no_duplicate_sources(self):
        sql = (
            "INSERT INTO tgt (a) "
            "SELECT a FROM prod.raw.orders o1 "
            "JOIN prod.raw.orders o2 ON o1.id = o2.id"
        )
        result = parse_pipeline(sql)
        assert result["source_tables"].count("prod.raw.orders") == 1

    def test_sql_keywords_not_included_as_source(self):
        sql = "INSERT INTO tgt (id) SELECT id FROM prod.orders WHERE id > 1"
        result = parse_pipeline(sql)
        sources = result["source_tables"]
        for keyword in ("where", "and", "or", "select", "on"):
            assert keyword not in sources


# ---------------------------------------------------------------------------
# End-to-end: qualified names round-trip through parse_pipeline
# ---------------------------------------------------------------------------

class TestQualifiedNameEndToEnd:

    def test_three_part_target_and_sources(self):
        sql = (
            "INSERT INTO prod.marts.order_summary (order_id, customer_name, total) "
            "SELECT o.id, c.name, o.total "
            "FROM prod.raw.orders o "
            "JOIN prod.raw.customers c ON o.cust_id = c.id"
        )
        result = parse_pipeline(sql)
        assert result["target_table"] == "prod.marts.order_summary"
        assert "prod.raw.orders" in result["source_tables"]
        assert "prod.raw.customers" in result["source_tables"]
        assert len(result["column_mappings"]) == 3

    def test_ctas_three_part_with_qualified_source(self):
        sql = (
            "CREATE TABLE dw.gold.revenue_summary AS "
            "SELECT year, SUM(amount) AS total "
            "FROM dw.silver.transactions"
        )
        result = parse_pipeline(sql)
        assert result["target_table"] == "dw.gold.revenue_summary"
        assert "dw.silver.transactions" in result["source_tables"]

    def test_invalid_sql_still_raises(self):
        with pytest.raises(ValueError):
            parse_pipeline("SELECT * FROM orders")
