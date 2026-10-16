"""
Utility functions for accessing Odoo models and basic records using RPC.

This module provides helper functions to:
- Retrieve Odoo models via client.odoo.env
- Access commonly used models like users, products, and sales orders
- Fetch a limited number of records (entries) from each model
"""

from clients.odoo_client import client


def get_model(model_name: str):
    return client.odoo.env[model_name]


# ------------------ MODEL ACCESS ------------------ #

def get_user():
    return get_model('res.users')


def get_product():
    return get_model('product.product')


def get_product_template():
    return get_model('product.template')


def get_sale_order():
    return get_model('sale.order')


def get_order_line():
    return get_model('sale.order.line')


# ------------------For Understanding ----------------- #

def get_product_records(limit=2):
    product_model = client.odoo.env['product.product']
    records = product_model.search_read([], fields=['id', 'name'], limit=limit)
    return records


def get_user_records(limit=2):
    user_model = client.odoo.env['res.users']
    records = user_model.search_read([], fields=['id', 'name'], limit=limit)
    return records


def get_sale_order_records(limit=2):
    order_model = client.odoo.env['sale.order']
    records = order_model.search_read([], fields=['id', 'name'], limit=limit)
    return records



# ------------------ MAIN (FOR TESTING) ------------------ #

if __name__ == "__main__":
    print("=== Testing Model Access ===")

    print("User Model:", get_user())
    print("Product Model:", get_product())
    print("Sale Order Model:", get_sale_order())

    print("\n=== Testing Record Access ===")

    print("\nUsers:")
    for u in get_user_records():
        print(u['id'], u['name'])

    print("\nProducts:")
    for p in get_product_records():
        print(p['id'], p['name'])

    print("\nOrders:")
    for o in get_sale_order_records():
        print(o['id'], o['name'])

    print("\n=== Done ===")