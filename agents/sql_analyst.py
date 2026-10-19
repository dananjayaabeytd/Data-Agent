import logging
import os

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph

from Models.schema import AgentSchema, JudgeSchema
from utils.database import DatabaseUtil
from utils.llm_pick import pick_llm

LOGGER = logging.getLogger(__name__)


def database_config() -> dict:
    """Connection settings for the SQL agent, which must use the read-only analytics role.

    A read-only transaction blocks writes but not reads, so connecting as the owner role would
    let generated SQL read agent_sessions (every user's chats) or call pg_read_file.
    """
    required = ("host", "port", "user", "password", "database")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            f"Missing database environment variables: {', '.join(missing)}"
        )

    readonly_user = os.getenv("db_readonly_user")
    if not readonly_user or readonly_user == os.environ["user"]:
        message = (
            "The SQL agent is using the database owner role. Set db_readonly_user and "
            "db_readonly_password to a separate role (created automatically at startup)."
        )
        if os.getenv("APP_ENV", "development").lower() == "production":
            raise RuntimeError(message)
        LOGGER.warning(message)
        readonly_user, readonly_password = os.environ["user"], os.environ["password"]
    else:
        readonly_password = os.getenv("db_readonly_password", "")

    return {
        "host": os.environ["host"],
        "port": int(os.environ["port"]),
        "user": readonly_user,
        "password": readonly_password,
        "dbname": os.environ["database"],
    }


def curate_ques(state: AgentSchema) -> AgentSchema:

    user_question = state.user_question

    llm = pick_llm("low")

    prompt = f"""
    Rewrite the user's current request as one clear, standalone question about the database.
    Rules:
    - Do NOT answer the question and do NOT say whether data is available. Only rewrite it.
    - Keep every number, filter, threshold, limit, date, and sort order exactly as asked
      (for example "top 5", "at least 10 ratings", "in 2026").
    - If conversation history is included, use it only to resolve follow-up references such
      as "what about 2026?" or "those drivers". Ignore earlier questions that the current
      request does not refer to.
    - Return only the rewritten question, with no explanation.

    User input:
    {user_question}
    """

    response = llm.invoke(prompt).content

    return {
        "curated_question": response,
        "messages": [HumanMessage(content=response)],
    }


def prompt_query_context(state: AgentSchema) -> AgentSchema:

    curated_question = state.curated_question

    conn_details = database_config()

    obj = DatabaseUtil(conn_details)

    schema_info = obj.schema_details("public")

    # Constructing the prompt query for the agent to generate the SQL query
    prompt = f"""
    You are an SQL analyst agent. Your task is to convert the user's natural language 
    query into Postgres SQL query that can be executed on the database. You are provided 
    with the user's original query and the schema details of the database, including
    table names, column names, data types, and sample data for each table so that 
    you can understand the structure of the database and generate an accurate SQL query.

    Rules:
    - Row limits: if the question names a number ("top 5", "3 cities", "first five"),
      use exactly that LIMIT. If it asks for one extreme ("the highest", "which X has the
      most"), return a single row with MAX/MIN or LIMIT 1. A single aggregate over the
      whole question (COUNT, SUM, AVG, MAX) needs no LIMIT. Use LIMIT 10 only for
      open-ended lists that would otherwise return many rows.
    - Use only the tables the question needs. Do not join another table unless the
      question requires one of its columns: extra joins change counts and totals.
    - Filter on the column the question names (for example "requested" means
      requested_at, a ride's "fare" is rides.fare, payment amounts are payments.amount).
    - When grouping (per month, per city), include the grouping column in the SELECT.

    Note - Just generate the SQL query without any explanation or additional text because
    this query will be executed directly on the database. So, the output should be SQL
    ready to be executed without any modifications.  
    
    User's Original Query: {curated_question}

    Database Schema Details:
    {schema_info}
    
    """

    return {"prompt_query_context": prompt}


def generate_sql(state: AgentSchema) -> AgentSchema:

    prompt = state.prompt_query_context

    llm = pick_llm(
        "medium"
    )  # Pick the appropriate LLM based on the level of the question

    generated_sql_query = llm.invoke(
        prompt
    ).content  # Generate the SQL query using the LLM

    return {"generated_sql_query": generated_sql_query}


def is_safe_sql(state: AgentSchema) -> AgentSchema:

    sql_query = state.generated_sql_query

    llm = pick_llm("medium")
    llm_judge = llm.with_structured_output(JudgeSchema)

    prompt = f"""
    You are an SQL Judge for data security. Your task is to determine whether the SQL query is 
    safe or not. The SQL query should only be used for data retrieval and should not modify the 
    database in any way. Neither the SQL query nor the prompt should contain any SQL commands that can modify the
    database, such as INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, or any other commands that can change
    the structure or content of the database. If the SQL query is safe, respond with 'Yes' otherwise respond with 
    'No'. Additionally, provide comments explaining your decision.
    Here's the SQL query to evaluate:
    {sql_query}"""

    response = llm_judge.invoke(
        prompt
    ).model_dump()  # Get the structured output as a dictionary
    return {"is_safe": response["answer"], "comments": response["comments"]}


