import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langchain_core.messages import HumanMessage
from langgraph.graph import START, StateGraph

from agents.etl_analyst import etl_analyst
from agents.sql_analyst import sql_analyst
from Models.schema import DataAgentSchema, RouterSchema
from utils.llm_pick import pick_llm

llm = pick_llm("medium")

llm_router = llm.with_structured_output(RouterSchema)


# ---------------------------- DATA AGENT GRAPH ---------------------------- #


def router_node(state: DataAgentSchema):

    message = state.messages[-1].content

    route_response_dict = llm_router.invoke(message).model_dump()

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


data_agent_graph = StateGraph(DataAgentSchema)

data_agent_graph.add_node("router_node", router_node)
data_agent_graph.add_node("etl_node", etl_node)
data_agent_graph.add_node("sql_node", sql_node)

data_agent_graph.add_edge(START, "router_node")


def route_edge(state: DataAgentSchema) -> str:
    if state.route_response == "sql":
        return "sql_node"
    elif state.route_response == "etl":
        return "etl_node"
    else:
        raise ValueError(f"Invalid route response: {state.route_response}")


data_agent_graph.add_conditional_edges(
    "router_node", route_edge, {"sql_node": "sql_node", "etl_node": "etl_node"}
)

data_agent = data_agent_graph.compile()

if __name__ == "__main__":
    response = data_agent.invoke(
        {
            "messages": [
                HumanMessage(
                    content="I want to extract the data from the API endpoint 'https://pokeapi.co/api/v2/pokemon' and save it to data/extract folder in the csv folder"
                )
            ],
            "route_response": None,
        }
    )

    print(response)
