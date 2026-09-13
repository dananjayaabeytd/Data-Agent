import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langchain.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.graph import END, START, StateGraph

from Models.schema import ETLAgentSchema, TransformationPlan
from utils.etl_tools import ETLTools
from utils.llm_pick import pick_llm


@tool
def extract_load_tool(url: str, output_folder: str, format: str) -> str:
    """Extract records from an API and save them as CSV, JSON, or Parquet."""
    return ETLTools().extract_load(url, output_folder, format)


@tool
def transform_load_tool(
    input_file_path: str, output_folder: str, output_format: str, user_question: str
) -> str:
    """Apply an allowlisted structured transformation plan to a local data file."""
    etl_tools = ETLTools()
    top_3_rows = etl_tools.transform_load_context(input_file_path)
    planner = pick_llm("medium").with_structured_output(TransformationPlan)
    prompt = f"""
You are a data transformation planner. Return a structured plan only.
Allowed operations, in order: filter_equals, filter_contains, select_columns, sort, limit.
Never propose Python code, imports, file access, shell commands, or arbitrary expressions.
Use an empty steps list when no transformation is required.

Input file: {input_file_path}
Output folder: {output_folder}
Output format: {output_format}
User request: {user_question}
Data sample:
{top_3_rows}
"""

    try:
        plan = planner.invoke(prompt)
        resolved_input = etl_tools._resolve_project_path(input_file_path)
        resolved_output = etl_tools._resolve_project_path(output_folder)
        return etl_tools.apply_transformation_plan(
            str(resolved_input), str(resolved_output), output_format, plan
        )
    except (OSError, TypeError, ValueError) as error:
        return f"Transformation rejected: {error}"


tools = [extract_load_tool, transform_load_tool]
llm = pick_llm("medium")
llm_bind = llm.bind_tools(tools)


def llm_node(state: ETLAgentSchema):
    prompt = f"""
You are a data analyst with tools for API extraction and safe tabular transformations.
Choose the appropriate tool for the user's request. After a tool succeeds, summarize
what happened and stop. Never invent file paths or transformation code.
Chat history: {state.messages}
"""
    response = llm_bind.invoke(prompt)
    return {"messages": [response]}


def tool_node(state: ETLAgentSchema):
    tools_by_name = {available_tool.name: available_tool for available_tool in tools}
    results = []
    for tool_call in state.messages[-1].tool_calls:
        selected_tool = tools_by_name.get(tool_call["name"])
        if selected_tool is None:
            raise ValueError(f"Unknown ETL tool: {tool_call['name']}")
        observation = selected_tool.invoke(tool_call["args"])
        results.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
    return {"messages": results}


etl_analyst_graph = StateGraph(ETLAgentSchema)
etl_analyst_graph.add_node("llm_node", llm_node)
etl_analyst_graph.add_node("tool_node", tool_node)
etl_analyst_graph.add_edge(START, "llm_node")


def is_tool_call(state: ETLAgentSchema):
    return "tool_node" if state.messages[-1].tool_calls else "end"


etl_analyst_graph.add_conditional_edges(
    "llm_node", is_tool_call, {"tool_node": "tool_node", "end": END}
)
etl_analyst_graph.add_edge("tool_node", "llm_node")
etl_analyst = etl_analyst_graph.compile()
