from typing import TYPE_CHECKING, Optional, Union

from shipstation.models import ShipStationItem, ShipStationOrderItem

import frappe
from frappe.utils import flt

if TYPE_CHECKING:
	from shipstation_integration.shipstation_integration.doctype.shipstation_store.shipstation_store import (
		ShipstationStore,
	)
	from shipstation_integration.shipstation_integration.doctype.shipstation_settings.shipstation_settings import (
		ShipstationSettings,
	)

NON_STOCK_ITEM_KEYWORDS = ["coupon"]


def create_item(
	product: Union[ShipStationItem, ShipStationOrderItem],
	settings: "ShipstationSettings",
	store: Optional["ShipstationStore"] = None,
) -> str:
	"""
	Create or update a Shipstation item, and setup item defaults.

	Args:
		product (shipstation.ShipStationItem | shipstation.ShipStationOrderItem):
			The Shipstation item or order item document.
		settings (ShipstationSettings, optional): A Shipstation Settings instance.
		store (ShipstationStore, optional): The selected Shipstation store.
			Defaults to None.

	Returns:
		str: The item code of the created or updated Shipstation item.
	"""

	item_name = product.name[:140]
	if not product.sku:
		item_code = frappe.db.get_value("Item", {"item_name": item_name.strip()})
	else:
		item_code = frappe.db.get_value("Item", {"item_code": product.sku.strip()})
		item_name = (
			frappe.db.get_value("Item", item_code, "item_name") or item_name
		)

	if item_code:
		item = frappe.get_doc("Item", item_code)
	else:
		is_stock_item = not any(
			keyword.lower() in item_name.lower() for keyword in NON_STOCK_ITEM_KEYWORDS
		)

		item = frappe.new_doc("Item")
		item.update(
			{
				"item_code": product.sku or item_name,
				"item_name": item_name,
				"item_group": settings.default_item_group,
				"is_stock_item": is_stock_item,
				"include_item_in_manufacturing": 0,
				"description": getattr(product, "internal_notes", product.name),
				"end_of_life": "",
			}
		)

	# update weight values
	weight_per_unit, weight_uom = 1.0, "Ounce"
	if isinstance(product, ShipStationItem):
		weight_per_unit = flt(getattr(product, "weight_oz", 1))
	elif isinstance(product, ShipStationOrderItem):
		weight = product.weight if hasattr(product, "weight") else frappe._dict()
		if weight:
			weight_per_unit = flt(weight.value) if weight else 1
			weight_uom = weight.units.title() if weight and weight.units else "Ounce"
			if weight_uom == "Ounces":
				# map Shipstation UOM to ERPNext UOM
				weight_uom = "Ounce"

	item.update(
		{
			"weight_per_unit": weight_per_unit,
			"weight_uom": weight_uom,
		}
	)

	# create item defaults, if missing
	if store and store.company and not item.get("item_defaults"):
		item.set(
			"item_defaults",
			[
				{
					"company": store.company,
					"default_price_list": "ShipStation",
					"default_warehouse": "",  # leave unset
					"buying_cost_center": store.cost_center,
					"selling_cost_center": store.cost_center,
					"expense_account": store.expense_account,
					"income_account": store.sales_account,
				}
			],
		)

	item.save()
	return item.item_code
