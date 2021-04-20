import datetime
from typing import TYPE_CHECKING, Union

import frappe
from frappe.utils import getdate
from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_delivery_note
from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

if TYPE_CHECKING:
	from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice
	from erpnext.stock.doctype.delivery_note.delivery_note import DeliveryNote
	from shipstation.models import ShipStationOrder
	from shipstation_integration.shipstation_integration.doctype.shipstation_store.shipstation_store import ShipstationStore
	from shipstation_integration.shipstation_integration.doctype.shipstation_settings.shipstation_settings import ShipstationSettings


def list_shipments(
	settings: "ShipstationSettings" = None,
	last_shipment_datetime: "datetime.datetime" = None
):
	"""
	Fetch Shipstation shipments and create Sales Invoice and Delivery Note documents.

	By default, only shipments from enabled Shipstation Settings and from the last day
	onwards will be fetched. Optionally, a list of Shipstation Settings instances and
	a custom start date can be passed.

	Args:
		settings (ShipstationSettings, optional): The Shipstation account to use for
			fetching orders. Defaults to None.
		last_order_datetime (datetime.datetime, optional): The start date for fetching
			shipments. Defaults to None.
	"""

	if not settings:
		settings = frappe.get_all("Shipstation Settings", filters={"enabled": True})
	elif not isinstance(settings, list):
		settings = [settings]

	for sss in settings:
		sss_doc: "ShipstationSettings" = frappe.get_doc("Shipstation Settings", sss.name)
		if not sss_doc.enabled:
			continue

		client = sss_doc.client()
		client.timeout = 60

		if not last_shipment_datetime:
			# Get data for the last day, Shipstation API behaves oddly when it's a shorter period
			last_shipment_datetime = datetime.datetime.utcnow() - datetime.timedelta(hours=24)

		store: "ShipstationStore"
		for store in sss_doc.shipstation_stores:
			if not (store.enable_orders or store.enable_shipments):
				continue

			parameters = {
				'store_id': store.store_id,
				'create_date_start': last_shipment_datetime,
				'create_date_end': datetime.datetime.utcnow()
			}

			shipments = client.list_shipments(parameters=parameters)
			shipment: "ShipStationOrder"
			for shipment in shipments:
				# if a date filter is set in Shipstation Settings, don't create orders before that date
				if sss_doc.since_date and getdate(shipment.create_date) < sss_doc.since_date:
					continue

				if frappe.db.exists("Delivery Note",
					{"docstatus": 1, "shipstation_order_id": shipment.order_id}):
					if shipment.voided:
						cancel_voided_shipments(shipment)
				else:
					create_erpnext_shipment(shipment, store)


def create_erpnext_shipment(shipment: "ShipStationOrder", store: "ShipstationStore") -> Union[str, None]:
	"""
	Create a Delivery Note using shipment data from Shipstation

	Assumptions:
		- Do not create Shipstation orders if it doesn't exist in Parsimony

	Args:
		shipment (ShipStationOrder): The shipment data.
		store (ShipStationStore): The current active Shipstation store.

	Returns:
		str, None: The ID of the Delivery Note, if created, otherwise None.
	"""

	sales_invoice = create_sales_invoice(shipment, store)
	if not sales_invoice:
		return

	delivery_note = create_delivery_note(shipment, sales_invoice)
	return delivery_note.name


def cancel_voided_shipments(shipment):
	existing_dn = frappe.db.get_value("Delivery Note",
		{"docstatus": 1, "shipstation_shipment_id": shipment.shipment_id})
	if existing_dn:
		frappe.get_doc("Delivery Note", existing_dn).cancel()

	existing_si = frappe.db.get_value("Sales Invoice",
		{"docstatus": 1, "shipstation_shipment_id": shipment.shipment_id})
	if existing_si:
		frappe.get_doc("Sales Invoice", existing_si).cancel()


def create_sales_invoice(shipment, store):
	so_name = frappe.get_value('Sales Order', {'shipstation_order_id': shipment.order_id})
	if not so_name:
		return

	si: "SalesInvoice" = make_sales_invoice(so_name)
	si.shipstation_shipment_id = shipment.shipment_id
	si.cost_center = store.cost_center

	if shipment.shipment_cost:
		si.append('taxes', {
			'charge_type': 'Actual',
			'account_head': store.shipping_expense_account,
			'description': 'Shipstation Shipping Cost',
			'tax_amount': -shipment.shipment_cost,
			'cost_center': store.cost_center
		})

	si.save()
	si.submit()
	return si


def create_delivery_note(shipment, sales_invoice):
	dn: "DeliveryNote" = make_delivery_note(sales_invoice.name)
	dn.shipstation_shipment_id = shipment.shipment_id
	dn.carrier = shipment.carrier_code.upper()
	dn.carrier_service = shipment.service_code.upper()
	dn.tracking_number = shipment.tracking_number

	for row in dn.items:
		row.allow_zero_valuation_rate = 1  # if row.rate < 0.001 else 0

	dn.save()
	dn.submit()
	frappe.db.commit()
	return dn
