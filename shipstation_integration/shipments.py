import datetime
from typing import TYPE_CHECKING, Optional

from httpx import HTTPError

import frappe
from frappe.utils import getdate
from erpnext.accounts.doctype.sales_invoice.sales_invoice import (
	make_delivery_note as make_delivery_from_invoice,
)
from erpnext.selling.doctype.sales_order.sales_order import (
	make_sales_invoice,
	make_delivery_note as make_delivery_from_order,
)
from erpnext.stock.doctype.delivery_note.delivery_note import make_shipment

if TYPE_CHECKING:
	from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice
	from erpnext.stock.doctype.delivery_note.delivery_note import DeliveryNote
	from erpnext.stock.doctype.shipment.shipment import Shipment
	from shipstation.models import ShipStationOrder
	from shipstation_integration.shipstation_integration.doctype.shipstation_store.shipstation_store import (
		ShipstationStore,
	)
	from shipstation_integration.shipstation_integration.doctype.shipstation_settings.shipstation_settings import (
		ShipstationSettings,
	)


def list_shipments(
	settings: "ShipstationSettings" = None,
	last_shipment_datetime: "datetime.datetime" = None,
):
	"""
	Fetch Shipstation shipments and create Sales Invoice and Delivery Note documents.

	By default, only shipments from enabled Shipstation Settings and from the last day
	onwards will be fetched. Optionally, a list of Shipstation Settings instances and
	a custom start date can be passed.

	:param settings: The Shipstation account to use for fetching orders. Defaults to None.
	:param last_order_datetime: The start date for fetching shipments. Defaults to None.
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

		if not last_shipment_datetime:
			# Get data for the last day, Shipstation API behaves oddly when it's a shorter period
			last_shipment_datetime = datetime.datetime.utcnow() - datetime.timedelta(
				hours=24
			)

		store: "ShipstationStore"
		for store in sss_doc.shipstation_stores:
			if not store.enable_shipments or not any(
				[
					store.create_sales_invoice,
					store.create_delivery_note,
					store.create_shipment,
				]
			):
				continue

			parameters = {
				"store_id": store.store_id,
				"create_date_start": last_shipment_datetime,
				"create_date_end": datetime.datetime.utcnow(),
				"include_shipment_items": True,
			}

			try:
				shipments = client.list_shipments(parameters=parameters)
			except HTTPError as e:
				frappe.log_error(
					title="Error while fetching Shipstation shipment", message=e
				)
				continue

			shipment: Optional["ShipStationOrder"]
			for shipment in shipments:
				# sometimes Shipstation will return `None` in the response
				if not shipment:
					continue

				# if a date filter is set in Shipstation Settings, don't create orders before that date
				if (
					sss_doc.since_date
					and getdate(shipment.create_date) < sss_doc.since_date
				):
					continue

				if shipment.voided:
					if frappe.db.exists(
						"Delivery Note",
						{"docstatus": 1, "shipstation_order_id": shipment.order_id},
					):
						cancel_voided_shipments(shipment)
					continue

				create_erpnext_shipment(shipment, store)


def create_erpnext_shipment(shipment: "ShipStationOrder", store: "ShipstationStore"):
	"""
	Create a Delivery Note using shipment data from Shipstation

	Assumptions:
	- Do not create Shipstation orders if it doesn't exist in Parsimony

	:param shipment: The shipment data.
	:param store: The current active Shipstation store.
	"""

	sales_invoice = None
	if store.create_sales_invoice:
		sales_invoice = create_sales_invoice(shipment, store)

	delivery_note = None
	if store.create_delivery_note:
		delivery_note = create_delivery_note(shipment, sales_invoice)

	shipment_doc = None
	if store.create_shipment:
		shipment_doc = create_shipment(shipment, store, delivery_note)

	return shipment_doc


def cancel_voided_shipments(shipment: "ShipStationOrder"):
	existing_shipment = frappe.get_value(
		"Shipment",
		{"docstatus": 1, "shipment_id": shipment.shipment_id},
	)
	if existing_shipment:
		frappe.get_doc("Shipment", existing_shipment).cancel()

	existing_dn = frappe.get_value(
		"Delivery Note",
		{"docstatus": 1, "shipstation_shipment_id": shipment.shipment_id},
	)
	if existing_dn:
		frappe.get_doc("Delivery Note", existing_dn).cancel()

	existing_si = frappe.get_value(
		"Sales Invoice",
		{"docstatus": 1, "shipstation_shipment_id": shipment.shipment_id},
	)
	if existing_si:
		frappe.get_doc("Sales Invoice", existing_si).cancel()


def create_sales_invoice(shipment: "ShipStationOrder", store: "ShipstationStore"):
	existing_si = frappe.get_value(
		"Sales Invoice", {"docstatus": 1, "shipstation_order_id": shipment.order_id}
	)

	if existing_si:
		return frappe.get_doc("Sales Invoice", existing_si)

	so_name = frappe.get_value(
		"Sales Order", {"docstatus": 1, "shipstation_order_id": shipment.order_id}
	)
	if not so_name:
		return

	si: "SalesInvoice" = make_sales_invoice(so_name)
	si.shipstation_shipment_id = shipment.shipment_id
	si.cost_center = store.cost_center

	if shipment.shipment_cost:
		si.append(
			"taxes",
			{
				"charge_type": "Actual",
				"account_head": store.shipping_expense_account,
				"description": "Shipstation Shipping Cost",
				"tax_amount": -shipment.shipment_cost,
				"cost_center": store.cost_center,
			},
		)

	si.save()
	si.submit()
	return si


def create_delivery_note(
	shipment: "ShipStationOrder", sales_invoice: Optional["SalesInvoice"] = None
):
	existing_dn = frappe.get_value(
		"Delivery Note", {"docstatus": 1, "shipstation_order_id": shipment.order_id}
	)

	if existing_dn:
		return frappe.get_doc("Delivery Note", existing_dn)

	if sales_invoice:
		dn: "DeliveryNote" = make_delivery_from_invoice(sales_invoice.name)
	else:
		so_name = frappe.get_value(
			"Sales Order", {"docstatus": 1, "shipstation_order_id": shipment.order_id}
		)
		if not so_name:
			return
		dn: "DeliveryNote" = make_delivery_from_order(so_name)

	dn.shipstation_shipment_id = shipment.shipment_id

	for row in dn.items:
		row.allow_zero_valuation_rate = 1  # if row.rate < 0.001 else 0

	dn.save()
	dn.submit()
	frappe.db.commit()
	return dn


def create_shipment(
	shipment: "ShipStationOrder",
	store: "ShipstationStore",
	delivery_note: Optional["DeliveryNote"] = None,
):
	existing_shipment = frappe.get_all(
		"Shipment",
		filters={"docstatus": 1},
		or_filters={
			"shipment_id": shipment.shipment_id,
			"shipstation_order_id": shipment.order_id,
		},
		pluck="name",
	)

	if existing_shipment:
		shipment_doc: "Shipment" = frappe.get_doc("Shipment", existing_shipment[0])
		return shipment_doc

	if delivery_note:
		shipment_doc: "Shipment" = make_shipment(delivery_note.name)
	else:
		shipment_deliveries = frappe.get_all(
			"Delivery Note",
			filters={"docstatus": 1},
			or_filters={
				"shipstation_order_id": shipment.order_id,
				"shipstation_shipment_id": shipment.shipment_id,
			},
			pluck="name",
		)

		if not shipment_deliveries:
			return

		shipment_doc: "Shipment" = make_shipment(shipment_deliveries[0])

	shipment_doc.update(
		{
			"shipment_id": shipment.shipment_id,
			"pickup_date": shipment.create_date,
			"carrier": shipment.carrier_code,
			"carrier_service": shipment.service_code,
			"awb_number": shipment.tracking_number,
			"shipment_amount": shipment.shipment_cost,
			"service_provider": "Shipstation",
			"incoterm": "DAP (Delivered At Place)",
			"shipstation_store_name": store.store_name,
			"shipstation_order_id": shipment.order_id,
			"marketplace": store.marketplace_name,
			"marketplace_order_id": shipment.order_number,
		}
	)

	if shipment.shipment_items:
		description = ""
		for count, shipment_item in enumerate(shipment.shipment_items, 1):
			stock_uom = frappe.get_value(
				"Item", {"item_name": shipment_item.name}, "stock_uom"
			)
			description += f"{count}. {shipment_item.name} - {shipment_item.quantity} {stock_uom}\n"
		shipment_doc.update({"description_of_content": description})

	if shipment.dimensions:
		if shipment.weight.value:
			weight_in_ounces = shipment.weight.value
			weight_in_pounds = weight_in_ounces / 16
		else:
			weight_in_pounds = 0.01

		shipment_doc.append(
			"shipment_parcel",
			{
				"length": shipment.dimensions.length,
				"width": shipment.dimensions.width,
				"height": shipment.dimensions.height,
				"weight": weight_in_pounds,
			},
		)

	shipment_doc.flags.ignore_mandatory = True
	shipment_doc.run_method("set_missing_values")

	shipment_doc.save()
	shipment_doc.submit()
	frappe.db.commit()

	return shipment_doc
