import datetime

import frappe
from shipstation_integration.customer import create_customer, get_billing_address, update_customer_details
from shipstation_integration.items import create_item
from shipstation_integration.utils import get_marketplace
from frappe.utils import getdate


def list_orders(settings=None, last_order_datetime=None):
	if not settings:
		settings = frappe.get_all("Shipstation Settings")
	for sss in settings:
		sss_doc = frappe.get_doc("Shipstation Settings", sss.name)
		client = sss_doc.client()
		client.timeout = 60
		if not last_order_datetime:
			# Get data for the last day, ShipStation API behaves oddly when it's a shorter period
			last_order_datetime = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
		for store in sss_doc.shipstation_stores:
			if not store.is_enabled:
				continue

			parameters = {
				'store_id': store.store_id,
				'create_date_start': last_order_datetime,
				'create_date_end': datetime.datetime.utcnow()
			}

			orders = client.list_orders(parameters=parameters)
			for order in orders:
				create_erpnext_order(order, store)


def create_erpnext_order(order, store):
	if not order:
		return

	if frappe.db.get_value('Sales Order', {'shipstation_order_id': order.order_id, "docstatus": 1}):
		return

	if store.is_amazon_store:
		is_fbm_enabled = frappe.db.get_value("MWS Setup Marketplace", {
			"enable_orders": True, "parent": store.mws_setup,
			"marketplace_id": store.amazon_marketplace
		}, "pull_fbm_orders")

		if is_fbm_enabled:
			existing_so = frappe.db.get_value('Sales Order',
				{'amazon_order_id': order.order_number, "docstatus": 1})

			if existing_so:
				update_customer_details(existing_so, order)
			else:
				# TODO: figure out a way to rerun this later when
				# the order has been made through the MWS integration;
				# could be done with the `get_missing_data` function
				pass

			return

	customer = create_customer(order)
	so = frappe.new_doc('Sales Order')
	so.update({
		"shipstation_order_id": order.order_id,
		"customer": customer.name,
		"company": store.company,
		"transaction_date": getdate(order.order_date),
		"delivery_date": getdate(order.ship_date),
		"shipping_address_name": customer.customer_primary_address,
		"customer_primary_address": get_billing_address(customer.name),
		"store": store.marketplace_name,
		"integration_doctype": store.parent_doc.doctype,
		"integration_doc": store.parent
	})

	if store.is_amazon_store:
		so.update({
			"customer": get_marketplace(id=store.amazon_marketplace).sales_partner,
			"amazon_order_id": order.order_number,
			"amazon_marketplace": store.amazon_marketplace,
			"amazon_customer": order.customer_email,
			"customer_grand_total": order.amount_paid,
			"has_pii": True
		})

	for row in getattr(order, 'items', []):
		item_code = create_item(row, store)
		rate = getattr(row, "unit_price", 0.0)
		so.append('items', {
			'item_code': item_code,
			'qty': row.quantity,
			'uom': 'Nos',
			'conversion_factor': 1,
			'rate': rate,
			'warehouse': store.warehouse
		})

	if not so.get('items'):
		return

	so.dont_update_if_missing = ['customer_name', 'base_total_in_words']

	if order.tax_amount:
		so.append('taxes', {
			'charge_type': 'Actual',
			'account_head': store.tax_account,
			'description': 'ShipStation Tax Amount',
			'tax_amount': order.tax_amount,
			'cost_center': store.cost_center
		})

	if order.shipping_amount:
		so.append('taxes', {
			'charge_type': 'Actual',
			'account_head': store.shipping_income_account,
			'description': 'ShipStation Shipping Amount',
			'tax_amount': order.shipping_amount,
			'cost_center': store.cost_center
		})

	so.save()
	so.submit()
	frappe.db.commit()
	return so.name


def get_missing_data():
	"""
		TODO:
		1. Made from MWS Integration
		2. Fulfilled by Merchant
		3. Have "missing_customer_data" as 1
	"""
