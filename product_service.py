"""
Unified Product Service Module
 
Handles all product-related operations including:
- Product search with vector embeddings
- Shopping cart management (add, update, remove items)
- Cart information retrieval
 
This service integrates with:
- Vector store for semantic product search
- Odoo client for cart and inventory management
"""
 
from vector_store.vector_operations import build_vector_store
from clients.odoo_client import client
from models.odoo_models import get_model
 
 
# ============================================================================
# SECTION 1: PRODUCT SEARCH OPERATIONS
# ============================================================================
 
def search_products(text, min_price=None, max_price=None, limit=None):
    """
    Semantic search for products using vector embeddings with optional filtering
   
    Args:
        text: Search query text (e.g., "chair", "wooden table", "office furniture")
        min_price: Minimum price filter (optional)
        max_price: Maximum price filter (optional)
        limit: Maximum number of results to return (optional)
       
    Returns:
        Dictionary with search results and unique product count
    """
    vs = build_vector_store()
    
    # Use similarity search with scores to filter by relevance
    # Returns (document, distance_score) tuples where lower distance = better match
    vector_results = vs.similarity_search_with_score(text, k=50)
 
    output = []
    seen_products = set()  # Track seen products to avoid duplicates
 
    for doc, distance_score in vector_results:
        product_name = doc.metadata.get("name", "")
        price = doc.metadata.get("price", 0)
        category = doc.metadata.get("category")
       
        # Skip duplicates
        if product_name in seen_products:
            continue
 
        # Filter by relevance: Chroma uses L2 distance (lower = better)
        # Distance typically ranges 0-2: 
        # < 0.8 = excellent match, < 1.2 = good, < 1.5 = acceptable, > 1.8 = poor
        # Adjust threshold based on your data (1.5 is balanced)
        if distance_score > 1.5:
            continue
 
        # Apply price filters
        if min_price is not None and price < min_price:
            continue
        if max_price is not None and price > max_price:
            continue
 
        # Calculate relevance percentage for display (0-100%)
        relevance = max(0, min(100, int((1.5 - distance_score) / 1.5 * 100)))
 
        output.append({
            "name": product_name,
            "price": price,
            "category": category,
            "relevance": relevance
        })
        seen_products.add(product_name)
 
    # Sort by relevance (highest first) - distance_score was already sorted by vector search
    # but we'll ensure it's in the right order
    output.sort(key=lambda x: x['relevance'], reverse=True)
 
    # Apply limit if specified
    if limit:
        output = output[:limit]
 
    return {
        "status": "success",
        "products": output,
        "count": len(output)
    }
 
 
# ============================================================================
# SECTION 2: HELPER FUNCTIONS
# ============================================================================
 
def _find_product(product_name):
    """Find product by name"""

    Product = get_model('product.product')

    # Try exact match first
    product_ids = Product.search(
        [('name', '=', product_name)],
        limit=1
    )

    # Fallback to partial match
    if not product_ids:
        product_ids = Product.search(
            [('name', 'ilike', product_name)],
            limit=1
        )

    if not product_ids:
        return None, None

    product_id = product_ids[0]
    product = Product.read(product_id, ['name'])[0]

    return product_id, product
 
 
def _get_user_cart():
    """Get or create user's shopping cart"""
    SaleOrder = get_model('sale.order')
    cart_ids = SaleOrder.search(
        [
            ('partner_id.user_ids', 'in', [client.uid]),
            ('state', '=', 'draft'),
            ('website_id', '!=', False)
        ],
        limit=1,
        order='date_order desc'
    )
   
    if cart_ids:
        return cart_ids[0]
   
    # Create new cart
    print("No cart found, creating new cart...")
    User = get_model('res.users')
    user = User.read(client.uid, ['partner_id'])[0]
    partner_id = user['partner_id'][0]
   
    Website = get_model('website')
    website_ids = Website.search([], limit=1)
    website_id = website_ids[0] if website_ids else False
   
    cart_id = SaleOrder.create({
        'partner_id': partner_id,
        'state': 'draft',
        'website_id': website_id,
    })
    print(f"? Created new cart: {cart_id}")
    return cart_id
 
 
# ============================================================================
# SECTION 3: CART OPERATIONS
# ============================================================================
 
def add_to_cart(product_name, quantity):
    """
    Add a product to the shopping cart
   
    Args:
        product_name: Name of the product to add
        quantity: Quantity to add
       
    Returns:
        Dictionary with status and message
    """
    product_id, product = _find_product(product_name)
   
    if not product_id:
        return {'status': 'error', 'message': f'Product "{product_name}" not found'}
   
    cart_id = _get_user_cart()
   
    OrderLine = get_model('sale.order.line')
    existing_line_ids = OrderLine.search(
        [
            ('order_id', '=', cart_id),
            ('product_id', '=', product_id)
        ],
        limit=1
    )
   
    if existing_line_ids:
        # Update existing line - increase quantity
        line_id = existing_line_ids[0]
        line = OrderLine.read(line_id, ['product_uom_qty'])[0]
        new_quantity = line['product_uom_qty'] + quantity
       
        OrderLine.write(line_id, {'product_uom_qty': new_quantity})
        print(f"Updated cart line {line_id}: quantity = {new_quantity}")
        return {'status': 'success', 'message': f'Updated {product_name} quantity to {new_quantity}'}
    else:
        # Add new line to cart
        line_id = OrderLine.create({
            'order_id': cart_id,
            'product_id': product_id,
            'product_uom_qty': quantity,
        })
       
        return {
            'status': 'success',
            'message': f"Added {product['name']} to cart (line {line_id})"
        }
 
 
