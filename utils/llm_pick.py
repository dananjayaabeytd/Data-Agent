from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


def pick_llm(level: str):
    """
    Picks the appropriate LLM based on the level of the question.

    Args:
        level (str): The level of the question, can be "low", "medium", or "high".

    Returns:
        ChatOpenAI: The LLM instance to be used.
    """
    common_options = {"temperature": 0, "timeout": 60, "max_retries": 2}
    if level.lower() == "low":
        llm = ChatOpenAI(
            model_name="gpt-5.6-luna", reasoning_effort="none", **common_options
        )
    elif level.lower() == "medium":
        llm = ChatOpenAI(
            model_name="gpt-5.6-terra", reasoning_effort="none", **common_options
        )
    elif level.lower() == "high":
        llm = ChatOpenAI(
            model_name="gpt-5.6-sol", reasoning_effort="none", **common_options
        )
    else:
        raise ValueError(f"Unsupported level: {level}")

    return llm


if __name__ == "__main__":
    llm_obj = pick_llm("low")
    print(llm_obj.invoke("What is the capital of France?"))
