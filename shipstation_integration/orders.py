import datetime
from typing import TYPE_CHECKING, Optional, Union

from httpx import HTTPError

import frappe
from frappe.utils import getdate

from shipstation_integration.customer import (
	create_customer,
	get_billing_address,
	update_customer_details,
)
from shipstation_integration.items import create_item

if TYPE_CHECKING:
	from erpnext.selling.doctype.sales_order.sales_order import SalesOrder
	from shipstation.models import ShipStationOrder, ShipStationOrderItem
	from shipstation_integration.shipstation_integration.doctype.shipstation_store.shipstation_store import (
		ShipstationStore,
	)
	from shipstation_integration.shipstation_integration.doctype.shipstation_settings.shipstation_settings import (
		ShipstationSettings,
	)


def list_orders(
	settings: "ShipstationSettings" = None,
	last_order_datetime: datetime.datetime = None,
):
	"""
	Fetch Shipstation orders and create Sales Orders.

	By default, only orders from enabled Shipstation Settings and from the last day onwards
	will be fetched. Optionally, a list of Shipstation Settings instances and a custom
	start date can be passed.

	Args:
		settings (ShipstationSettings, optional): The Shipstation account to use for
			fetching orders. Defaults to None.
		last_order_datetime (datetime.datetime, optional): The start date for fetching orders.
			Defaults to None.
	"""

	if not settings:
		settings = frappe.get_all("Shipstation Settings", filters={"enabled": True})
	elif not isinstance(settings, list):
		settings = [settings]

	for sss in settings:
		sss_doc: "ShipstationSettings" = frappe.get_doc(
			"Shipstation Settings", sss.name
		)
		if not sss_doc.enabled:
			continue

		client = sss_doc.client()
		client.timeout = 60

		if not last_order_datetime:
			# Get data for the last day, Shipstation API behaves oddly when it's a shorter period
			last_order_datetime = datetime.datetime.utcnow() - datetime.timedelta(
				hours=24
			)

		store: "ShipstationStore"
		for store in sss_doc.shipstation_stores:
			if not store.enable_orders:
				continue

			parameters = {
				"store_id": store.store_id,
				"modify_date_start": last_order_datetime,
				"modify_date_end": datetime.datetime.utcnow(),
			}

			update_parameter_hook = frappe.get_hooks(
				"update_shipstation_list_order_parameters"
			)
			if update_parameter_hook:
				parameters = frappe.get_attr(update_parameter_hook[0])(parameters)

			try:
				orders = client.list_orders(parameters=parameters)
			except HTTPError as e:
				frappe.log_error(
					title="Error while fetching Shipstation orders", message=e
				)
				continue

			order: "ShipStationOrder"
			for order in orders:
				if validate_order(sss_doc, order, store):
					should_create_order = True

					process_order_hook = frappe.get_hooks("process_shipstation_order")
					if process_order_hook:
						should_create_order = frappe.get_attr(process_order_hook[0])(
							order, store
						)

					if should_create_order:
						create_erpnext_order(order, store)


def validate_order(
	settings: "ShipstationSettings",
	order: "ShipStationOrder",
	store: "ShipstationStore",
):
	if not order:
		return False

	# if an order already exists, skip
	if frappe.db.get_value(
		"Sales Order", {"shipstation_order_id": order.order_id, "docstatus": 1}
	):
		return False

	# only create orders for warehouses defined in Shipstation Settings;
	# if no warehouses are set, fetch everything
	if (
		settings.active_warehouse_ids
		and order.advanced_options.warehouse_id not in settings.active_warehouse_ids
	):
		return False

	# if a date filter is set in Shipstation Settings, don't create orders before that date
	if settings.since_date and getdate(order.create_date) < settings.since_date:
		return False

	# allow other apps to run validations on Shipstation-Amazon or Shipstation-Shopify
	# orders; if an order already exists, stop process flow
	process_hook = None
	if store.get("is_amazon_store"):
		process_hook = frappe.get_hooks("process_shipstation_amazon_order")
	elif store.get("is_shopify_store"):
		process_hook = frappe.get_hooks("process_shipstation_shopify_order")

	if process_hook:
		existing_order: Union["SalesOrder", bool] = frappe.get_attr(process_hook[0])(
			store, order, update_customer_details
		)
		return not existing_order

	return True


