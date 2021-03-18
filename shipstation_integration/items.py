import frappe


def create_item(product, settings, store=None):
	"""
	Create or update a Shipstation item, and setup item defaults.

	Args:
		product (shipstation.ShipStationItem): The Shipstation item.
		settings (ShipstationSettings, optional): A Shipstation Settings instance.
		store (ShipstationStore, optional): The selected Shipstation store.
			Defaults to None.

	Returns:
		str: The item code of the created or updated Shipstation item.
	"""

	if not product.sku:
		item_name = product.name[:140]
		item_code = frappe.get_value("Item", {"item_name": item_name.strip()})
	else:
		item_code = frappe.get_value("Item", {"item_code": product.sku.strip()})

	if item_code:
		item = frappe.get_doc("Item", item_code)
	else:
		item = frappe.new_doc("Item")
		item.update({
			"item_code": product.sku or product.name[:140],
			"item_name": product.name[:140],
			"item_group": settings.default_item_group,
			"is_stock_item": 1,
			"include_item_in_manufacturing": 0,
			"description": getattr(product, "internal_notes", product.name),
			"weight_per_unit": getattr(product, "weight_oz", 0),
			"weight_uom": "Ounce",
			"end_of_life": ""
		})

	if store and store.company and not item.get("item_defaults"):
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
