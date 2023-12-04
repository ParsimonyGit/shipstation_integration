import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def get_setup_stages(args=None):
	return [
		{
			"status": _("Creating shipstation masters"),
			"fail_msg": _("Failed to create shipstation masters"),
			"tasks": [
				{
					"fn": create_customer_group,
					"args": args,
					"fail_msg": _("Failed to create Shipstation Customer Group"),
				},
				{
					"fn": create_price_list,
					"args": args,
					"fail_msg": _("Failed to create Shipstation Price List"),
				},
				{
					"fn": setup_custom_fields,
					"args": args,
					"fail_msg": _("Failed to create Shipstation custom fields"),
				},
			],
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


def create_customer_group():
	if frappe.db.get_value("Customer Group", {"customer_group_name": "ShipStation"}):
		return

	customer_group = frappe.new_doc("Customer Group")
	customer_group.customer_group_name = "ShipStation"
	customer_group.parent_customer_group = "All Customer Groups"
	customer_group.save()


def create_price_list():
	if frappe.db.get_value("Price List", {"price_list_name": "ShipStation"}):
		return

	price_list = frappe.new_doc("Price List")
	price_list.price_list_name = "ShipStation"
	price_list.selling = True
	price_list.save()


def setup_custom_fields():
	item_fields = [
		# Integration section
		dict(
			fieldname="sb_integration",
			label="Integration Details",
			fieldtype="Section Break",
			insert_after="description",
			collapsible=1,
		),
		dict(
			fieldname="integration_doctype",
			label="Integration DocType",
			fieldtype="Link",
			options="DocType",
			insert_after="sb_integration",
			hidden=1,
			print_hide=1,
		),
		dict(
			fieldname="integration_doc",
			label="Integration Doc",
			fieldtype="Dynamic Link",
			insert_after="integration_doctype",
			options="integration_doctype",
			read_only=1,
			print_hide=1,
		),
		dict(fieldname="cb_integration", fieldtype="Column Break", insert_after="integration_doc"),
		dict(
			fieldname="store",
			label="Store",
			fieldtype="Data",
			insert_after="cb_integration",
			read_only=1,
			print_hide=1,
			translatable=0,
		),
	]

	warehouse_fields = [
		dict(
			fieldtype="Data",
			fieldname="shipstation_warehouse_id",
			read_only=True,
			label="Shipstation Warehouse ID",
			insert_after="parent_warehouse",
			translatable=False,
		)
	]

	common_custom_sales_fields = [
		dict(
			fieldname="tb_commerce",
			label="E-commerce",
			fieldtype="Tab Break",
			insert_after="company_address_display",
		),
		dict(
			fieldtype="Section Break",
			fieldname="sb_shipstation",
			collapsible=True,
			label="Shipstation",
			insert_after="tb_commerce",
		),
		dict(
			fieldtype="Data",
			fieldname="shipstation_store_name",
			read_only=True,
			label="Shipstation Store",
			insert_after="sb_shipstation",
			translatable=False,
		),
		dict(
			fieldtype="Data",
			fieldname="shipstation_order_id",
			read_only=True,
			label="Shipstation Order ID",
			insert_after="shipstation_store_name",
			in_standard_filter=True,
			translatable=False,
		),
		dict(
			fieldtype="Column Break",
			fieldname="cb_shipstation",
			insert_after="shipstation_order_id",
		),
		dict(
			fieldtype="Data",
			fieldname="marketplace",
			read_only=True,
			label="Marketplace",
			insert_after="cb_shipstation",
			translatable=False,
		),
		dict(
			fieldtype="Data",
			fieldname="marketplace_order_id",
			read_only=True,
			label="Marketplace Order ID",
			insert_after="marketplace",
			translatable=False,
		),
		dict(
			fieldtype="Check",
			fieldname="has_pii",
			hidden=True,
			label="Has PII",
			insert_after="marketplace_order_id",
		),
		dict(
			fieldtype="Section Break",
			fieldname="sb_notes",
			collapsible=True,
			collapsible_depends_on="eval:doc.shipstation_customer_notes || doc.shipstation_internal_notes",
			label="Notes",
			insert_after="has_pii",
			depends_on="eval:doc.shipstation_customer_notes || doc.shipstation_internal_notes",
		),
		dict(
			fieldtype="Long Text",
			fieldname="shipstation_customer_notes",
			read_only=True,
			label="Shipstation Customer Notes",
			insert_after="sb_notes",
			translatable=False,
		),
		dict(
			fieldtype="Column Break",
			fieldname="cb_notes",
			insert_after="shipstation_customer_notes",
		),
		dict(
			fieldtype="Long Text",
			fieldname="shipstation_internal_notes",
			read_only=True,
			label="Shipstation Internal Notes",
			insert_after="cb_notes",
			translatable=False,
		),
	]

	common_custom_sales_item_fields = [
		dict(
			fieldtype="Section Break",
			fieldname="sb_shipstation",
			collapsible=True,
			label="Shipstation",
			insert_after="weight_uom",
		),
		dict(
			fieldtype="Data",
			fieldname="shipstation_order_item_id",
			read_only=True,
			label="Shipstation Order Item ID",
			insert_after="sb_shipstation",
			translatable=False,
		),
		dict(
			fieldtype="Long Text",
			fieldname="shipstation_item_notes",
			read_only=True,
			label="Shipstation Item Notes",
			insert_after="shipstation_order_item_id",
			translatable=False,
		),
	]

	sales_order_fields = common_custom_sales_fields
	sales_invoice_fields = common_custom_sales_fields + [
		dict(
			fieldtype="Data",
			fieldname="shipstation_shipment_id",
			read_only=True,
			label="Shipstation Shipment ID",
			insert_after="shipstation_order_id",
			translatable=False,
		)
	]

	delivery_note_fields = common_custom_sales_fields + [
		dict(
			fieldtype="Data",
			fieldname="shipstation_shipment_id",
			read_only=True,
			label="Shipstation Shipment ID",
			insert_after="shipstation_order_id",
			translatable=False,
		)
	]

	shipment_fields = [
		dict(
			fieldtype="Data",
			fieldname="shipstation_store_name",
			read_only=True,
			label="Shipstation Store",
			insert_after="shipment_amount",
			translatable=False,
		),
		dict(
			fieldtype="Data",
			fieldname="shipstation_order_id",
			read_only=True,
			label="Shipstation Order ID",
			insert_after="shipstation_store_name",
			in_standard_filter=True,
			translatable=False,
		),
		dict(
			fieldtype="Data",
			fieldname="marketplace",
			read_only=True,
			label="Marketplace",
			insert_after="awb_number",
			translatable=False,
		),
		dict(
			fieldtype="Data",
			fieldname="marketplace_order_id",
			read_only=True,
			label="Marketplace Order ID",
			insert_after="marketplace",
			translatable=False,
		),
	]

	custom_fields = {
		"Item": item_fields,
		"Warehouse": warehouse_fields,
		"Sales Order": sales_order_fields,
		"Sales Order Item": common_custom_sales_item_fields,
		"Sales Invoice": sales_invoice_fields,
		"Sales Invoice Item": common_custom_sales_item_fields,
		"Delivery Note": delivery_note_fields,
		"Delivery Note Item": common_custom_sales_item_fields,
		"Shipment": shipment_fields,
	}

	# for v13 -> v14 migration, we need to reload the custom field doctype
	frappe.reload_doc("custom", "doctype", "custom_field")

	print("Creating custom fields for Shipstation")
	create_custom_fields(custom_fields)

	property_setters = [
		dict(
			doctype="Shipment Parcel",
			fieldname="length",
			property="label",
			property_type="Text",
			value="Length (Inch)",
		),
		dict(
			doctype="Shipment Parcel",
			fieldname="width",
			property="label",
			property_type="Text",
			value="Width (Inch)",
		),
		dict(
			doctype="Shipment Parcel",
			fieldname="height",
			property="label",
			property_type="Text",
			value="Height (Inch)",
		),
		dict(
			doctype="Shipment Parcel",
			fieldname="weight",
			property="label",
			property_type="Text",
			value="Weight (Pounds)",
		),
	]

	print("Creating property setters for Shipstation")
	for property_setter in property_setters:
		if not frappe.db.exists(
			"Property Setter",
			dict(
				doc_type=property_setter.get("doctype"),
				field_name=property_setter.get("fieldname"),
				property=property_setter.get("property"),
				property_type=property_setter.get("property_type"),
				value=property_setter.get("value"),
			),
		):
			make_property_setter(**property_setter)
