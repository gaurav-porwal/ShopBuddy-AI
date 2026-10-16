"""
====================================================
SHOP BUDDY ? CREWAI MULTI-AGENT SYSTEM
====================================================
"""

import os
import requests

from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool
from typing import Optional

# ------------------ CONFIG ------------------

load_dotenv(override=True)
API_KEY = os.getenv("OPENAI_API_KEY")
PROXY_URL = os.getenv("OPENAI_BASE_URL")
BASE_URL = "http://localhost:8000"


# ------------------ LLM ------------------

llm = LLM(
    model="gpt-4o-mini",
    api_key=API_KEY,
    base_url=PROXY_URL,
)


# ------------------ TOOLS ------------------



@tool("SearchProducts")
def search_tool(query: str, filter_1: Optional[float] = None, filter_2: Optional[float] = None) -> str:
    """
    Search for products by name/description with optional price filters.
    Args:
        query: search text (e.g. "office chair")
        filter_1: minimum price (optional, omit if not specified)
        filter_2: maximum price (optional, omit if not specified)
    Returns product results as JSON text.
    """
    try:
        params = {"text": query}
        if filter_1 is not None:
            params["min_price"] = filter_1
        if filter_2 is not None:
            params["max_price"] = filter_2

        response = requests.get(f"{BASE_URL}/search_products/", params=params)
        response.raise_for_status()
        return str(response.json())
    except Exception as e:
        return f"Error searching products: {e}"


@tool("GetCartItems")
def retrieve_tool() -> str:
    """
    Retrieve all items currently in the cart. Takes no arguments.
    """
    try:
        response = requests.get(f"{BASE_URL}/get_cart_items/")
        response.raise_for_status()
        return str(response.json())
    except Exception as e:
        return f"Error retrieving cart: {e}"


@tool("AddProductToCart")
def create_tool(name: str, value: int) -> str:
    """
    Add a product to the cart.
    Args:
        name: exact product name
        value: quantity to add
    """
    try:
        response = requests.post(
            f"{BASE_URL}/add_product_to_cart/",
            params={"product_name": name, "quantity": value},
        )
        response.raise_for_status()
        return str(response.json())
    except Exception as e:
        return f"Error adding product to cart: {e}"


@tool("UpdateCartItem")
def update_tool(name: str, value: int) -> str:
    """
    Update the quantity of a product already in the cart.
    Args:
        name: exact product name
        value: new quantity
    """
    try:
        response = requests.put(
            f"{BASE_URL}/update_product_in_cart/",
            params={"product_name": name, "quantity": value},
        )
        response.raise_for_status()
        return str(response.json())
    except Exception as e:
        return f"Error updating cart item: {e}"


@tool("DeleteCartItem")
def delete_tool(name: str) -> str:
    """
    Remove a product from the cart.
    Args:
        name: exact product name to remove
    """
    try:
        response = requests.delete(
            f"{BASE_URL}/delete_product_from_cart/",
            params={"product_name": name},
        )
        response.raise_for_status()
        return str(response.json())
    except Exception as e:
        return f"Error deleting cart item: {e}"


# ------------------ AGENTS ------------------

