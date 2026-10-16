"""
ODO RPC Layer - FastAPI Endpoints
"""

from fastapi import FastAPI
from typing import Optional
from product_service import (search_products, add_to_cart, get_cart_items, update_cart, delete_cart)
from phase2_crew.shopping_crew import (crew_run)
from phase3_autogen.shopping_autogen import (autogen_run)
from phase4_langgraph.shopping_graph import (langgraph_run)

app = FastAPI()

# =====================================================
# ROOT
# =====================================================

@app.get("/")
def root():
    return {"message": "ODO RPC Layer FastAPI Endpoints Running"}

# =====================================================
# PRODUCT SEARCH
# =====================================================

@app.get("/search_products/")
def search(text: str, min_price: Optional[float] = None, max_price: Optional[float] = None):
    return search_products(text, min_price, max_price)

# =====================================================
# CART APIs
# =====================================================

@app.get("/get_cart_items/")
def get_cart():
    return get_cart_items()

@app.post("/add_product_to_cart/")
def add(product_name: str, quantity: int):
    return add_to_cart(product_name, quantity)

@app.put("/update_product_in_cart/")
def update(product_name: str, quantity: int):
    return update_cart(product_name, quantity)

@app.delete("/delete_product_from_cart/")
def delete(product_name: str):
    return delete_cart(product_name)

# =====================================================
# CREWAI ENDPOINT
# =====================================================

@app.post("/crew_chat/")
def crew_chat(query: str):
    try:
        result = crew_run(query)
        return {
            "status": "success",
            "framework": "CrewAI",
            "response": str(result)
        }
    except Exception as e:
        return {
            "status": "error",
            "framework": "CrewAI",
            "message": str(e)
        }

# =====================================================
# AUTOGEN ENDPOINT
# =====================================================

@app.post("/autogen_chat/")
def autogen_chat(query: str):
    try:
        result = autogen_run(query)
        return {
            "status": "success",
            "framework": "AutoGen",
            "response": result
        }
    except Exception as e:
        return {
            "status": "error",
            "framework": "AutoGen",
            "message": str(e)
        }

# =====================================================
# LANGGRAPH ENDPOINT
# =====================================================

@app.post("/langgraph_chat/")
def langgraph_chat(query: str):
    try:
        result = langgraph_run(query)
        return {
            "status": "success",
            "framework": "LangGraph",
            "response": result
        }
    except Exception as e:
        return {
            "status": "error",
            "framework": "LangGraph",
            "message": str(e)
        }