from langchain_core.messages import HumanMessage

from agents.data_agent import data_agent

if __name__ == "__main__":
    response = data_agent.invoke(
        {"messages":[HumanMessage(content="I want to extract the data from the API endpoint 'https://pokeapi.co/api/v2/pokemon' and save it to data/extract folder in the csv folder")],
         "route_response": None}
    )

    final_message = response["messages"][-1]
    print(final_message.content)