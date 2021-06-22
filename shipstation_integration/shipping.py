import base64
import json
from io import BytesIO
from typing import TYPE_CHECKING, Dict, List, NoReturn, Optional

from httpx import HTTPError
from shipstation.models import ShipStationAddress, ShipStationOrder, ShipStationWeight

import frappe
from frappe import _
from frappe.contacts.doctype.address.address import Address
from frappe.utils.data import get_datetime, today
from frappe.utils.file_manager import save_file

if TYPE_CHECKING:
	from frappe.core.doctype.file.file import File
	from shipstation_integration.shipstation_integration.doctype.shipstation_settings.shipstation_settings import (
		ShipstationSettings
	)


@frappe.whitelist()
def update_carriers_and_stores():  # scheduled daily
	settings_list: List["ShipstationSettings"] = frappe.get_list("Shipstation Settings")
	for settings in settings_list:
		settings_doc: "ShipstationSettings" = frappe.get_cached_doc(
			"Shipstation Settings", settings.name
		)
		settings_doc.update_carriers_and_stores().save()
		settings_doc.update_stores().save()


@frappe.whitelist()
def create_shipping_label(doc: str, values: str):
	create_shipping_label_folder()
	_create_shipping_label(doc, values, user=frappe.session.user)


def create_shipping_label_folder():
	if not frappe.db.get_value("File", "Home/Shipstation Labels"):
		folder: "File" = frappe.new_doc("File")
		folder.update(
			{"file_name": "Shipstation Labels", "is_folder": True, "folder": "Home"}
		)
		folder.save()


def _create_shipping_label(doc: str, values: str, user: str = str()):
	if isinstance(doc, str):
		doc: frappe._dict = frappe._dict(json.loads(doc))
		values: frappe._dict = frappe._dict(json.loads(values))

	settings_name = get_shipstation_settings(doc)
	if not settings_name:
		frappe.throw(_("No Shipstation order reference found"))

	settings: "ShipstationSettings" = frappe.get_cached_doc(
		"Shipstation Settings", settings_name
	)

	if not settings.enabled:
		return

	values.package = (
		"package" if values.package.lower() == "package" else values.package
	)

	doc.carrier_service = values.service
	doc.package_code = values.package

	if not doc.ship_method_type:
		doc.ship_method_type = values.ship_method_type

	client = settings.client()
	client.timeout = 30

	# build the shipstation label payload
	if doc.shipstation_order_id:
		try:
			shipstation_order = client.get_order(doc.shipstation_order_id)
		except HTTPError as e:
			response = e.response.json()
			process_error(response)
	else:
		shipstation_order = make_shipstation_order(doc)

	update_carrier_code(doc, shipstation_order, settings)

	if not shipstation_order.ship_date or shipstation_order.ship_date < get_datetime(
		today()
	):
		shipstation_order.ship_date = get_datetime(doc.delivery_date or today())

	shipstation_order.weight = ShipStationWeight(
		value=values.gross_weight, units="pounds"
	)

	# generate and save the shipping label for the order
	try:
		shipment = client.create_label_for_order(shipstation_order)
	except HTTPError as e:
		response = e.response.json()
		process_error(response)

	if isinstance(shipment, dict) and shipment.get("ExceptionMessage"):
		process_error(
			shipment,
			message="There was an error generating the label. Please contact your administrator."
		)

	pdf = BytesIO(base64.b64decode(shipment.label_data))
	file = attach_shipping_label(pdf, doc.doctype, doc.name)

	if doc.doctype == "Delivery Note":
		frappe.db.set_value(doc.doctype, doc.name, "shipstation_shipment_id", shipment.shipment_id)
		frappe.db.set_value(doc.doctype, doc.name, "carrier", shipment.carrier_code.upper())
		frappe.db.set_value(doc.doctype, doc.name, "carrier_service", shipment.service_code.upper())
		frappe.db.set_value(doc.doctype, doc.name, "tracking_number", shipment.tracking_number)

	if user:
		push_attachment_update(file, user)


def attach_shipping_label(pdf: BytesIO, doctype: str, name: str):
	if not isinstance(pdf, BytesIO):
		process_error(
			pdf,
			message="There was an error attaching the label. Please contact your administrator."
		)

	file: "File" = save_file(
		fname=name + "_shipstation.pdf",
		content=pdf.getvalue(),
		dt=doctype,
		dn=name,
		folder="Home/Shipstation Labels",
		is_private=True
	)

	return file


def process_error(response: Dict, message: str = str()) -> NoReturn:
	if not message:
		message = "There was an error processing the request. Please contact your administrator."
	if isinstance(response, dict) and response.get("ExceptionMessage"):
		message = response.get("ExceptionMessage")
	frappe.throw(_(message))


def update_carrier_code(
	doc: frappe._dict, order: "ShipStationOrder", settings: "ShipstationSettings"
):
	if doc.ship_method_type and doc.carrier_service:
		order.carrier_code, order.service_code, order.package_code = settings.get_codes(
			doc.ship_method_type, doc.carrier_service, doc.package_code
		)


@frappe.whitelist()
def get_shipstation_address(address: Address, person_name: str = str()):
	if not isinstance(address, Address):
		frappe.throw("An address object is required")

	if not person_name and not address.address_title:
		frappe.throw(
			"Please edit this address to have either a person's name or address title."
		)

	name = person_name or address.address_title
	company = address.address_title if person_name else None
	country_code = frappe.get_value("Country", address.country, "code").upper()
	return ShipStationAddress(
		name=name,
		company=company,
		street1=address.address_line1,
		street2=address.address_line2,
		city=address.city,
		state=address.state,
		postal_code=address.pincode,
		phone=address.phone,
		country=country_code
	)


def make_shipstation_order(doc: frappe._dict):
	shipstation_order = ShipStationOrder(order_number=doc.name)
	shipstation_order.order_date = get_datetime(doc.transaction_date)
	shipstation_order.ship_date = get_datetime(doc.delivery_date)
	shipstation_order.order_status = "awaiting_shipment"
	shipstation_order.ship_to = get_shipstation_address(
		frappe.get_doc("Address", doc.shipping_address_name)
	)
	shipstation_order.bill_to = get_shipstation_address(
		frappe.get_doc("Address", doc.customer_address), doc.contact
	)
	shipstation_order.package_code = doc.package_code or "package"
	if doc.shipstation_order_id:
		shipstation_order.order_id = doc.shipstation_order_id
	return shipstation_order


@frappe.whitelist()
def get_carrier_services(settings: str):
	if settings:
		shipstation_settings: "ShipstationSettings" = frappe.get_doc(
			"Shipstation Settings", settings
		)
		return shipstation_settings._carrier_data()


@frappe.whitelist()
def get_shipstation_settings(doc: str) -> Optional[str]:
	if isinstance(doc, str):
		doc = frappe._dict(json.loads(doc))

	settings = None
	if doc.integration_doctype == "Shipstation Settings" and doc.integration_doc:
		settings = doc.integration_doc
	elif doc.shipstation_store_name:
		settings = frappe.db.get_value(
			"Shipstation Store", {"store_name": doc.shipstation_store_name}, "parent"
		)

	return settings


@frappe.whitelist()
def push_attachment_update(attachment: "File", user: str):
	js = f"if (cur_frm.doc.name =='{attachment.attached_to_name}') {{cur_frm.refresh();}}"
	frappe.publish_realtime("eval_js", js, user=user or frappe.session.user)
