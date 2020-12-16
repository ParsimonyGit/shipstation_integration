import frappe
import json
from shipstation_integration.orders import create_erpnext_order
from shipstation_integration.shipments import create_erpnext_shipment


@frappe.whitelist(allow_guest=True)
def webhook():
	data = frappe._dict(frappe.api.get_request_form_data())
	if not data.resource_url:
		return

	frappe.set_user("Administrator")

	settings = frappe.get_last_doc("Shipstation Settings")
	client = settings.client()
	client.url = data.resource_url

	if data.resource_type == 'ORDER_NOTIFY':
		for store in settings.shipstation_stores:
			orders = client.list_orders({"store_id": store.store_id})
			for order in orders:
				create_erpnext_order(order, store)
	elif data.resource_type == 'ITEM_SHIP_NOTIFY':
		for store in settings.shipstation_stores:
			shipments = client.list_shipments({"store_id": store.store_id})
			for shipment in shipments:
				create_erpnext_shipment(shipment, store)
