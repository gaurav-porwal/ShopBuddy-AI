"""
====================================================
SHOP BUDDY - LANGGRAPH
IMPORTANT:
- Do NOT change the langgraph_run() function name
- Return updated state from every node
====================================================
"""
import os
import requests
import operator
import threading
from typing import TypedDict, List, Annotated, Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
    BaseMessage,
    AIMessage
)
from langchain_core.tools import tool
from langgraph.graph import (
    StateGraph,
    END
)
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"

# =====================================================
# CONFIG
# =====================================================

load_dotenv(override=True)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = os.getenv("OPENAI_BASE_URL")
BASE_URL = "http://localhost:8000"

# =====================================================
# LLM
# =====================================================

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    openai_api_key=OPENAI_API_KEY,
    openai_api_base=OPENAI_API_BASE,
)

# =====================================================
# STATE
# =====================================================

class ShopState(TypedDict):
    """
    Shared workflow state.
    - messages: full conversation history (accumulated across nodes/turns)
    - intent: classified as "search" or "cart" by the orchestrator
    """
    messages: Annotated[List[BaseMessage], operator.add]
    intent: str

# =====================================================
# TOOLS
# =====================================================

@tool
def search_products(query: str, min_price: Optional[float] = None, max_price: Optional[float] = None) -> str:
    """
    Search for products by name/description with optional price filters.
    Args:
        query: search text (e.g. "office chair")
        min_price: minimum price (optional, omit if not specified)
        max_price: maximum price (optional, omit if not specified)
    Returns product search results as a JSON string.
    """
    try:
        params = {"text": query}
        if min_price is not None:
            params["min_price"] = min_price
        if max_price is not None:
            params["max_price"] = max_price
        response = requests.get(f"{BASE_URL}/search_products/", params=params)
        response.raise_for_status()
        return str(response.json())
    except Exception as e:
        return f"Error searching products: {e}"


@tool
def get_cart() -> str:
    """
    Retrieve all items currently in the cart. Takes no arguments.
    """
    try:
        response = requests.get(f"{BASE_URL}/get_cart_items/")
        response.raise_for_status()
        return str(response.json())
    except Exception as e:
        return f"Error retrieving cart: {e}"


@tool
def add_to_cart(product_name: str, quantity: int) -> str:
    """
    Add a product to the cart.
    Args:
        product_name: exact catalog product name
        quantity: quantity to add
    """
    try:
        response = requests.post(
            f"{BASE_URL}/add_product_to_cart/",
            params={"product_name": product_name, "quantity": quantity},
        )
        response.raise_for_status()
        return str(response.json())
    except Exception as e:
        return f"Error adding product to cart: {e}"


@tool
def update_cart(product_name: str, quantity: int) -> str:
    """
    Update the quantity of a product already in the cart.
    Args:
        product_name: exact catalog product name
        quantity: new quantity
    """
    try:
        response = requests.put(
            f"{BASE_URL}/update_product_in_cart/",
            params={"product_name": product_name, "quantity": quantity},
        )
        response.raise_for_status()
        return str(response.json())
    except Exception as e:
        return f"Error updating cart item: {e}"


@tool
def delete_from_cart(product_name: str) -> str:
    """
    Remove a product from the cart.
    Args:
        product_name: exact catalog product name to remove
    """
    try:
        response = requests.delete(
            f"{BASE_URL}/delete_product_from_cart/",
            params={"product_name": product_name},
        )
        response.raise_for_status()
        return str(response.json())
    except Exception as e:
        return f"Error deleting cart item: {e}"

# =====================================================
# TOOL COLLECTIONS
# =====================================================

search_tools = [search_products]
cart_tools = [search_products, get_cart, add_to_cart, update_cart, delete_from_cart]

# =====================================================
# TOOL BINDING
# =====================================================

search_llm = llm.bind_tools(search_tools)
cart_llm = llm.bind_tools(cart_tools)

search_tool_node = ToolNode(search_tools)
cart_tool_node = ToolNode(cart_tools)

# =====================================================
# AGENTS (GRAPH NODES)
# =====================================================

ORCHESTRATOR_SYSTEM_PROMPT = """You are the Shopping Workflow Orchestrator for UrbanNest Furnishings.

Classify the user's latest message as exactly one of:
- "search": pure product discovery/browsing, no cart mutation or retrieval requested.
- "cart": any cart operation ? add, update, delete, or retrieve/view the cart ? even if it
  also references a product by name that needs to be resolved first.

Respond with ONLY the single word "search" or "cart", nothing else.
"""

def orchestrator_node(state: ShopState) -> ShopState:
    messages = state["messages"]
    classification_messages = [SystemMessage(content=ORCHESTRATOR_SYSTEM_PROMPT)] + messages
    response = llm.invoke(classification_messages)
    intent = "cart" if "cart" in response.content.strip().lower() else "search"
    return {"messages": [], "intent": intent}


