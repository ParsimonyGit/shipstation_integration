import frappe
from frappe.utils import flt, update_progress_bar

from shipstation_integration.setup import setup_custom_fields


def execute():
	"""This patch needs to be executed manually since it needs to call the
	Shipstation API multiple times, which can keep sites down for a long time."""

	# setup_custom_fields()

	shipstation_settings = frappe.get_all("Shipstation Settings", filters={"enabled": True})

	for settings in shipstation_settings:
		settings_doc = frappe.get_doc("Shipstation Settings", settings.name)
		client = settings_doc.client()

		for store in settings_doc.shipstation_stores:
			if not store.enable_orders:
				continue

			store_orders = frappe.get_all(
				"Sales Order",
				filters={
					"docstatus": 1,
					"shipstation_store_name": store.store_name,
					"marketplace": store.marketplace_name,
					"shipstation_order_id": ["is", "set"],
				},
				fields=["name", "shipstation_order_id"],
			)

			for i, order in enumerate(store_orders):
				update_progress_bar(
					f"Updating Shipstation order item IDs for {store.marketplace_name} ({store.store_name})",
					i,
					len(store_orders),
				)

				shipstation_order = client.get_order(order.shipstation_order_id)
				sales_order = frappe.get_doc("Sales Order", order.name)

				for item in shipstation_order.items:
					if not item.order_item_id:
						continue

					for order_item in sales_order.items:
						if (
							order_item.item_code == item.sku.strip()
							and flt(order_item.qty) == flt(item.quantity)
							and flt(order_item.rate) == flt(item.unit_price)
						):
							frappe.db.set_value(
								"Sales Order Item",
								order_item.name,
								"shipstation_order_item_id",
								item.order_item_id,
								update_modified=False,
							)
							frappe.db.commit()
