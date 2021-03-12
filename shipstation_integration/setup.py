import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def get_setup_stages(args=None):
	return [
		{
			'status': _('Creating shipstation masters'),
			'fail_msg': _('Failed to create shipstation masters'),
			'tasks': [
				{
					'fn': create_customer_group,
					'args': args,
					'fail_msg': _("Failed to create Shipstation Customer Group")
				},
				{
					'fn': create_price_list,
					'args': args,
					'fail_msg': _("Failed to create Shipstation Price List")
				},
				{
					'fn': setup_custom_fields,
					'args': args,
					'fail_msg': _("Failed to create Shipstation custom fields")
				}
			]
		}
	]


def setup_shipstation():
	"""
	Development function to ease the process of creating the masters
	and custom fields
	"""

	create_customer_group()
	create_price_list()
	setup_custom_fields()


def create_customer_group(args=None):
	if frappe.db.get_value('Customer Group', {'customer_group_name': 'ShipStation'}):
		return

	customer_group = frappe.new_doc("Customer Group")
	customer_group.customer_group_name = 'ShipStation'
	customer_group.parent_customer_group = 'All Customer Groups'
	customer_group.save()


def create_price_list(args=None):
	if frappe.db.get_value('Price List', {'price_list_name': 'ShipStation'}):
		return

	price_list = frappe.new_doc("Price List")
	price_list.price_list_name = 'ShipStation'
	price_list.selling = True
	price_list.save()


def setup_custom_fields(args=None):
	common_custom_fields = [
		dict(fieldtype="Data", fieldname="shipstation_store_name", read_only=1,
			label="Shipstation Store", insert_after="sb_shipstation", translatable=0),
		dict(fieldtype="Data", fieldname="shipstation_order_id", read_only=1,
			label="Shipstation Order ID", insert_after="shipstation_store_name",
			translatable=0),
		dict(fieldtype="Column Break", fieldname="cb_shipstation",
			insert_after="shipstation_order_id"),
		dict(fieldtype="Data", fieldname="marketplace", read_only=1,
			label="Marketplace", insert_after="cb_shipstation", translatable=0),
		dict(fieldtype="Data", fieldname="marketplace_order_id", read_only=1,
			label="Marketplace Order ID", insert_after="marketplace",
			translatable=0),
		dict(fieldtype="Check", fieldname="has_pii",
			hidden=1, label="Has PII", insert_after="marketplace_order_id")
	]

	sales_order_fields = [
		dict(fieldtype="Section Break", fieldname="sb_shipstation",
			label="Shipstation", insert_after="tax_id"),
	] + common_custom_fields

	sales_invoice_fields = [
		dict(fieldtype="Section Break", fieldname="sb_shipstation",
			label="Shipstation", insert_after="amended_from"),
	] + common_custom_fields + [
		dict(fieldtype="Data", fieldname="shipstation_shipment_id", read_only=1,
			label="Shipstation Shipment ID", insert_after="shipstation_order_id",
			translatable=0)
	]

	delivery_note_fields = [
		dict(fieldtype="Section Break", fieldname="sb_shipstation",
			label="Shipstation", insert_after="return_against"),
	] + common_custom_fields + [
		dict(fieldtype="Data", fieldname="shipstation_shipment_id", read_only=1,
			label="Shipstation Shipment ID", insert_after="shipstation_order_id",
			translatable=0),
		dict(fieldtype="Section Break", fieldname="shipment_details",
			label="Shipment Details", insert_after="has_pii"),
		dict(fieldtype="Data", fieldname="carrier", read_only=1,
			label="Carrier", insert_after="shipment_details", translatable=0),
		dict(fieldtype="Data", fieldname="tracking_number", read_only=1,
			label="Tracking Number", insert_after="carrier", translatable=0),
		dict(fieldtype="Column Break", fieldname="columnbreak91",
			insert_after="tracking_number"),
		dict(fieldtype="Data", fieldname="carrier_service", read_only=1,
			label="Carrier Service", insert_after="columnbreak91",
			translatable=0),
	]

	custom_fields = {
		"Sales Order": sales_order_fields,
		"Sales Invoice": sales_invoice_fields,
		"Delivery Note": delivery_note_fields
	}

	create_custom_fields(custom_fields)
