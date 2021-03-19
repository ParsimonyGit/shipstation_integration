import frappe


def execute():
	frappe.reload_doc("shipstation_integration", "doctype", "shipstation_settings")
	frappe.reload_doc("shipstation_integration", "doctype", "shipstation_warehouse")

	for settings in frappe.get_all("Shipstation Settings"):
		settings_doc = frappe.get_doc("Shipstation Settings", settings.name)
		settings_doc.enabled = 1
		settings_doc.update_warehouses()
		settings_doc.save()
