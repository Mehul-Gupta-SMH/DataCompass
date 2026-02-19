import logging
import re

import sqlparse
import sqlparse.tokens as T

from APIManager.AllAPICaller import CallLLMApi
from APIManager.PromptBuilder import PromptBuilder
from SQLBuilderComponents import SQLBuilderSupport

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SQLValidationError(Exception):
    pass


_CODE_FENCE_RE = re.compile(r'```(?:sql)?\s*(.*?)\s*```', re.DOTALL | re.IGNORECASE)

_VALID_PROVIDERS = {"open_ai", "anthropic", "google", "groq"}
_MAX_QUERY_LENGTH = 2000


def _strip_code_fence(text: str) -> str:
    """Remove markdown code fences if the LLM wrapped the SQL in them."""
    match = _CODE_FENCE_RE.search(text)
    return match.group(1).strip() if match else text.strip()


def validate_sql(llm_output: str) -> str:
    """
    Validate that llm_output contains parseable SQL and return it cleaned.

    Strips markdown code fences, then checks that at least one token
    across all parsed statements is a DML (SELECT/INSERT/UPDATE/DELETE)
    or DDL (CREATE/DROP/ALTER) keyword.

    Raises SQLValidationError if no valid SQL is found.
    Returns the cleaned SQL string.
    """
    cleaned = _strip_code_fence(llm_output)

    statements = [s for s in sqlparse.parse(cleaned) if str(s).strip()]

    if not statements:
        raise SQLValidationError(
            f"LLM response is empty after stripping. Raw: {llm_output[:200]!r}"
        )

    for stmt in statements:
        for token in stmt.flatten():
            if token.ttype in (T.Keyword.DML, T.Keyword.DDL):
                return cleaned

    raise SQLValidationError(
        f"LLM response does not appear to contain valid SQL.\nRaw: {llm_output[:200]!r}"
    )


def getRelevantContext(user_query: str) -> dict:
    """
    Retrieves the schema context needed to build a SQL query for the given question.

    :param user_query: Natural language question from the user.
    :return: Dict containing user_query, table_list, and join_keys.
    """
    queryContext = SQLBuilderSupport()
    return queryContext.getBuildComponents(user_query)


def generateQuery(userQuery: str, LLMservice: str) -> str:
    """
    Generates a SQL query from a natural language question.

    :param userQuery: Natural language question from the user.
    :param LLMservice: LLM provider to use ('open_ai', 'anthropic', 'google', 'groq').
    :return: Generated SQL query string.
    """
    if not isinstance(userQuery, str) or not userQuery.strip():
        raise ValueError("userQuery must be a non-empty string.")
    if len(userQuery) > _MAX_QUERY_LENGTH:
        raise ValueError(
            f"userQuery exceeds maximum length of {_MAX_QUERY_LENGTH} characters "
            f"(got {len(userQuery)})."
        )
    if not isinstance(LLMservice, str) or LLMservice.lower() not in _VALID_PROVIDERS:
        raise ValueError(
            f"LLMservice must be one of {sorted(_VALID_PROVIDERS)}, got {LLMservice!r}."
        )

    context = getRelevantContext(userQuery)

    schema_str = PromptBuilder.format_schema(context)
    prompt = PromptBuilder('generate sql').build({'SCHEMA': schema_str})

    logger.debug("Prompt sent to LLM:\n%s", prompt)

    LLMObj = CallLLMApi(LLMservice)
    raw = LLMObj.CallService(prompt)

    logger.debug("Raw LLM response:\n%s", raw)

    return validate_sql(raw)


if __name__ == "__main__":
    query = """
    Which products have the highest sales revenue and which products have the lowest sales revenue over the past year?
    """
    print(generateQuery(query, "open_ai"))
