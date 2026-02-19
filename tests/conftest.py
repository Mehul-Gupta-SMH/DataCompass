"""
conftest.py — pre-mock heavy ML packages so the test suite runs in CI
without installing torch, sentence-transformers, FlagEmbedding, or chromadb.

These libraries are only needed at runtime when actual models are loaded.
All tests mock the classes/functions that use them, so the modules just
need to be importable, not functional.
"""
import sys
from unittest.mock import MagicMock

_HEAVY_MODULES = [
    "FlagEmbedding",
    "sentence_transformers",
    "torch",
    "chromadb",
    "chromadb.api",
    "chromadb.api.types",
    "chromadb.config",
    "pyvis",
    "pyvis.network",
]

for _mod in _HEAVY_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()
