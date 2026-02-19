"""
Abstract base class for the vector store layer.

Any concrete implementation (ChromaDB, Pinecone, QDrant, etc.) must subclass
BaseVectorStore and implement all abstract methods. This allows swapping the
vector store backend without touching RAGPipeline or any other caller.
"""

from abc import ABC, abstractmethod


class BaseVectorStore(ABC):

    @abstractmethod
    def connect(self, sessions_args: dict, session_type: str = "local") -> None:
        """
        Establish a connection to the vector store.

        Args:
            sessions_args (dict): Connection parameters (e.g. path, host, port).
            session_type (str): 'local' for a local persistent store, 'hosted' for remote.
        """
        ...

    @abstractmethod
    def add_data(self, data: list, metadata: dict) -> str:
        """
        Upsert a list of embedding records into the store.

        Args:
            data (list): Each item is a dict with keys:
                         'documents', 'embedding', 'metadata', 'id'.
            metadata (dict): Collection-level metadata including 'collection_name'.

        Returns:
            str: Success message.
        """
        ...

    @abstractmethod
    def get_data(self, query_emb: list, metadata: dict) -> dict:
        """
        Query the store with an embedding vector and return nearest neighbours.

        Args:
            query_emb (list): Query embedding vector.
            metadata (dict): Must contain 'collection_name' and 'n_chunks'.

        Returns:
            dict: Raw query results from the backend (ids, documents, metadatas, distances).
        """
        ...
