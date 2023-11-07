from typing import TYPE_CHECKING, Optional, Union

from shipstation.models import ShipStationItem, ShipStationOrderItem

import frappe
from frappe.utils import flt

from shipstation_integration.hook_events.item import get_item_alias

if TYPE_CHECKING:
	from erpnext.stock.doctype.item.item import Item
	from shipstation_integration.shipstation_integration.doctype.shipstation_store.shipstation_store import (
		ShipstationStore,
	)
	from shipstation_integration.shipstation_integration.doctype.shipstation_settings.shipstation_settings import (
		ShipstationSettings,
	)

# map Shipstation UOM to ERPNext UOM
WEIGHT_UOM_MAP = {"Grams": "Gram", "Ounces": "Ounce", "Pounds": "Pound"}


def create_item(
	product: Union[ShipStationItem, ShipStationOrderItem],
	settings: "ShipstationSettings",
	store: Optional["ShipstationStore"] = None,
) -> str:
	"""
	Create or update a Shipstation item, and setup item defaults.

	:param product: The Shipstation item or order item document
	:param settings: (optional) A Shipstation Settings instance
	:param store: (optional) The selected Shipstation store, defaults to None
	:return: The item code of the created or updated Shipstation item
	"""

	item_code = get_item_alias(product)
	item_name = (
		frappe.db.get_value("Item", item_code, "item_name") or product.name[:140]
	)

	if not item_code:
		if not product.sku:
			item_code = frappe.db.get_value("Item", {"item_name": item_name.strip()})
		else:
			item_code = frappe.db.get_value("Item", {"item_code": product.sku.strip()})
			item_name = (
				frappe.db.get_value("Item", item_code, "item_name")
				or product.name[:140]
			)

	if item_code:
		item: "Item" = frappe.get_doc("Item", item_code)
	else:
		weight_per_unit = weight_uom = None
		if isinstance(product, ShipStationItem):
			weight_per_unit = getattr(product, "weight_oz", None)
			weight_uom = "Ounce" if weight_per_unit else None
		elif isinstance(product, ShipStationOrderItem):
			weight = product.weight if hasattr(product, "weight") else frappe._dict()
			if weight:
				weight_per_unit = weight.value if weight else 1
				weight_uom = (
					weight.units.title() if weight and weight.units else "Ounce"
				)

		item: "Item" = frappe.new_doc("Item")
		item.update(
			{
				"item_code": product.sku or item_name,
				"item_name": item_name,
				"item_group": settings.default_item_group,
				"is_stock_item": True,
				"include_item_in_manufacturing": False,
				"description": getattr(product, "internal_notes", product.name),
				"weight_per_unit": flt(weight_per_unit),
				"weight_uom": WEIGHT_UOM_MAP.get(weight_uom, weight_uom),
				"end_of_life": "",
			}
		)

	if item.disabled:
		# override disabled status to be able to add the item to the order
		item.disabled = False
		item.add_comment(
			comment_type="Edit",
			text="re-enabled this item after a new order was fetched from Shipstation",
		)

	# create item defaults, if missing
	if store:
		item.update(
			{
				"integration_doctype": "Shipstation Settings",
				"integration_doc": store.parent,
				"store": store.name,
			}
		)

		if store.company and not item.get("item_defaults"):
			item.set(
				"item_defaults",
				[
					{
						"company": store.company,
						"default_price_list": "ShipStation",
						"default_warehouse": store.warehouse,
						"buying_cost_center": store.cost_center,
						"selling_cost_center": store.cost_center,
						"expense_account": store.expense_account,
						"income_account": store.sales_account,
					}
				],
			)

	before_save_hook = frappe.get_hooks("update_shipstation_item_before_save")
	if before_save_hook:
		item = frappe.get_attr(before_save_hook[0])(store, item)

	item.save()
	return item.item_code
