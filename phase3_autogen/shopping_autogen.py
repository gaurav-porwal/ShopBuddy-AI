"""
====================================================
SHOP BUDDY - AUTOGEN
IMPORTANT:
- Do NOT change the autogen_run() function name
====================================================
"""
import os
import requests
from dotenv import load_dotenv
import autogen
import threading

# =====================================================
# CONFIG
# =====================================================

load_dotenv(override=True)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PROXY_URL = os.getenv("OPENAI_BASE_URL")
BASE_URL = "http://localhost:8000"

# =====================================================
# LLM CONFIG
# =====================================================

llm_config = {
    "config_list": [
        {
            "model": "gpt-4o-mini",
            "api_key": OPENAI_API_KEY,
            "base_url": PROXY_URL,
        }
    ],
    "temperature": 0,
    "cache_seed": None,  # Disables disk cache to avoid read-only DB errors
}
_autogen_lock = threading.Lock()

# =====================================================
# TOOLS
# =====================================================

def search_products(query: str, min_price: float = None, max_price: float = None) -> dict:
    """
    Search for products by name/description with optional price filters.
    Args:
        query: search text (e.g. "office chair")
        min_price: minimum price (optional)
        max_price: maximum price (optional)
    Returns product search results as a JSON-serializable dict.
    """
    try:
        params = {"text": query}
        if min_price is not None:
            params["min_price"] = min_price
        if max_price is not None:
            params["max_price"] = max_price
        response = requests.get(f"{BASE_URL}/search_products/", params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"status": "error", "message": f"Error searching products: {e}"}


def get_cart() -> dict:
    """
    Retrieve all items currently in the cart. Takes no arguments.
    """
    try:
        response = requests.get(f"{BASE_URL}/get_cart_items/")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"status": "error", "message": f"Error retrieving cart: {e}"}


def add_to_cart(product_name: str, quantity: int) -> dict:
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
        return response.json()
    except Exception as e:
        return {"status": "error", "message": f"Error adding product to cart: {e}"}


def update_cart(product_name: str, quantity: int) -> dict:
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
        return response.json()
    except Exception as e:
        return {"status": "error", "message": f"Error updating cart item: {e}"}


def delete_from_cart(product_name: str) -> dict:
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
        return response.json()
    except Exception as e:
        return {"status": "error", "message": f"Error deleting cart item: {e}"}


# =====================================================
# ORCHESTRATOR AGENT
# =====================================================

orchestrator_agent = autogen.AssistantAgent(
    name="Orchestrator_Agent",
    llm_config=llm_config,
    system_message="""You are the Shopping Workflow Orchestrator for UrbanNest Furnishings' Shop Buddy.

Your job: analyze the user's request and state a short routing plan ? whether it needs
(a) product search only, (b) cart management only, or (c) both in sequence.

Rules:
- If a cart operation (add/update/delete) mentions a product by name, ALWAYS note that
  Search_Agent must resolve the exact catalog name first before Cart_Agent acts ? never
  assume the user's wording matches the catalog exactly.
- You do NOT call any tools yourself. You only state the plan, then let Search_Agent and/or
  Cart_Agent proceed.
- Keep your response short and clear.
- Do not say TERMINATE yourself; only Search_Agent or Cart_Agent may end the conversation.
""",
)

# =====================================================
# SEARCH AGENT
# =====================================================

search_agent = autogen.AssistantAgent(
    name="Search_Agent",
    llm_config=llm_config,
    system_message="""You are the Product Search Specialist for UrbanNest Furnishings.

You have access to the search_products tool. Use it for ALL product-related lookups.

Rules:
- For pure discovery/browse requests: call search_products, then present ONLY the genuinely
  relevant top results (typically the top 3-5 by relevance score and by matching the
  requested product type) under a clearly labeled "Recommendations:" section, listing name,
  price, and category for each. Do NOT dump the entire raw result list ? filter out items
  that are not actually the type of product the user asked for (e.g. if the user asked for
  desks, exclude unrelated items like chairs, deposits, or delivery services even if they
  appeared in the raw search results).
- For cart operations (add/update/delete) that reference a product by name: call
  search_products and resolve to EXACTLY ONE best-matching product ? the single closest
  match by name to what the user asked (e.g. "office chairs" -> the product literally named
  "Office Chair", not a differently named variant, unless the user specifically asked for
  that variant). State that ONE exact catalog name clearly so Cart_Agent can use it next.
- If this is a pure cart retrieve request with no product mentioned, say clearly that no
  search is needed and let Cart_Agent proceed.

MANDATORY TERMINATION RULE:
- If your response is the FINAL answer for a pure search/discovery request (i.e. Cart_Agent
  does not need to act), you MUST end your message with the exact word TERMINATE alone on
  the last line. This is not optional. Example ending:
  "These are some affordable chair options available.
  TERMINATE"
- If Cart_Agent still needs to act (cart operation in progress), do NOT include TERMINATE.
""",
)

