"""
Abstract base class for the metadata store layer.

Any concrete implementation (SQLite, Postgres, etc.) must subclass
BaseMetadataStore and implement all abstract methods. This allows
swapping the storage backend without touching any caller code.
"""

from abc import ABC, abstractmethod


class BaseMetadataStore(ABC):

    @abstractmethod
    def create_table(self, tableSchema: dict) -> None:
        """
        Create a table if it does not already exist.

        Args:
            tableSchema (dict): Schema definition with keys:
                - 'tableName' (str): Name of the table.
                - 'columns' (dict): Mapping of column name → list of SQL modifiers,
                  e.g. {'id': ['TEXT', 'PRIMARY KEY'], 'val': ['TEXT', '']}.
        """
        ...

    @abstractmethod
    def get_data(self, tableName: str, lookupDict: dict, lookupVal: list,
                 fetchtype: str = "one"):
        """
        Retrieve one or many rows from a table.

        Args:
            tableName (str): Target table.
            lookupDict (dict): Column → value filter pairs (WHERE clause).
                               Pass an empty dict to return all rows.
            lookupVal (list): Columns to SELECT. Pass an empty list for '*'.
            fetchtype (str): 'one' returns a single tuple; 'all' returns a list.

        Returns:
            tuple | list | None
        """
        ...

    @abstractmethod
    def post_data(self, tableName: str, insertlist: list) -> None:
        """
        Insert one or more rows into a table.

        Args:
            tableName (str): Target table.
            insertlist (list[dict]): Each dict maps column name → value.
        """
        ...

    @abstractmethod
    def update_data(self, tableName: str, matchVal: dict, updateVal: dict) -> None:
        """
        Update rows in a table.

        Args:
            tableName (str): Target table.
            matchVal (dict): Column → value pairs for the WHERE clause.
            updateVal (dict): Column → value pairs to SET.
        """
        ...

    @abstractmethod
    def delete_data(self, tableName: str, lookupDict: dict) -> None:
        """
        Delete rows from a table.

        Args:
            tableName (str): Target table.
            lookupDict (dict): Column → value pairs for the WHERE clause.
                               Pass an empty dict to delete all rows.
        """
        ...
