import frappe


def execute():
	frappe.reload_doc("shipstation_integration", "doctype", "shipstation_store")

	for store in frappe.get_all("Shipstation Store", fields=["*"]):
		if store.is_enabled:
			frappe.db.set_value("Shipstation Store", store.name, "enable_orders", True)
			frappe.db.set_value("Shipstation Store", store.name, "enable_shipments", True)
