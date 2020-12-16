import frappe


def create_item(product, store):
    if not product.sku:
        item_name = product.name[:140]
        item_code = frappe.get_value("Item", {"item_name": item_name.strip()})
    else:
        item_code = frappe.get_value(
            "Item", {"item_code": product.sku.strip()})

    if item_code:
        return item_code

    item = frappe.new_doc("Item")
    item.update({
        "item_code": product.sku or product.name[:140],
        "item_name": product.name[:140],
        "item_group": store.parent_doc.default_item_group,
        "is_stock_item": 1,
        "include_item_in_manufacturing": 0,
        "description": getattr(product, "internal_notes", product.name),
        "weight_per_unit": getattr(product, "weight_oz", 0),
        "weight_uom": "Ounce",
        "end_of_life": ""
    })

    if store.company:
        item.set("item_defaults", [{
            "company": store.company,
            "default_price_list": "ShipStation",
            "default_warehouse": "",  # leave unset
            "buying_cost_center": store.cost_center,
            "selling_cost_center": store.cost_center,
            "expense_account": store.expense_account,
            "income_account": store.sales_account
        }])

    item.save()
    return item.item_code
