# -*- coding: utf-8 -*-
# Copyright (c) 2020, Parsimony LLC and contributors
# For license information, please see license.txt

import json

from shipstation import ShipStation

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.nestedset import get_root_of

from shipstation_integration.items import create_item
from shipstation_integration.orders import list_orders
from shipstation_integration.shipments import list_shipments
from shipstation_integration.utils import get_marketplace


class ShipstationSettings(Document):
	@property
	def store_ids(self):
		stores = json.loads(self.store_data)
		stores = [json.loads(s) for s in stores]
		return [s.get('storeId') for s in stores]

	@property
	def active_warehouse_ids(self):
		warehouse_ids = []
		for warehouse in self.shipstation_warehouses:
			warehouse_id = frappe.db.get_value("Warehouse",
				warehouse.get("warehouse"), "shipstation_warehouse_id")
			warehouse_ids.append(warehouse_id)
		return warehouse_ids

	def onload(self):
		if self.carrier_data:
			self.set_onload('carriers', self._carrier_data())

	def validate(self):
		self.validate_enabled_stores()

	def after_insert(self):
		self.update_carriers_and_stores()
		self.update_warehouses()

	def get_orders(self):
		list_orders(self)

	def get_shipments(self):
		list_shipments(self)

	def client(self):
		return ShipStation(
			key=self.get_password('api_key'),
			secret=self.get_password('api_secret'),
			debug=False,
			timeout=30
		)

	def validate_enabled_stores(self):
		for store in self.shipstation_stores:
			if store.enable_shipments and not store.enable_orders:
				store.enable_shipments = False

	def update_carriers_and_stores(self):
		unstructured_carriers = []
		carriers = self.client().list_carriers()
		for carrier in carriers:
			carrier_code = carrier.code
			carrier = carrier._unstructure()
			services = self.client().list_services(carrier_code)
			carrier['services'] = [s._unstructure() for s in services]
			packages = self.client().list_packages(carrier_code)
			carrier['packages'] = [p._unstructure() for p in packages]
			unstructured_carriers.append(carrier)
		self.carrier_data = json.dumps(unstructured_carriers)
		self.update_stores()
		self.save()
		return self

	def update_warehouses(self):
		root_warehouse = get_root_of("Warehouse")
		if not frappe.db.exists("Warehouse", {"warehouse_name": "Shipstation Warehouses"}):
			ss_warehouse_doc = frappe.new_doc("Warehouse")
			ss_warehouse_doc.update({
				"warehouse_name": "Shipstation Warehouses",
				"parent_warehouse": root_warehouse,
				"is_group": True
			})
			ss_warehouse_doc.insert()
		parent_warehouse = frappe.get_doc("Warehouse", {"warehouse_name": "Shipstation Warehouses"})
		warehouses = self.client().list_warehouses()
		for warehouse in warehouses:
			if frappe.db.exists("Warehouse", {"shipstation_warehouse_id": warehouse.warehouse_id}):
				warehouse_doc = frappe.get_doc("Warehouse",
					{"shipstation_warehouse_id": warehouse.warehouse_id})
			else:
				warehouse_doc = frappe.new_doc("Warehouse")
				warehouse_doc.update({
					"shipstation_warehouse_id": warehouse.warehouse_id,
					"warehouse_name": warehouse.warehouse_name,
					"parent_warehouse": parent_warehouse.name
				})
				warehouse_doc.insert()
			self.append("shipstation_warehouses", {"warehouse": warehouse_doc.name})
		self.save()

	def update_stores(self):
		stores = self.client().list_stores(show_inactive=False)
		for store in stores:
			store_exists = False
			for ss_store in self.shipstation_stores:
				if store.store_id == ss_store.store_id:
					ss_store.update({
						"marketplace_name": store.marketplace_name,
						"store_name": store.store_name
					})
					store_exists = True

			if store_exists:
				continue

			if store.marketplace_name == "Amazon":
				self.append("shipstation_stores", {
					"enable_orders": 1,
					"is_amazon_store": 1,
					"store_id": store.store_id,
					"marketplace_name": get_marketplace(id=store.account_name).sales_partner,
					"amazon_marketplace": store.account_name,
					"store_name": store.store_name
				})
			else:
				self.append("shipstation_stores", {
					"enable_orders": 1,
					"store_id": store.store_id,
					"marketplace_name": store.marketplace_name,
					"store_name": store.store_name
				})
		return self

	def get_items(self):
		products = self.client().list_products()
		if not products.results:
			return "No products found to import"
		for product in products:
			create_item(product, settings=self)
		return "{} product(s) imported succesfully".format(len(products.results))

	def _carrier_data(self):
		return json.loads(self.carrier_data)

	def get_carrier_services(self, carrier):
		for ss_carrier in self._carrier_data():
			if carrier in [ss_carrier['name'], ss_carrier['nickname']]:
				return '\n'.join([s['name'] for s in ss_carrier['services']])

	def get_codes(self, carrier, service, package):
		_carrier, _service, _package = None, None, 'Package'
		for ss_carrier in self._carrier_data():
			if carrier in [ss_carrier.get('name'), ss_carrier.get('nickname')]:
				_carrier = ss_carrier['code']
				for serv in ss_carrier['services']:
					if serv['name'] == service:
						_service = serv['code']
				for pack in ss_carrier['packages']:
					if pack['name'] == package:
						_package = pack['code']
		return _carrier, _service, _package
