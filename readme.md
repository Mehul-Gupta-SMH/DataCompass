# To be updated

-----

# SQL Query Generator

## Overview

The SQL Query Generator is a Python-based tool designed to automate the creation of SQL queries based on user input questions. By analyzing the user's question, the tool identifies the relevant tables and generates the appropriate SQL query. This tool helps developers and data analysts quickly generate SQL queries without manually writing complex SQL code, ensuring consistency and saving time.

## Features

- **Natural Language Processing (NLP)**: Understands user questions to determine relevant tables and columns.
- **Automated SQL Query Generation**: Generate SELECT, INSERT, UPDATE, and DELETE queries automatically.
- **Supports Multiple SQL Dialects**: Compatible with major SQL databases (MySQL, PostgreSQL, SQLite, etc.).
- **Customizable Queries**: Easily customize the generated queries to suit specific requirements.
- **Command Line Interface (CLI)**: Simple and intuitive CLI for generating queries.
- **Extensible**: Easy to extend and add support for additional SQL features or databases.

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [Examples](#examples)
- [Configuration](#configuration)
- [Contributing](#contributing)
- [License](#license)

## Installation

### Prerequisites

- Python 3.7+
- pip (Python package installer)

### Steps

1. Clone the repository:
    ```bash
    git clone https://github.com/Mehul-Gupta-SMH/SQLCoder.git
    cd SQLCoder
    ```

2. Install the required packages:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

The SQL Query Generator can be used via its command line interface (CLI) or integrated into other Python scripts.

### CLI Usage

1. Generate a SELECT query:
    ```bash
    python generate_sql.py "Show me all users"
    ```

2. Generate an INSERT query:
    ```bash
    python generate_sql.py "Add a new user with id, name, and email"
    ```

3. Generate an UPDATE query:
    ```bash
    python generate_sql.py "Update the email of the user with id 1"
    ```

4. Generate a DELETE query:
    ```bash
    python generate_sql.py "Delete the user with id 1"
    ```

### Script Integration

You can import the SQL Query Generator into your Python scripts:

```python
from sql_query_generator import SQLQueryGenerator

# Initialize with table metadata
metadata = {
    'users': {
        'columns': ['id', 'name', 'email', 'created_at'],
        'primary_key': 'id'
    }
}

# Create an instance of the generator
generator = SQLQueryGenerator(metadata)

# Generate a SELECT query from user question
question = "Show me all users"
select_query = generator.generate_query_from_question(question)
print(select_query)
```

## Examples

### Generating a SELECT Query

```bash
python generate_sql.py "Show me all users"
```

Output:
```sql
SELECT id, name, email, created_at FROM users;
```

### Generating an INSERT Query

```bash
python generate_sql.py "Add a new user with id, name, and email"
```

Output:
```sql
INSERT INTO users (id, name, email) VALUES (?, ?, ?);
```

### Generating an UPDATE Query

```bash
python generate_sql.py "Update the email of the user with id 1"
```

Output:
```sql
UPDATE users SET email = ? WHERE id = 1;
```

### Generating a DELETE Query

```bash
python generate_sql.py "Delete the user with id 1"
```

Output:
```sql
DELETE FROM users WHERE id = 1;
```

## Configuration

You can configure the SQL Query Generator by modifying the `config.json` file. This file contains database-specific settings and query customization options.

Example `config.json`:

```json
{
    "database": "mysql",
    "placeholders": {
        "mysql": "?",
        "postgresql": "$1",
        "sqlite": "?"
    }
}
```

## Contributing

We welcome contributions! Please read the [CONTRIBUTING.md](CONTRIBUTING.md) file for guidelines on how to get started.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.

---

Happy coding! If you have any questions or need further assistance, feel free to open an issue or contact us directly.