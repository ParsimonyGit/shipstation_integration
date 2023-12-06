# Copyright (c) 2020, Parsimony LLC and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.nestedset import get_root_of
from httpx import HTTPError
from shipstation import ShipStation

from shipstation_integration.items import create_item
from shipstation_integration.orders import list_orders
from shipstation_integration.shipments import list_shipments
from shipstation_integration.utils import get_marketplace


class ShipstationSettings(Document):
	@property
	def store_ids(self):
		stores = json.loads(self.store_data)
		stores = [json.loads(s) for s in stores]
		return [s.get("storeId") for s in stores]

	@property
	def active_warehouse_ids(self) -> list[str]:
		warehouse_ids = []

		for warehouse in self.shipstation_warehouses:
			warehouse_id = frappe.db.get_value(
				"Warehouse", warehouse.get("warehouse"), "shipstation_warehouse_id"
			)
			warehouse_ids.append(warehouse_id)

		return warehouse_ids

	def onload(self):
		if self.carrier_data:
			self.set_onload("carriers", self._carrier_data())

	def validate(self):
		self.validate_label_generation()
		self.validate_enabled_stores()
		if self.hours_to_fetch < 24:
			frappe.throw(
				_("Order Age must be greater than or equal to 24 hours"),
				title=_("Invalid Order Age"),
			)

	def before_insert(self):
		self.validate_api_connection()

	def after_insert(self):
		self.update_carriers_and_stores()
		self.update_warehouses()

	@frappe.whitelist()
	def get_orders(self):
		self.validate()
		list_orders(self)

	@frappe.whitelist()
	def get_shipments(self):
		list_shipments(self)

	def client(self):
		return ShipStation(
			key=self.get_password("api_key"),
			secret=self.get_password("api_secret"),
			debug=False,
			timeout=30,
		)

	def validate_label_generation(self):
		if not self.enabled and self.enable_label_generation:
			self.enable_label_generation = False

	def validate_enabled_stores(self):
		for store in self.shipstation_stores:
			if store.enable_shipments and not store.enable_orders:
				store.enable_shipments = False
				store.create_sales_invoice = False
				store.create_delivery_note = False
				store.create_shipment = False

	def validate_api_connection(self):
		try:
			client = self.client()
			client.list_carriers()
		except HTTPError as e:
			if e.response.status_code == 401:
				frappe.throw(_("Invalid API key or secret"))
			else:
				frappe.throw(_(e.text))

	@frappe.whitelist()
	def update_carriers_and_stores(self):
		client = self.client()

		unstructured_carriers = []
		carriers = client.list_carriers()
		for carrier in carriers:
			carrier_dict = carrier._unstructure()
			services = client.list_services(carrier.code)
			carrier_dict["services"] = [s._unstructure() for s in services]
			packages = client.list_packages(carrier.code)
			carrier_dict["packages"] = [p._unstructure() for p in packages]
			unstructured_carriers.append(carrier_dict)

		self.carrier_data = json.dumps(unstructured_carriers)
		self.update_stores()
		self.save()
		return self

	@frappe.whitelist()
	def update_warehouses(self):
		self.shipstation_warehouses = []
		root_warehouse = get_root_of("Warehouse")

		if not frappe.db.exists("Warehouse", {"warehouse_name": "Shipstation Warehouses"}):
			ss_warehouse_doc = frappe.new_doc("Warehouse")
			ss_warehouse_doc.update(
				{
					"warehouse_name": "Shipstation Warehouses",
					"parent_warehouse": root_warehouse,
					"is_group": True,
				}
			)
			ss_warehouse_doc.insert()

		parent_warehouse = frappe.get_doc("Warehouse", {"warehouse_name": "Shipstation Warehouses"})
		warehouses = self.client().list_warehouses()

		for warehouse in warehouses:
			if frappe.db.exists("Warehouse", {"shipstation_warehouse_id": warehouse.warehouse_id}):
				warehouse_doc = frappe.get_doc(
					"Warehouse", {"shipstation_warehouse_id": warehouse.warehouse_id}
				)
			else:
				warehouse_doc = frappe.new_doc("Warehouse")
				warehouse_doc.update(
					{
						"shipstation_warehouse_id": warehouse.warehouse_id,
						"warehouse_name": warehouse.warehouse_name,
						"parent_warehouse": parent_warehouse.name,
					}
				)
				warehouse_doc.insert()

			self.append("shipstation_warehouses", {"warehouse": warehouse_doc.name})

		self.save()

	def update_stores(self):
		stores = self.client().list_stores(show_inactive=False)
		for store in stores:
			store_exists = False
			for ss_store in self.shipstation_stores:
				if store.store_id == ss_store.store_id:
					ss_store.update(
						{
							"marketplace_name": store.marketplace_name,
							"store_name": store.store_name,
						}
					)
					store_exists = True

			if store_exists:
				continue

			if "Amazon" in store.marketplace_name:
				self.append(
					"shipstation_stores",
					{
						"is_amazon_store": 1,
						"amazon_marketplace": store.account_name,
						"enable_orders": 1,
						"store_id": store.store_id,
						"marketplace_name": get_marketplace(id=store.account_name).sales_partner,
						"store_name": store.store_name,
					},
				)
			elif "Shopify" in store.marketplace_name:
				self.append(
					"shipstation_stores",
					{
						"is_shopify_store": 1,
						"enable_orders": 1,
						"store_id": store.store_id,
						"marketplace_name": store.marketplace_name,
						"store_name": store.store_name,
					},
				)
			else:
				self.append(
					"shipstation_stores",
					{
						"enable_orders": 1,
						"store_id": store.store_id,
						"marketplace_name": store.marketplace_name,
						"store_name": store.store_name,
					},
				)

		return self

	@frappe.whitelist()
	def get_items(self):
		products = self.client().list_products()

		if not products.results:
			return "No products found to import"

		for product in products:
			create_item(product, settings=self)

		return f"{len(products.results)} product(s) imported succesfully"

	def _carrier_data(self):
		return json.loads(self.carrier_data)

	def get_carrier_services(self, carrier):
		for ss_carrier in self._carrier_data():
			if carrier in [ss_carrier["name"], ss_carrier["nickname"]]:
				return "\n".join([s["name"] for s in ss_carrier["services"]])

	def get_codes(self, carrier, service, package):
		_carrier, _service, _package = None, None, "Package"
		for ss_carrier in self._carrier_data():
			if carrier in [ss_carrier.get("name"), ss_carrier.get("nickname")]:
				_carrier = ss_carrier["code"]

				for serv in ss_carrier["services"]:
					if serv["name"] == service:
						_service = serv["code"]

				for pack in ss_carrier["packages"]:
					if pack["name"] == package:
						_package = pack["code"]

		return _carrier, _service, _package

	# create custom fields on the Sales Order Item doctype from the item_custom_fields table (for storing Shipstation metadata)
	@frappe.whitelist()
	def update_order_item_custom_fields(self, removed_item_custom_fields=None):
		# first, create any new custom fields
		item_custom_fields = self.item_custom_fields
		insert_after = "shipstation_item_notes"
		item_doctypes = ["Delivery Note Item", "Sales Order Item", "Sales Invoice Item"]

		for field in item_custom_fields:
			field_def = {
				"insert_after": insert_after,
				"label": field.label,
				"fieldtype": field.fieldtype,
				"fieldname": field.fieldname,
				"length": field.length,
				"reqd": field.reqd,
				"hidden": field.hidden,
				"read_only": field.read_only,
				"options": field.options,
				"default": field.default,
				"fetch_from": field.fetch_from,
				"fetch_if_empty": field.fetch_if_empty,
			}

			for dt in item_doctypes:
				if not frappe.db.exists("Custom Field", {"dt": dt, "fieldname": field.fieldname}):
					custom_field = frappe.new_doc("Custom Field")
					custom_field.dt = dt
					custom_field.update(field_def)
					custom_field.insert()
				else:
					custom_field = frappe.get_doc("Custom Field", {"dt": dt, "fieldname": field.fieldname})
					custom_field.update(field_def)
					custom_field.save()

				if frappe.db.exists("Custom Field", {"dt": dt, "fieldname": field.fieldname}):
					insert_after = field.fieldname

		# delete any removed custom fields
		if removed_item_custom_fields:
			# make sure that the removed field is not in the item_custom_fields variable
			removed_item_custom_fields = [
				field
				for field in removed_item_custom_fields
				if field not in [f.fieldname for f in item_custom_fields]
			]

			for fieldname in removed_item_custom_fields:
				for dt in item_doctypes:
					if frappe.db.exists("Custom Field", {"dt": dt, "fieldname": fieldname}):
						frappe.db.delete("Custom Field", {"dt": dt, "fieldname": fieldname})
