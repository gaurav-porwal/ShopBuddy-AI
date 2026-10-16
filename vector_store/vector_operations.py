"""
ODO RPC Layer - Odoo Product Vector Store Service
"""
from typing import List, Dict, Any
from models.odoo_models import get_product_template
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

from dotenv import load_dotenv
import os
load_dotenv()

# Configure embeddings to use proxy endpoint
embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    openai_api_base=os.getenv("OPENAI_BASE_URL")
)

def get_all_products() -> List[Dict[str, Any]]:
    """
    Fetch all product templates from Odoo.

    Returns:
        List[Dict]: List of product records containing
        name, list_price, description_sale, and categ_id.
    """
    product_model = get_product_template()

    return product_model.search_read(
        [],
        ['name', 'list_price', 'description_sale', 'categ_id']
    )


def build_vector_store() -> Chroma:
    """
    Build a Chroma vector store from Odoo product data.

    Steps:
        1. Fetch products from Odoo
        2. Convert each product into a text document
        3. Create metadata for each product
        4. Generate embeddings and store in Chroma

    Returns:
        Chroma: Vector store containing product embeddings
    """
    products = get_all_products()

    documents: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    for product in products:
        # Create document text
        name = product.get("name", "")
        description = product.get("description_sale") or ""

        text = f"{name} {description}".strip()
        documents.append(text)

        # Extract category safely
        category = None
        categ = product.get("categ_id")
        if isinstance(categ, list) and len(categ) > 1:
            category = categ[1]

        # Create metadata
        metadata = {
            "name": name,
            "price": product.get("list_price"),
            "category": category
        }
        metadatas.append(metadata)

    # Build vector store
    return Chroma.from_texts(
        texts=documents,
        embedding=embeddings,
        metadatas=metadatas
    )