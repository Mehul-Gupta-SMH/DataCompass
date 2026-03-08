"""
Tests for APIManager.PromptBuilder.

Covers format_schema() and build() without any ML models or live databases.
"""

import unittest
from unittest.mock import patch, mock_open

from APIManager.PromptBuilder import PromptBuilder, UnidentifiedPromptType, MissingPromptParams


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_CONTEXT = {
    "user_query": "Show me all orders",
    "table_list": {
        "direct": {
            "orders": {
                "description": "All customer orders",
                "columns": [
                    ("order_id", "INT", "PRIMARY KEY", "Unique order ID"),
                    ("customer_id", "INT", "FOREIGN KEY", "FK to customers"),
                ]
            }
        },
        "intermediate": {}
    },
    "join_keys": []
}

CONTEXT_WITH_JOINS = {
    "user_query": "List orders with customer names",
    "table_list": {
        "direct": {
            "orders": {
                "description": "Order records",
                "columns": [("order_id", "INT", "PRIMARY KEY", "Order ID")]
            }
        },
        "intermediate": {
            "customers": {
                "description": "Customer info",
                "columns": [("customer_id", "INT", "PRIMARY KEY", "Customer ID")]
            }
        }
    },
    "join_keys": [
        {
            "source": "orders",
            "target": "customers",
            "edge_attributes": {"JoinKeys": "orders.customer_id = customers.customer_id"},
            "node1_attributes": {},
            "node2_attributes": {}
        }
    ]
}


# ---------------------------------------------------------------------------
# format_schema tests
# ---------------------------------------------------------------------------

class TestFormatSchema(unittest.TestCase):

    def test_includes_user_question(self):
        result = PromptBuilder.format_schema(MINIMAL_CONTEXT)
        self.assertIn("Show me all orders", result)

    def test_includes_table_name(self):
        result = PromptBuilder.format_schema(MINIMAL_CONTEXT)
        self.assertIn("orders", result)

    def test_includes_direct_label(self):
        result = PromptBuilder.format_schema(MINIMAL_CONTEXT)
        self.assertIn("[direct]", result)

    def test_includes_intermediate_label(self):
        result = PromptBuilder.format_schema(CONTEXT_WITH_JOINS)
        self.assertIn("[intermediate]", result)

    def test_includes_table_description(self):
        result = PromptBuilder.format_schema(MINIMAL_CONTEXT)
        self.assertIn("All customer orders", result)

    def test_includes_column_names(self):
        result = PromptBuilder.format_schema(MINIMAL_CONTEXT)
        self.assertIn("order_id", result)
        self.assertIn("customer_id", result)

    def test_includes_column_types(self):
        result = PromptBuilder.format_schema(MINIMAL_CONTEXT)
        self.assertIn("INT", result)

    def test_includes_column_constraints(self):
        result = PromptBuilder.format_schema(MINIMAL_CONTEXT)
        self.assertIn("PRIMARY KEY", result)

    def test_join_paths_section_present(self):
        result = PromptBuilder.format_schema(CONTEXT_WITH_JOINS)
        self.assertIn("## Join Paths", result)

    def test_join_path_content(self):
        result = PromptBuilder.format_schema(CONTEXT_WITH_JOINS)
        self.assertIn("orders → customers", result)
        self.assertIn("orders.customer_id = customers.customer_id", result)

    def test_no_join_section_when_empty(self):
        result = PromptBuilder.format_schema(MINIMAL_CONTEXT)
        self.assertNotIn("## Join Paths", result)

    def test_description_as_tuple_is_unwrapped(self):
        ctx = {
            "user_query": "q",
            "table_list": {"direct": {"t": {"description": ("desc text",), "columns": []}}, "intermediate": {}},
            "join_keys": []
        }
        result = PromptBuilder.format_schema(ctx)
        self.assertIn("desc text", result)


# ---------------------------------------------------------------------------
# build() tests
# ---------------------------------------------------------------------------

FAKE_TEMPLATE = "You are an expert.\n<<SCHEMA>>\nRules."

class TestBuild(unittest.TestCase):

    def _make_builder_with_mock(self, prompt_type, expected_params, template_str):
        """Return a PromptBuilder whose file read is mocked."""
        builder = PromptBuilder(prompt_type)
        builder.prompt_template_str = template_str
        builder.expected_params = expected_params
        return builder

    @patch("builtins.open", mock_open(read_data=FAKE_TEMPLATE))
    def test_build_replaces_placeholder(self):
        result = PromptBuilder("generate sql").build({"CONVERSATION": "", "SCHEMA": "my schema"})
        self.assertIn("my schema", result)
        self.assertNotIn("<<SCHEMA>>", result)

    @patch("builtins.open", mock_open(read_data=FAKE_TEMPLATE))
    def test_build_raises_on_wrong_params(self):
        with self.assertRaises(MissingPromptParams):
            PromptBuilder("generate sql").build({"WRONG_KEY": "val"})

    def test_build_raises_on_unknown_type(self):
        with self.assertRaises(UnidentifiedPromptType):
            PromptBuilder("nonexistent type").build({})


if __name__ == "__main__":
    unittest.main()
