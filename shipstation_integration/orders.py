import datetime

import frappe
from shipstation_integration.customer import create_customer, get_billing_address, update_customer_details
from shipstation_integration.items import create_item
from frappe.utils import getdate


def list_orders(settings=None, last_order_datetime=None):
	if not settings:
		settings = frappe.get_all("Shipstation Settings")
	for sss in settings:
		sss_doc = frappe.get_doc("Shipstation Settings", sss.name)
		client = sss_doc.client()
		client.timeout = 60
		if not last_order_datetime:
			# Get data for the last day, Shipstation API behaves oddly when it's a shorter period
			last_order_datetime = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
		for store in sss_doc.shipstation_stores:
			if not store.enable_orders:
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
		# allow other apps to run validations on Shipstation-Amazon orders
		# if orders don't need to be created, stop process flow
		process_hook = frappe.get_hooks("process_shipstation_amazon_order")
		if process_hook:
			should_create_order = frappe.get_attr(process_hook[0])(store, order, update_customer_details)
			if not should_create_order:
				return

	customer = create_customer(order)
	so = frappe.new_doc('Sales Order')
	so.update({
		"shipstation_order_id": order.order_id,
		"marketplace": store.marketplace_name,
		"marketplace_order_id": order.order_number,
		"customer": customer.name,
		"company": store.company,
		"transaction_date": getdate(order.order_date),
		"delivery_date": getdate(order.ship_date),
		"shipping_address_name": customer.customer_primary_address,
		"customer_primary_address": get_billing_address(customer.name),
		"integration_doctype": store.parent_doc.doctype,
		"integration_doc": store.parent,
		"has_pii": True
	})

	if store.is_amazon_store:
		update_hook = frappe.get_hooks("update_shipstation_amazon_order")
		if update_hook:
			so = frappe.get_attr(update_hook[0])(store, order, so)

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
			'description': 'Shipstation Tax Amount',
			'tax_amount': order.tax_amount,
			'cost_center': store.cost_center
		})

	if order.shipping_amount:
		so.append('taxes', {
			'charge_type': 'Actual',
			'account_head': store.shipping_income_account,
			'description': 'Shipstation Shipping Amount',
			'tax_amount': order.shipping_amount,
			'cost_center': store.cost_center
		})

	so.save()
	so.submit()
	frappe.db.commit()
	return so.name
