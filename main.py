import logging

from APIManager.AllAPICaller import CallLLMApi
from APIManager.PromptBuilder import PromptBuilder
from SQLBuilderComponents import SQLBuilderSupport

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
    context = getRelevantContext(userQuery)

    schema_str = PromptBuilder.format_schema(context)
    prompt = PromptBuilder('generate sql').build({'SCHEMA': schema_str})

    logger.debug("Prompt sent to LLM:\n%s", prompt)

    LLMObj = CallLLMApi(LLMservice)
    return LLMObj.CallService(prompt)


query = """
Which products have the highest sales revenue and which products have the lowest sales revenue over the past year?
"""

print(generateQuery(query, "open_ai"))
