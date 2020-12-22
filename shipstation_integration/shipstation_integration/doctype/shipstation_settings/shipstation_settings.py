# -*- coding: utf-8 -*-
# Copyright (c) 2020, Parsimony LLC and contributors
# For license information, please see license.txt

import json

from shipstation import ShipStation

import frappe
from frappe import _
from frappe.model.document import Document
from shipstation_integration.items import create_item
from shipstation_integration.orders import list_orders
from shipstation_integration.shipments import list_shipments
from shipstation_integration.utils import get_marketplace


class ShipstationSettings(Document):
	def validate(self):
		if not self.api_key and not self.api_secret:
			frappe.throw(frappe._("API Key and Secret are both required."))

		self.validate_enabled_checks()

	# def before_insert(self):
	# 	create_defaults()

	def client(self):
		return ShipStation(
			key=self.get_password('api_key'),
			secret=self.get_password('api_secret'),
			debug=False,
			timeout=10
		)

	def validate_enabled_checks(self):
		for store in self.shipstation_stores:
			if store.enable_shipments and not store.enable_orders:
				store.enable_shipments = False

	def update_carriers(self):
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

	def update_stores(self):
		self.set("shipstation_stores", [])
		stores = self.client().list_stores(show_inactive=False)
		for store in stores:
			if store.marketplace_name == "Amazon":
				self.append("shipstation_stores", {
					"enabled": 1,
					"is_amazon_store": 1,
					"store_id": store.store_id,
					"marketplace_name": get_marketplace(id=store.account_name).sales_partner,
					"amazon_marketplace": store.account_name,
					"store_name": store.store_name
				})
			else:
				self.append("shipstation_stores", {
					"enabled": 1,
					"store_id": store.store_id,
					"marketplace_name": store.marketplace_name,
					"store_name": store.store_name
				})
		return self

	def get_orders(self):
		list_orders()

	def get_shipments(self):
		list_shipments()

	def get_items(self):
		products = self.client().list_products()
		if not products.results:
			return "No products found to import"
		for product in products:
			create_item(product)
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
			if ss_carrier['name'] == carrier or ss_carrier['nickname'] == carrier:
				_carrier = ss_carrier['code']
				for serv in ss_carrier['services']:
					if serv['name'] == service:
						_service = serv['code']
				for pack in ss_carrier['packages']:
					if pack['name'] == package:
						_package = pack['code']
		return _carrier, _service, _package

	@property
	def shipstation_methods(self):
		return [t.strip() for t in self.trigger_on.split(",")]

	def onload(self):
		if self.carrier_data:
			self.set_onload('carriers', self._carrier_data())

	@property
	def store_ids(self):
		stores = json.loads(self.store_data)
		stores = [json.loads(s) for s in stores]
		return [s['storeId'] for s in stores]