def canceled_sql(state: AgentSchema) -> AgentSchema:

    comments = state.comments

    final_answer = f"The generated SQL query was deemed unsafe to execute. The reason provided by the judge is: {comments}. Therefore, the SQL query will not be executed."
    return {"final_answer": final_answer, "messages": [AIMessage(content=final_answer)]}


def execute_sql(state: AgentSchema) -> AgentSchema:

    sql_query = state.generated_sql_query

    conn_details = database_config()

    obj = DatabaseUtil(conn_details)

    execution_result = obj.execute_sql(
        sql_query
    )  # Execute the SQL query on the database

    return {"sql_query_execution_result": execution_result}


def repair_sql(state: AgentSchema) -> AgentSchema:
    """Ask the model to fix a query that the database rejected, using the exact error."""

    llm = pick_llm("medium")

    prompt = f"""
    {state.prompt_query_context}

    The previous SQL query failed when it was executed on PostgreSQL.

    Failed query:
    {state.generated_sql_query}

    Database error:
    {state.sql_query_execution_result}

    Fix the query so it answers the user's question using only the tables and columns in the
    schema above. Return only the corrected SQL query.
    """

    return {
        "generated_sql_query": llm.invoke(prompt).content,
        "sql_repairs": state.sql_repairs + 1,
    }


def represent_final_answer(state: AgentSchema) -> AgentSchema:

    execution_result = state.sql_query_execution_result
    curated_question = state.curated_question

    llm = pick_llm("low")

    prompt = f"""
    You are an SQL analyst agent. Your task is to provide a final answer to the user based on the
    execution result of the SQL query and the user's original question. The final answer should be
    concise, clear, and directly address the user's query. Avoid including any SQL code or technical
    details in the final answer. The final answer should be in a user-friendly format that is easy to
    understand. If the execution result is empty or does not provide a clear answer to the user's question, explain this in the final answer. \n
    Here is the execution result: {execution_result} \n
    Here is the user's original question: {curated_question}
    """

    llm_response = llm.invoke(prompt).content  # Get the final answer from the LLM

    return {
        "final_answer": llm_response,
        "messages": [AIMessage(content=llm_response)],
    }


# ------------ Graph Building ------------

sql_agent_graph = StateGraph(AgentSchema)

# Nodes
sql_agent_graph.add_node(curate_ques, name="curate_ques")
sql_agent_graph.add_node(prompt_query_context, name="prompt_query_context")
sql_agent_graph.add_node(generate_sql, name="generate_sql")
sql_agent_graph.add_node(is_safe_sql, name="is_safe_sql")
sql_agent_graph.add_node(canceled_sql, name="canceled_sql")
sql_agent_graph.add_node(execute_sql, name="execute_sql")
sql_agent_graph.add_node(repair_sql, name="repair_sql")
sql_agent_graph.add_node(represent_final_answer, name="represent_final_answer")

# Edges
sql_agent_graph.add_edge(START, "curate_ques")
sql_agent_graph.add_edge("curate_ques", "prompt_query_context")
sql_agent_graph.add_edge("prompt_query_context", "generate_sql")
sql_agent_graph.add_edge("generate_sql", "is_safe_sql")


# Codintional Edge Function
def is_safe_sql_edge(state: AgentSchema) -> str:
    is_safe = state.is_safe

    if is_safe.lower() == "yes":
        return "execute_sql"

    else:
        return "canceled_sql"


sql_agent_graph.add_conditional_edges(
    "is_safe_sql",
    is_safe_sql_edge,
    {"execute_sql": "execute_sql", "canceled_sql": "canceled_sql"},
)


MAX_SQL_REPAIRS = 2


def needs_repair_edge(state: AgentSchema) -> str:
    # Only database errors are repaired. Validator rejections ("Rejected: ...") are a safety
    # decision, so they are never retried.
    failed = state.sql_query_execution_result.startswith("Error executing query")
    if failed and state.sql_repairs < MAX_SQL_REPAIRS:
        return "repair_sql"
    return "represent_final_answer"


sql_agent_graph.add_edge("canceled_sql", END)
sql_agent_graph.add_conditional_edges(
    "execute_sql",
    needs_repair_edge,
    {"repair_sql": "repair_sql", "represent_final_answer": "represent_final_answer"},
)
# A repaired query is judged again before it runs.
sql_agent_graph.add_edge("repair_sql", "is_safe_sql")
sql_agent_graph.add_edge("represent_final_answer", END)

# Compile the Graph
sql_analyst = sql_agent_graph.compile()