def create_erpnext_order(
	order: "ShipStationOrder", store: "ShipstationStore"
) -> Optional[str]:
	"""
	Create a Sales Order from a Shipstation order.

	Args:
		order (ShipStationOrder): The Shipstation order.
		store (ShipstationStore): The Shipstation store to set order defaults.

	Returns:
		(str, None): The ID of the created Sales Order. If no items are found, returns None.
	"""

	customer = create_customer(order)
	so: "SalesOrder" = frappe.new_doc("Sales Order")
	so.update(
		{
			"shipstation_store_name": store.store_name,
			"shipstation_order_id": order.order_id,
			"shipstation_customer_notes": getattr(order, "customer_notes", None),
			"shipstation_internal_notes": getattr(order, "internal_notes", None),
			"marketplace": store.marketplace_name,
			"marketplace_order_id": order.order_number,
			"customer": customer.name,
			"company": store.company,
			"transaction_date": getdate(order.order_date),
			"delivery_date": getdate(order.ship_date),
			"shipping_address_name": customer.customer_primary_address,
			"customer_primary_address": get_billing_address(customer.name),
			"integration_doctype": "Shipstation Settings",
			"integration_doc": store.parent,
			"has_pii": True,
		}
	)

	if store.get("is_amazon_store"):
		update_hook = frappe.get_hooks("update_shipstation_amazon_order")
		if update_hook:
			so = frappe.get_attr(update_hook[0])(store, order, so)
	elif store.get("is_shopify_store"):
		update_hook = frappe.get_hooks("update_shipstation_shopify_order")
		if update_hook:
			so = frappe.get_attr(update_hook[0])(store, order, so)

	# using `hasattr` over `getattr` to use type annotations
	order_items = order.items if hasattr(order, "items") else []
	if not order_items:
		return

	process_order_items_hook = frappe.get_hooks("process_shipstation_order_items")
	if process_order_items_hook:
		order_items = frappe.get_attr(process_order_items_hook[0])(order_items)

	for item in order_items:

		if item.quantity < 1:
			continue

		settings = frappe.get_doc("Shipstation Settings", store.parent)
		item_code = create_item(item, settings=settings, store=store)
		item_notes = get_item_notes(item)
		rate = item.unit_price if hasattr(item, "unit_price") else None
		so.append(
			"items",
			{
				"item_code": item_code,
				"qty": item.quantity,
				"uom": frappe.db.get_single_value("Stock Settings", "stock_uom"),
				"conversion_factor": 1,
				"rate": rate,
				"warehouse": store.warehouse,
				"shipstation_order_item_id": item.order_item_id,
				"shipstation_item_notes": item_notes,
			},
		)

	if not so.get("items"):
		return

	so.dont_update_if_missing = ["customer_name", "base_total_in_words"]

	if order.tax_amount:
		so.append(
			"taxes",
			{
				"charge_type": "Actual",
				"account_head": store.tax_account,
				"description": "Shipstation Tax Amount",
				"tax_amount": order.tax_amount,
				"cost_center": store.cost_center,
			},
		)

	if order.shipping_amount:
		so.append(
			"taxes",
			{
				"charge_type": "Actual",
				"account_head": store.shipping_income_account,
				"description": "Shipstation Shipping Amount",
				"tax_amount": order.shipping_amount,
				"cost_center": store.cost_center,
			},
		)

	so.save()

	before_submit_hook = frappe.get_hooks("update_shipstation_order_before_submit")
	if before_submit_hook:
		so = frappe.get_attr(before_submit_hook[0])(store, so)
		so.save()

	so.submit()
	frappe.db.commit()
	return so.name


def get_item_notes(item: "ShipStationOrderItem"):
	notes = None
	item_options = item.options if hasattr(item, "options") else None
	if item_options:
		for option in item_options:
			if option.name == "Description":
				notes = option.value
				break
	return notes