def update_cart(product_name, new_quantity):
    """
    Update the quantity of a product in the cart
   
    Args:
        product_name: Name of the product to update
        new_quantity: New quantity value
       
    Returns:
        Dictionary with status and message
    """
    product_id, _ = _find_product(product_name)
   
    if not product_id:
        return {'status': 'error', 'message': f'Product "{product_name}" not found'}
   
    SaleOrder = get_model('sale.order')
    cart_ids = SaleOrder.search(
        [
            ('partner_id.user_ids', 'in', [client.uid]),
            ('state', '=', 'draft'),
            ('website_id', '!=', False)
        ],
        limit=1,
        order='date_order desc'
    )
   
    if not cart_ids:
        return {'status': 'error', 'message': 'No cart found'}
   
    cart_id = cart_ids[0]
   
    OrderLine = get_model('sale.order.line')
    line_ids = OrderLine.search(
        [
            ('order_id', '=', cart_id),
            ('product_id', '=', product_id)
        ],
        limit=1
    )
   
    if not line_ids:
        return {'status': 'error', 'message': f'Product "{product_name}" not in cart'}
   
    line_id = line_ids[0]
   
    if new_quantity <= 0:
        OrderLine.unlink([line_id])
        return {'status': 'success', 'message': f'Removed {product_name} from cart'}
    else:
        OrderLine.write(line_id, {'product_uom_qty': new_quantity})
        return {'status': 'success', 'message': f'Updated {product_name} quantity to {new_quantity}'}
 
 
def delete_cart(product_name):
    """
    Remove a product from the shopping cart
   
    Args:
        product_name: Name of the product to remove
       
    Returns:
        Dictionary with status and message
    """
    product_id, product = _find_product(product_name)
   
    if not product_id:
        return {'status': 'error', 'message': f'Product "{product_name}" not found'}
   
    SaleOrder = get_model('sale.order')
    cart_ids = SaleOrder.search(
        [
            ('partner_id.user_ids', 'in', [client.uid]),
            ('state', '=', 'draft'),
            ('website_id', '!=', False)
        ],
        limit=1,
        order='date_order desc'
    )
   
    if not cart_ids:
        return {'status': 'error', 'message': 'No cart found'}
   
    cart_id = cart_ids[0]
   
    OrderLine = get_model('sale.order.line')
    line_ids = OrderLine.search(
        [
            ('order_id', '=', cart_id),
            ('product_id', '=', product_id)
        ],
        limit=1
    )
   
    if not line_ids:
        return {'status': 'error', 'message': f'Product "{product_name}" not in cart'}
   
    line_id = line_ids[0]
    OrderLine.unlink([line_id])
   
    print(f"? Removed {product['name']} from cart")
    return {
        'status': 'success',
        'message': f'Removed {product["name"]} from cart'
    }
 
 
# ============================================================================
# SECTION 4: CART INFORMATION
# ============================================================================
 
def get_cart_items(user_email=None):
    """
    Get all items in the current user's shopping cart
   
    Args:
        user_email: User email (optional, for future use)
       
    Returns:
        Dictionary with cart information and items
    """
    SaleOrder = get_model('sale.order')
   
    cart_orders = SaleOrder.search_read(
        [
            ('partner_id.user_ids', 'in', [client.uid]),
            ('state', '=', 'draft'),
            ('website_id', '!=', False)
        ],
        ['id', 'name', 'order_line', 'amount_total', 'date_order'],
        limit=1,
        order='date_order desc'
    )
   
    results = {}
    if cart_orders:
        cart = cart_orders[0]
        results.update({"Cart ID": cart['id']})
        results.update({"Cart Name": cart['name']})
        results.update({"Total Amount": cart['amount_total']})
        results.update({'Items': []})
       
        order_line_ids = cart['order_line']
        if order_line_ids:
            OrderLine = get_model('sale.order.line')
            cart_items = OrderLine.read(
                order_line_ids,
                ['product_id', 'name', 'product_uom_qty',
                 'price_unit', 'price_subtotal']
            )
           
            print("\nCart Items:")
            for item in cart_items:
                item_data = {
                    "Product": item['product_id'],
                    "Quantity": item['product_uom_qty'],
                    "Unit Price": item['price_unit'],
                    "SubTotal": item['price_subtotal']
                }
                results['Items'].append(item_data)
        else:
            print("Cart is empty")
   
    return results