# =====================================================
# CART AGENT
# =====================================================

cart_agent = autogen.AssistantAgent(
    name="Cart_Agent",
    llm_config=llm_config,
    system_message="""You are the Cart Management Specialist for UrbanNest Furnishings.

You have access to: get_cart, add_to_cart, update_cart, delete_from_cart.

Rules:
- Use the SINGLE exact product name resolved by Search_Agent for any add/update/delete
  action ? never the user's raw wording, never split one requested item/quantity across
  multiple different products.
- If a tool call errors, you may retry once with a corrected exact name if one is available.
  Afterward, ALWAYS call get_cart to verify the actual current cart state before writing
  your final answer.
- Base your final answer strictly on the VERIFIED cart state from get_cart, not on an
  earlier failed attempt. If the intended item/quantity is now correct in the cart, report
  success even if an earlier attempt errored. If it's genuinely not reflected, report the
  failure honestly.
- For retrieve requests ("show my cart"), call get_cart and present the full cart contents
  clearly (items, quantities, prices, subtotal, total).
- Once you have produced the final, friendly, user-facing response, end your message with
  the word TERMINATE on its own line.
""",
)

# =====================================================
# USER PROXY
# =====================================================

def _is_termination_msg(msg):
    content = msg.get("content", "")
    return isinstance(content, str) and "TERMINATE" in content

user_proxy = autogen.UserProxyAgent(
    name="User_Proxy",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=10,
    is_termination_msg=_is_termination_msg,
    code_execution_config=False,
)

# =====================================================
# TOOL REGISTRATION
# =====================================================

autogen.register_function(
    search_products,
    caller=search_agent,
    executor=user_proxy,
    description="Search for products by name/description with optional min_price/max_price filters.",
)

autogen.register_function(
    get_cart,
    caller=cart_agent,
    executor=user_proxy,
    description="Retrieve all items currently in the cart.",
)

autogen.register_function(
    add_to_cart,
    caller=cart_agent,
    executor=user_proxy,
    description="Add a product to the cart by exact product_name and quantity.",
)

autogen.register_function(
    update_cart,
    caller=cart_agent,
    executor=user_proxy,
    description="Update the quantity of a product already in the cart by exact product_name.",
)

autogen.register_function(
    delete_from_cart,
    caller=cart_agent,
    executor=user_proxy,
    description="Remove a product from the cart by exact product_name.",
)

# =====================================================
# GROUP CHAT
# =====================================================

groupchat = autogen.GroupChat(
    agents=[user_proxy, orchestrator_agent, search_agent, cart_agent],
    messages=[],
    max_round=16,
    speaker_selection_method="auto",
)

manager = autogen.GroupChatManager(
    groupchat=groupchat,
    llm_config=llm_config,
)

# =====================================================
# RUN
# =====================================================

def autogen_run(user_query: str):
    """
    Runs one full multi-agent shopping workflow for a single user query.
    Resets all agent state first to avoid stale context bleeding across calls.
    """

    groupchat.messages.clear()
    for agent in [orchestrator_agent, search_agent, cart_agent, user_proxy]:
        agent.reset()

    user_proxy.initiate_chat(
        manager,
        message=user_query,
        clear_history=True,
    )

    final_response = "I'm sorry, I couldn't process that request."
    for msg in reversed(groupchat.messages):
        content = msg.get("content")
        if content and isinstance(content, str) and content.strip():
            final_response = content.replace("TERMINATE", "").strip()
            break

    return final_response

# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":

    print("\n===== SHOP BUDDY - AUTOGEN =====")
    print("Type 'exit' to quit.\n")

    while True:

        query = input("\nYou: ")

        if query.lower() == "exit":
            break

        try:
            response = autogen_run(query)
            print("\nBot:\n")
            print(response)

        except Exception as e:
            print("\nError:\n")
            print(str(e))