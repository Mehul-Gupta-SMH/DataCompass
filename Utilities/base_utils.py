# --------------------------------------------------------------------
# Import Library
# --------------------------------------------------------------------
import ast
import pathlib
import re
import yaml
import os
import functools
import logging
import sqlite3
import time
import inspect
import hashlib

# Resolved once at import time — all paths derive from here
_UTILS_DIR = pathlib.Path(__file__).parent
PROJECT_ROOT = _UTILS_DIR.parent
_CONFIG_FILE = _UTILS_DIR / "config.yaml"

from Utilities.store_interface import BaseMetadataStore

class TableCreateError(Exception):
    pass

# Only allow plain identifiers — no spaces, quotes, or SQL metacharacters
_IDENTIFIER_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

def _validate_identifier(name: str) -> None:
    """Raise ValueError if name is not a safe SQL identifier."""
    if name != "*" and not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Unsafe SQL identifier: {name!r}")


@functools.lru_cache(maxsize=None)
def _load_yaml(path: str) -> dict:
    """Load and cache a YAML file by absolute path string."""
    with open(path, "r") as f:
        return yaml.load(f, yaml.FullLoader)


# --------------------------------------------------------------------
def get_config_val(config_type: str, key_list: list, get_all=False) -> str:
    """
    Retrieve a configuration value from a YAML configuration file based on the provided configuration type and keys.

    args:
        - config_type (str): The type of configuration to retrieve.
        - *args (str): Variable length argument list of keys to navigate through the configuration.

    returns:
        - str: The value corresponding to the specified configuration type and keys.

    raises:
        - KeyError: If the provided configuration type is not found in the configuration file.
        - AttributeError: If unable to resolve the configuration value from the list of keys provided.

    """
    config_map = _load_yaml(str(_CONFIG_FILE))

    if config_type not in config_map.keys():
        raise KeyError(f"{config_type} : Config Type not Correct")

    sub_config_path = pathlib.Path(config_map[config_type])
    if not sub_config_path.is_absolute():
        sub_config_path = _UTILS_DIR / sub_config_path

    config_val = _load_yaml(str(sub_config_path))

    for key_val in key_list:
        try:
            config_val = config_val[key_val]
        except (KeyError, TypeError):
            raise KeyError(f"Key Value incorrect {key_val}")

    if isinstance(config_val, dict) and get_all == False:
        raise AttributeError("Incomplete Key List : Unable to resolve config value from list of keys provided")

    return config_val

# --------------------------------------------------------------------

