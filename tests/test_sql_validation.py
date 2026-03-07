"""
Tests for validate_sql() and _strip_code_fence() in main.py.

No ML models, databases, or API keys required.
main.py is imported safely because module-level execution is guarded
by if __name__ == "__main__".
"""

import unittest

# conftest.py (loaded automatically by pytest) pre-mocks all heavy ML
# packages so main.py and its transitive imports can be imported here
# without torch, sentence-transformers, etc. being installed.
from main import validate_sql, _strip_code_fence, SQLValidationError


class TestStripCodeFence(unittest.TestCase):

    def test_plain_sql_unchanged(self):
        sql = "SELECT * FROM orders"
        self.assertEqual(_strip_code_fence(sql), sql)

    def test_strips_sql_fence(self):
        text = "```sql\nSELECT * FROM orders\n```"
        self.assertEqual(_strip_code_fence(text), "SELECT * FROM orders")

    def test_strips_plain_fence(self):
        text = "```\nSELECT 1\n```"
        self.assertEqual(_strip_code_fence(text), "SELECT 1")

    def test_strips_uppercase_sql_fence(self):
        text = "```SQL\nSELECT 1\n```"
        self.assertEqual(_strip_code_fence(text), "SELECT 1")

    def test_strips_surrounding_whitespace(self):
        text = "  SELECT * FROM orders  "
        self.assertEqual(_strip_code_fence(text), "SELECT * FROM orders")


class TestValidateSql(unittest.TestCase):

    def test_valid_select(self):
        result = validate_sql("SELECT * FROM orders")
        self.assertEqual(result["content"], "SELECT * FROM orders")

    def test_valid_select_in_code_fence(self):
        result = validate_sql("```sql\nSELECT id FROM users WHERE active = 1\n```")
        self.assertEqual(result["content"], "SELECT id FROM users WHERE active = 1")

    def test_valid_insert(self):
        result = validate_sql("INSERT INTO orders (id) VALUES (1)")
        self.assertIn("INSERT", result["content"])

    def test_valid_update(self):
        result = validate_sql("UPDATE orders SET status = 'done' WHERE id = 1")
        self.assertIn("UPDATE", result["content"])

    def test_valid_delete(self):
        result = validate_sql("DELETE FROM orders WHERE id = 1")
        self.assertIn("DELETE", result["content"])

    def test_valid_create(self):
        result = validate_sql("CREATE TABLE foo (id INT)")
        self.assertIn("CREATE", result["content"])

    def test_valid_cte(self):
        sql = "WITH cte AS (SELECT 1 AS n) SELECT n FROM cte"
        result = validate_sql(sql)
        self.assertEqual(result["content"], sql)

    def test_raises_on_empty_string(self):
        with self.assertRaises(SQLValidationError):
            validate_sql("")

    def test_raises_on_whitespace_only(self):
        with self.assertRaises(SQLValidationError):
            validate_sql("   \n  ")

    def test_raises_on_plain_text(self):
        with self.assertRaises(SQLValidationError):
            validate_sql("I cannot generate SQL for this query.")

    def test_raises_on_llm_apology(self):
        with self.assertRaises(SQLValidationError):
            validate_sql("Sorry, I don't have enough context to generate a SQL query.")

    def test_error_message_includes_raw_response(self):
        raw = "this is not sql"
        with self.assertRaises(SQLValidationError) as ctx:
            validate_sql(raw)
        self.assertIn(raw, str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
