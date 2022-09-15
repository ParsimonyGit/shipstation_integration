import frappe

def execute():
	delivery_note_custom_fields = [
		'Delivery Note-shipment_details',
		'Delivery Note-sb_shipment',
		'Delivery Note-carrier',
		'Delivery Note-tracking_number',
		'Delivery Note-cb_shipment',
		'Delivery Note-carrier_service'
	]
	for custom_field in delivery_note_custom_fields:
		frappe.delete_doc_if_exists("Custom Field", custom_field)