SEARCH_SYSTEM_PROMPT = """You are the Product Search Specialist for UrbanNest Furnishings.

You have access to the search_products tool. Use it to look up products matching the
user's request, applying price filters if mentioned.

Present ONLY the genuinely relevant top results (typically top 3-5, matching the requested
product type) under a clearly labeled "Recommendations:" section listing name, price, and
category for each. Do NOT dump the entire raw result list ? filter out items that are not
actually the type of product the user asked for.

Once you have your final answer, respond with plain text (no further tool calls needed).
"""

def search_node(state: ShopState) -> ShopState:
    messages = state["messages"]
    if not any(isinstance(m, SystemMessage) for m in messages):
        messages = [SystemMessage(content=SEARCH_SYSTEM_PROMPT)] + messages
    response = search_llm.invoke(messages)
    return {"messages": [response]}


CART_SYSTEM_PROMPT = """You are the Cart Management Specialist for UrbanNest Furnishings.

You have access to: search_products, get_cart, add_to_cart, update_cart, delete_from_cart.

Rules:
- If the user's request references a product by name for an add/update/delete action, FIRST
  call search_products to resolve the SINGLE exact catalog product name ? the closest match
  to what the user asked (e.g. "office chairs" -> the product literally named "Office Chair",
  not a differently named variant, unless the user specifically asked for that variant).
  Never use the user's raw wording directly in a cart tool call.
- Use that SINGLE exact resolved name for the cart action ? never split one requested
  item/quantity across multiple different products.
- Do NOT call get_cart before performing an add/update/delete action unless you genuinely
  need to check whether an item currently exists (e.g. before an update, to confirm it's
  there). If you do call get_cart early, you MUST still call it again as your LAST tool
  call, immediately before writing your final answer.
- CRITICAL: after performing any add/update/delete action, your VERY NEXT tool call MUST be
  get_cart, and it must be the LAST tool call before your final answer. Never write your
  final summary based on any get_cart result that came before the mutation ? always use the
  freshest get_cart result, called after the mutation, as the source of truth for your answer.
- Base your final answer strictly on that final, freshest get_cart result. If the intended
  item/quantity is now correct in the cart, report success even if an earlier attempt
  errored. If it's genuinely not reflected, report the failure honestly.
- For retrieve requests ("show my cart"), call get_cart once and present the full cart
  contents clearly (items, quantities, prices, subtotal, total).
- Once you have a final, friendly, human-readable answer, respond with plain text and do NOT
  call any more tools.
"""

def cart_node(state: ShopState) -> ShopState:
    messages = state["messages"]
    if not any(isinstance(m, SystemMessage) for m in messages):
        messages = [SystemMessage(content=CART_SYSTEM_PROMPT)] + messages
    response = cart_llm.invoke(messages)
    return {"messages": [response]}

# =====================================================
# ROUTERS
# =====================================================

def route_after_orchestrator(state: ShopState) -> str:
    return "cart_agent" if state.get("intent") == "cart" else "search_agent"


def route_search_tools(state: ShopState) -> str:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and getattr(last_message, "tool_calls", None):
        return "search_tools"
    return END


def route_cart_tools(state: ShopState) -> str:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and getattr(last_message, "tool_calls", None):
        return "cart_tools"
    return END

# =====================================================
# GRAPH
# =====================================================

def _build_graph():
    workflow = StateGraph(ShopState)

    workflow.add_node("orchestrator", orchestrator_node)
    workflow.add_node("search_agent", search_node)
    workflow.add_node("search_tools", search_tool_node)
    workflow.add_node("cart_agent", cart_node)
    workflow.add_node("cart_tools", cart_tool_node)

    workflow.set_entry_point("orchestrator")

    workflow.add_conditional_edges(
        "orchestrator",
        route_after_orchestrator,
        {"search_agent": "search_agent", "cart_agent": "cart_agent"},
    )

    workflow.add_conditional_edges(
        "search_agent",
        route_search_tools,
        {"search_tools": "search_tools", END: END},
    )
    workflow.add_edge("search_tools", "search_agent")

    workflow.add_conditional_edges(
        "cart_agent",
        route_cart_tools,
        {"cart_tools": "cart_tools", END: END},
    )
    workflow.add_edge("cart_tools", "cart_agent")

    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)


_compiled_graph = _build_graph()
_graph_lock = threading.Lock()

# =====================================================
# RUN
# =====================================================

def langgraph_run(user_input: str, thread_id: str = "default"):
    """
    Executes one turn of the LangGraph shopping workflow for the given user input,
    preserving conversation state across calls via thread_id (checkpointer memory).
    """
    with _graph_lock:
        config = {"configurable": {"thread_id": thread_id}}
        result = _compiled_graph.invoke(
            {"messages": [HumanMessage(content=user_input)], "intent": ""},
            config=config,
        )

        final_response = "I'm sorry, I couldn't process that request."
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage) and msg.content and not getattr(msg, "tool_calls", None):
                final_response = msg.content
                break

        return final_response

# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":

    print("\n===== SHOP BUDDY - LANGGRAPH =====")
    print("Type 'exit' to quit.\n")

    while True:

        user_input = input("\nYou: ")

        if user_input.lower() == "exit":
            break

        try:
            result = langgraph_run(user_input)
            print("\nBot:\n")
            print(result)

        except Exception as e:
            print("\nError:\n")
            print(str(e))