def create_agents():
    """
    Create THREE agents: Orchestrator, Product Search, Cart Management.
    """

    orchestrator = Agent(
        role="Shopping Workflow Orchestrator",
        goal=(
            "Analyze the user's natural language request and determine whether it requires "
            "product search, cart management, or both. Route the request to the correct "
            "downstream agent(s) and coordinate the overall workflow."
        ),
        backstory=(
            "You are the lead coordinator for UrbanNest Furnishings' AI shopping assistant. "
            "You understand customer intent quickly and never perform search or cart actions "
            "yourself ? you only decide what needs to happen and in what order."
        ),
        tools=[],
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    search_agent = Agent(
        role="Product Search Specialist",
        goal=(
            "Find the most relevant products for the user's query using the SearchProducts tool, "
            "applying price filters when mentioned, and prepare clear product details "
            "(name, price, key attributes) for any downstream cart operations."
        ),
        backstory=(
            "You are a furniture product expert at UrbanNest Furnishings with deep knowledge "
            "of the catalog. You use semantic search to find the best matching products and "
            "give concise, accurate recommendations."
        ),
        tools=[search_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    cart_agent = Agent(
        role="Cart Management Specialist",
        goal=(
            "Execute cart operations ? add, update, delete, and retrieve ? accurately based on "
            "user intent and any product information resolved by the search agent. Always confirm "
            "the final cart state in your response."
        ),
        backstory=(
            "You manage the shopping cart for UrbanNest Furnishings customers. You are precise "
            "with product names and quantities, and you always produce a clear, friendly summary "
            "of what changed in the cart."
        ),
        tools=[retrieve_tool, create_tool, update_tool, delete_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    return orchestrator, search_agent, cart_agent


# ------------------ TASKS ------------------

def create_tasks(user_input, orchestrator, search_agent, cart_agent):
    """
    Create THREE tasks: Orchestration, Search, Cart.
    """

    orchestration_task = Task(
        description=(
            f"Analyze this user request: '{user_input}'.\n"
            "Determine whether it requires: (a) product search only, (b) cart management only, "
            "or (c) both search and cart in sequence. Output a short plan describing the required "
            "workflow and any product/quantity details mentioned by the user."
        ),
        expected_output=(
            "A short orchestration plan stating which workflow(s) are needed (search/cart/both) "
            "and any relevant details (product name, quantity, price filters) extracted from the request."
        ),
        agent=orchestrator,
    )

    search_task = Task(
        description=(
            f"Based on the orchestration plan and the original user request: '{user_input}':\n"
            "- If this is a pure discovery/browse request (no cart action), use the SearchProducts tool "
            "and return several relevant options with price filters applied if mentioned.\n"
            "- If this is a cart operation (add/update/delete) that references a product by name, use the "
            "SearchProducts tool and resolve to EXACTLY ONE best-matching product ? the single closest match "
            "by name to what the user asked for (e.g. 'office chairs' -> the product literally named "
            "'Office Chair', not a differently-named variant like 'Office Chair Black', unless the user's "
            "wording specifically indicates that variant). Do NOT recommend or split the quantity across "
            "multiple different products for a single cart action. State the ONE exact catalog name to use.\n"
            "- Only skip search entirely if this is a cart retrieve request with no product mentioned.\n"
            "State clearly what you searched for and the single exact product name resolved for any cart action."
        ),
        expected_output=(
            "For discovery requests: relevant product results (name, price, key details). "
            "For cart-action requests: exactly ONE resolved exact catalog product name to use downstream, "
            "not a list of alternatives."
        ),
        agent=search_agent,
        context=[orchestration_task],
    )

    cart_task = Task(
        description=(
            f"Based on the orchestration plan and search results, and the original user request: "
            f"'{user_input}', perform the required cart operation(s) ? add, update, delete, or "
            "retrieve ? using the appropriate cart tool(s). Use the SINGLE exact product name resolved "
            "by the Product Search Specialist for the requested quantity ? never split one requested item "
            "and quantity across multiple different products, and never call a cart tool more than once "
            "for the same user-requested item. If no exact match was found in search results, say so "
            "clearly instead of guessing a name. Produce the final, friendly response for the user."
        ),
        expected_output=(
            "A clear, user-facing confirmation of the cart action taken and the resulting cart state, "
            "or the requested cart contents if this was a retrieve request."
        ),
        agent=cart_agent,
        context=[orchestration_task, search_task],
    )
    return orchestration_task, search_task, cart_task

# ------------------ CREW EXECUTION ------------------

def crew_run(user_input):
    """
    1. Create agents
    2. Create tasks
    3. Initialize Crew
    4. Execute using kickoff()
    5. Return final result
    """

    orchestrator, search_agent, cart_agent = create_agents()

    orchestration_task, search_task, cart_task = create_tasks(
        user_input, orchestrator, search_agent, cart_agent
    )

    crew = Crew(
        agents=[orchestrator, search_agent, cart_agent],
        tasks=[orchestration_task, search_task, cart_task],
        process=Process.sequential,
        verbose=True,
    )

    result = crew.kickoff()
    return result


# ------------------ MAIN ------------------

def main():
    print("\n===== SHOP BUDDY - CREWAI =====")
    print("Type 'exit' to quit.\n")

    while True:
        user_input = input("You: ")

        if user_input.lower() == "exit":
            print("\nShop Buddy: Goodbye!\n")
            break

        result = crew_run(user_input)
        print(f"\nShop Buddy: {result}\n")


if __name__ == "__main__":
    main()