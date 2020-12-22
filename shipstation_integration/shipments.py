import datetime

import frappe
from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_delivery_note
from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice


def list_shipments(settings=None, last_shipment_datetime=None):
	if not settings:
		settings = frappe.get_all("Shipstation Settings")
	for sss in settings:
		sss_doc = frappe.get_doc("Shipstation Settings", sss.name)
		client = sss_doc.client()
		client.timeout = 60
		if not last_shipment_datetime:
			# Get data for the last day, Shipstation API behaves oddly when it's a shorter period
			last_shipment_datetime = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
		for store in sss_doc.shipstation_stores:
			if not (store.enable_orders or store.enable_shipments):
				continue

			parameters = {
				'store_id': store.store_id,
				'create_date_start': last_shipment_datetime,
				'create_date_end': datetime.datetime.utcnow()
			}

			shipments = client.list_shipments(parameters=parameters)
			for shipment in shipments:
				if frappe.db.exists("Delivery Note",
					{"docstatus": 1, "shipstation_order_id": shipment.order_id}):
					if shipment.voided:
						cancel_voided_shipments(shipment)
				else:
					create_erpnext_shipment(shipment, store)


def create_erpnext_shipment(shipment, store):
	"""
	Create a Delivery Note using shipment data from Shipstation

	Assumptions:
		- Do not create Shipstation orders if it doesn't exist in Parsimony

	Args:
		shipment (ShipStationOrder): The shipment data
		store (ShipStationStore): The current active Shipstation store

	Returns:
		str: The ID of the created Delivery Note, if created, otherwise None
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

	si = make_sales_invoice(so_name)
	si.shipstation_shipment_id = shipment.shipment_id

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
	dn = make_delivery_note(sales_invoice.name)
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
