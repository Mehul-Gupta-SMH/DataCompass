
from APIManager.AllAPICaller import CallLLMApi
from SQLBuilderComponents import SQLBuilderSupport


def getRelevantContext(user_query: str):
    """
    Retrieves the context for building the query based on the question bu user

    :param user_query: question by user for which query is to be generated
    :return: JSON object containing context for building thq SQL query
    """
    queryContext = SQLBuilderSupport()
    return queryContext.getBuildComponents(user_query)




def generateQuery(userQuery: str, LLMservice: str):
    """

    :param userQuery:
    :param LLMservice:
    :return:
    """

    ContextJson_str = getRelevantContext(userQuery)

    prompt = f"""
    Using the context provided below, write a SQL query.
    {ContextJson_str}
    """

    print(prompt)

    LLMObj = CallLLMApi(LLMservice)

    return LLMObj.CallService(prompt)


query = """The Pricing Team wants to know for each currently offered product how their unit price compares against their categories average and median unit price. In order to help them they asked you to provide them a list of products with:

their category name
their product name
their unit price
their category average unit price (formatted to have only 2 decimals)
their category median unit price (formatted to have only 2 decimals)
their position against the category average unit price as:
“Below Average”
“Equal Average”
“Over Average”
their position against the category median unit price as:
“Below Median”
“Equal Median”
“Over Median”
Filtered on the following conditions:

They are not discontinued
Finally order the results by category name then product name (both ascending).
"""

print(generateQuery(query, "google"))