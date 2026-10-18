from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph

from agents.etl_analyst import etl_analyst
from agents.sql_analyst import sql_analyst
from Models.schema import DataAgentSchema, RouterSchema
from utils.llm_pick import pick_llm

llm = pick_llm("medium")

llm_router = llm.with_structured_output(RouterSchema)


# ---------------------------- DATA AGENT GRAPH ---------------------------- #


ROUTER_PROMPT = """
You are the router for a data assistant. Classify the user's CURRENT request into one route.

- "sql": questions answered by querying the company's PostgreSQL database. It holds
  ride-sharing business data in the tables users (riders and drivers), vehicles, rides,
  payments (amounts, payment methods, payment status), and ratings. Any question about
  these entities, counts, totals, averages, trends, or "what/which/how many" goes here.
- "etl": requests to extract data from an external HTTP API and save it to a file, or to
  transform a local CSV, JSON, or Parquet file (filter, select columns, sort, limit) and
  save the result.
- "chat": greetings, thanks, small talk, or questions about what this assistant can do.

If conversation history is included, use it only to understand follow-up requests such as
"what about 2026?". Classify the current request, not the earlier messages.

User input:
{message}
"""

CAPABILITIES = """
You can help with two kinds of work:
1. Answering questions about the ride-sharing database (users, drivers, vehicles, rides,
   payments, ratings) by running read-only SQL.
2. ETL: extracting data from an HTTP API into CSV/JSON/Parquet, and filtering, selecting,
   sorting, or limiting local data files.
"""


def router_node(state: DataAgentSchema):

    message = state.messages[-1].content

    route_response_dict = llm_router.invoke(
        ROUTER_PROMPT.format(message=message)
    ).model_dump()

    route_response = route_response_dict["answer"]

    return {"route_response": route_response}


def etl_node(state: DataAgentSchema):

    message = state.messages[-1].content

    response = etl_analyst.invoke(
        {
            "messages": [
                HumanMessage(
                    content=f"""
            {message}
    """
                )
            ]
        }
    )
    final_message = response["messages"][-1]
    return {"messages": [final_message]}


def sql_node(state: DataAgentSchema):

    message = state.messages[-1].content

    input_schema = {
        "messages": [],
        "user_question": f"{message}",
        "curated_question": "",
        "prompt_query_context": "",
        "generated_sql_query": "",
        "is_safe": "No",
        "comments": "",
        "sql_query_execution_result": "",
        "final_answer": "",
    }

    response = sql_analyst.invoke(input_schema)

    final_message = response["messages"][-1]
    return {"messages": [final_message]}


def chat_node(state: DataAgentSchema):

    message = state.messages[-1].content

    prompt = f"""
You are Data Agent, a friendly data assistant. Reply briefly and naturally to the user.
If it fits, mention what you can do and suggest an example question.
{CAPABILITIES}
User input:
{message}
"""
    response = pick_llm("low").invoke(prompt).content
    return {"messages": [AIMessage(content=response)]}


data_agent_graph = StateGraph(DataAgentSchema)

data_agent_graph.add_node("router_node", router_node)
data_agent_graph.add_node("etl_node", etl_node)
data_agent_graph.add_node("sql_node", sql_node)
data_agent_graph.add_node("chat_node", chat_node)

data_agent_graph.add_edge(START, "router_node")


def route_edge(state: DataAgentSchema) -> str:
    if state.route_response == "sql":
        return "sql_node"
    elif state.route_response == "etl":
        return "etl_node"
    elif state.route_response == "chat":
        return "chat_node"
    else:
        raise ValueError(f"Invalid route response: {state.route_response}")


data_agent_graph.add_conditional_edges(
    "router_node",
    route_edge,
    {"sql_node": "sql_node", "etl_node": "etl_node", "chat_node": "chat_node"},
)
data_agent_graph.add_edge("chat_node", END)

data_agent = data_agent_graph.compile()