def log_function(func):
    """
    Decorator function to log the inputs, outputs, and exceptions of a function.

    Input:
    - func (callable): The function to be decorated.

    Output:
    - callable: The decorated function.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Log function inputs
        logging.info(f"'{func.__name__}'|{time.time()}|Start||")

        try:
            # Execute the function
            result = func(*args, **kwargs)

            # Log function output
            logging.info(f"'{func.__name__}'|{time.time()}|Sucess||")
            return result

        except Exception as e:
            # Log exceptions
            logging.error(f"'{func.__name__}'|{time.time()}|Error|ErrorMessage{str(e)}|Args:{args} , Kwargs:{kwargs}")

    return wrapper

# --------------------------------------------------------------------
class accessDB(BaseMetadataStore):
    def __init__(self, info_type: str, db_name: str):
        """
        Initializes an instance of AccessDB class.

        Args:
            info_type (str): Type of information (e.g., 'cache', 'table metadata').
            db_name (str): Name of the SQLite database.
        """
        # Construct database file path
        base_path = get_config_val('database_config', ['database', 'base_path'])
        directory = os.path.join(base_path, info_type)
        if not os.path.exists(directory):
            os.makedirs(directory)

        dbconnection = os.path.join(directory,f"{db_name}.db")

        # Connect to the SQLite database
        self.connection = sqlite3.connect(dbconnection)
        self.cursor = self.connection.cursor()

    def create_table(self, tableSchema: dict):
        """
        Create a table in the SQLite database.

        Args:
            table_schema (dict): Dictionary containing table schema information.
        """
        tableName = tableSchema['tableName']
        _validate_identifier(tableName)

        # Construct column definitions
        collist = []
        for col, md in tableSchema['columns'].items():
            _validate_identifier(col)
            collist.append(col + " " + " ".join(md))

        # Construct table creation query
        tableCreateQuery = f'''
            CREATE TABLE IF NOT EXISTS {tableName} (
                {", ".join(collist)}
            )
        '''


        # Execute the table creation query
        try:
            self.cursor.execute(tableCreateQuery)
        except Exception as e:
            raise TableCreateError(f"""
            Tried creating table {tableName}
            Encountered Error : {str(e)}
            """)

        self.connection.commit()


    def get_data(self, tableName: str, lookupDict: dict, lookupVal: list, fetchtype = "one"):
        """
        Retrieve data from the SQLite database.

        Args:
            table_name (str): Name of the table.
            lookup_dict (dict): Dictionary containing lookup column-value pairs for filtering data (default: None).
            lookup_val (list): List of column names to retrieve (default: None).
            fetch_type (str): Type of fetch operation, 'one' or 'all' (default: 'one').

        Returns:
            tuple or list: Retrieved data.
        """
        _validate_identifier(tableName)

        if not len(lookupVal):
            lookupVal = ["*",]

        for col in lookupVal:
            _validate_identifier(col)

        if not len(lookupDict):
            self.cursor.execute(f'SELECT {", ".join(lookupVal)} FROM {tableName}')

        else:
            for col in lookupDict:
                _validate_identifier(col)

            conditions = " AND ".join(f"lower({col}) = lower(?)" for col in lookupDict)
            values = tuple(str(v) for v in lookupDict.values())
            self.cursor.execute(
                f'SELECT {", ".join(lookupVal)} FROM {tableName} WHERE {conditions}',
                values
            )

        if fetchtype == "one":
            return self.cursor.fetchone()
        else:
            return self.cursor.fetchall()

    def post_data(self, tableName: str, insertlist: list[dict[str,str]]) -> None:
        """
        Insert data into the SQLite database.

        Args:
            table_name (str): Name of the table.
            insert_list (list): List of dictionaries containing data to insert.
        """
        _validate_identifier(tableName)
        for records_dict in insertlist:
            for col in records_dict:
                _validate_identifier(col)
            colList = records_dict.keys()
            placehldr = ",".join(["?"]*len(records_dict.keys()))
            colval = tuple(map(str,records_dict.values()))
            self.cursor.execute(f'Insert into {tableName}(`{"`, `".join(colList)}`) values ({placehldr})', colval)

        self.connection.commit()


    def update_data(self, tableName: str, matchVal: dict[str,str], updateVal: dict[str,str]) -> None:
        """
        Update data in the SQLite database.

        Args:
            tableName (str): Name of the table to update.
            matchVal (dict): Dictionary containing column-value pairs for matching rows.
            updateVal (dict): Dictionary containing column-value pairs to update.

        Raises:
            ValueError: If update values are not provided.
        """
        if not len(updateVal):
            raise ValueError("Update values not provided")

        _validate_identifier(tableName)
        for col in updateVal:
            _validate_identifier(col)
        for col in matchVal:
            _validate_identifier(col)

        set_clause = ", ".join(f"{col} = ?" for col in updateVal)
        set_values = tuple(str(v) for v in updateVal.values())

        if len(matchVal):
            where_clause = " AND ".join(f"{col} = ?" for col in matchVal)
            where_values = tuple(str(v) for v in matchVal.values())
            self.cursor.execute(
                f'UPDATE {tableName} SET {set_clause} WHERE {where_clause}',
                set_values + where_values
            )
        else:
            self.cursor.execute(
                f'UPDATE {tableName} SET {set_clause}',
                set_values
            )

        self.connection.commit()


    def delete_data(self, tableName: str, lookupDict: dict):
        """
        Placeholder method for deleting data from the SQLite database.
        """
        _validate_identifier(tableName)
        for col in lookupDict:
            _validate_identifier(col)

        if len(lookupDict):
            where_clause = " AND ".join(f"{col} = ?" for col in lookupDict)
            values = tuple(str(v) for v in lookupDict.values())
            self.cursor.execute(f'DELETE FROM {tableName} WHERE {where_clause}', values)
        else:
            self.cursor.execute(f'DELETE FROM {tableName}')

        self.connection.commit()


# --------------------------------------------------------------------

class cachefunc:
    def __init__(self):
        """
        Initializes an instance of cachefunc class.
        """
        # Establish connection to the SQLite database
        self.info_type = "cache"
        self.dbName = "memoize"
        self.DBObj = accessDB(self.info_type, self.dbName)
        self.table_schema = {
            'tableName' : 'cache',
            'columns' : {
                'key': ['TEXT', 'PRIMARY KEY'],
                'value': ['TEXT', '']
            }
        }

    def create_cache_table(self):
        """
        Creates the cache table if it doesn't already exist.
        """
        self.DBObj.create_table(self.table_schema)

    def memoize(self, func):
        """
        Memoization decorator function.

        Args:
            func (function): The function to be memoized.

        Returns:
            function: The wrapper function for memoization.
        """

        def wrapper(*args, **kwargs):
            # Create cache table of not exists
            self.create_cache_table()
            # Get module and file path of the function
            module = inspect.getmodule(func)
            file_path = module.__file__ if module else ''
            # Create a unique key based on file path, function name, arguments, and keyword arguments
            key = (file_path, func.__qualname__, args[1:], str(kwargs))
            key = str(key).encode('utf-8')

            hasher = hashlib.sha256()
            hasher.update(key)
            key = hasher.hexdigest()

            # Check if the key exists in the cache table
            result = self.DBObj.get_data(self.table_schema["tableName"], {"key": str(key)}, ["value"])

            if result is not None:
                # Return the cached result if found
                try:
                    return ast.literal_eval(result[0])
                except (ValueError, SyntaxError):
                    return result[0]
            else:
                # Call the original function if the result is not in the cache
                result = func(*args, **kwargs)
                # Insert the result into the cache table

                vals_list = [
                    {
                        "key": str(key),
                        "value": str(result)
                    }
                ]
                self.DBObj.post_data(self.table_schema["tableName"], vals_list)

                return result

        return wrapper

    def close(self):
        """
        Closes the database connection.
        """
        self.DBObj.connection.close()

# --------------------------------------------------------------------