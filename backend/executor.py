from sqlalchemy import create_engine, text


def execute_query(sql: str, query_type: str, connection_string: str):
    """
    Execute a SQL or Spark SQL query via SQLAlchemy.

    Args:
        sql: The query string to execute.
        query_type: "sql" or "spark_sql" (dataframe_api is not supported).
        connection_string: SQLAlchemy-compatible connection string.

    Returns:
        Tuple of (columns: list[str], rows: list[list]).

    Raises:
        ValueError: For empty inputs.
        SQLAlchemy errors: Re-raised for the endpoint to handle.
    """
    if not sql or not sql.strip():
        raise ValueError("sql must be a non-empty string.")
    if not connection_string or not connection_string.strip():
        raise ValueError("connection_string must be a non-empty string.")

    engine = create_engine(connection_string, pool_pre_ping=True)

    with engine.connect() as conn:
        result = conn.execute(text(sql))
        columns = list(result.keys())
        rows = [list(row) for row in result.fetchmany(500)]

    return columns, rows
