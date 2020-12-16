import json
from io import BytesIO

from shipstation.models import ShipStationAddress, ShipStationOrder, ShipStationWeight
from six import string_types

import frappe
from erpnext.selling.doctype.sales_order.sales_order import SalesOrder
from frappe import _
from frappe.contacts.doctype.address.address import Address
from frappe.utils.data import get_datetime, today
from frappe.utils.file_manager import save_file


@frappe.whitelist()  # scheduled daily
def update_carriers():
    sss = frappe.get_list("Shipstation Settings")
    for settings in sss:
        frappe.get_cached_doc(
            'Shipstation Settings', settings.name
        ).update_carriers().save()
        frappe.get_cached_doc(
            'Shipstation Settings', settings.name
        ).update_stores().save()


@frappe.whitelist()
def create_shipping_label(doc, values):
    create_shipping_label_folder()
    _create_shipping_label(doc, values, user=frappe.session.user)


def create_shipping_label_folder():
    if not frappe.db.get_value("File", "Home/Shipstation Labels"):
        folder = frappe.new_doc("File").update(
            {"file_name": "Shipstation Labels", "is_folder": True, "folder": "Home"}
        ).save()


def _create_shipping_label(doc, values, user=None):
    if isinstance(doc, string_types):
        doc = frappe._dict(json.loads(doc))
        values = frappe._dict(json.loads(values))

    values.package = 'package' if values.package.lower() == 'package' else values.package
    doc.carrier_service = values.service
    doc.package_code = values.package
    if not doc.ship_method_type:
        doc.ship_method_type = values.ship_method_type

    ss = frappe.get_cached_doc('Shipstation Settings', doc.company)
    client = ss.client()
    client.timeout = 30

    # build the shipstation label payload
    if doc.shipstation_order_id:
        shipstation_order = client.get_order(doc.shipstation_order_id)
    else:
        shipstation_order = make_shipstation_order(doc)

    if not shipstation_order.ship_date or shipstation_order.ship_date < get_datetime(today()):
        shipstation_order.ship_date = get_datetime(doc.delivery_date or today())

    shipstation_order.weight = ShipStationWeight(value=values.gross_weight, units='pounds')

    # generate and save the shipping label for the order
    pdf = client.create_label_for_order(shipstation_order, test_label=True, pdf=True)

    if not isinstance(pdf, BytesIO):
        message = "There was an error generating the label. Please contact your administrator."
        if isinstance(pdf, dict) and pdf.get("ExceptionMessage"):
            message = pdf.get("ExceptionMessage")
        frappe.throw(_(message))

    file = save_file(doc.name + "_shipstation.pdf", pdf.getvalue(), doc.doctype,
        doc.name, folder="Home/Shipstation Labels", decode=False, is_private=0, df=None)

    if user:
        push_attachment_update(file, user)


@frappe.whitelist()
def get_shipstation_address(doc, persons_name=None):
    if not isinstance(doc, Address):
        frappe.throw("An address object is required")
    country_code = frappe.get_value("Country", doc.country, "code").upper()
    if not persons_name and not doc.address_title:
        frappe.throw('Please edit this address to have either a persons name or address title.')
    name = persons_name if persons_name else doc.address_title
    company = doc.address_title if persons_name else None
    return ShipStationAddress(
        name=name,
        company=company,
        street1=doc.address_line1,
        street2=doc.address_line2,
        city=doc.city,
        state=doc.state,
        postal_code=doc.pincode,
        phone=doc.phone,
        country=country_code
    )


@frappe.whitelist()
def make_shipstation_order(doc):
    sso = ShipStationOrder(order_number=doc.name)
    sso.order_date = get_datetime(doc.transaction_date)
    sso.ship_date = get_datetime(doc.delivery_date)
    sso.order_status = 'awaiting_shipment'
    sso.ship_to = get_shipstation_address(
        frappe.get_doc("Address", doc.shipping_address_name)
    )
    sso.bill_to = get_shipstation_address(
        frappe.get_doc("Address", doc.customer_address),
        doc.contact
    )
    ss = frappe.get_cached_doc('Shipstation Settings', doc.company)
    carrier_code = [c['code'] for c in ss._carrier_data()
        if c['name'] == doc.ship_method_type or c['nickname'] == doc.ship_method_type]
    if doc.ship_method_type and doc.carrier_service:
        sso.carrier_code, sso.service_code, sso.package_code = ss.get_codes(
            doc.ship_method_type, doc.carrier_service, doc.package_code
        )
    sso.package_code = doc.package_code if doc.get('package_code') else 'package'
    if doc.shipstation_order_id:
        sso.order_id = doc.shipstation_order_id
    return sso


@frappe.whitelist()
def get_carrier_services(company):
    shipstation_settings = frappe.db.get_value("Shipstation Store", {"company": company}, "parent")
    return frappe.get_doc("Shipstation Settings", shipstation_settings)._carrier_data()


@frappe.whitelist()
def push_attachment_update(attachment, user):
    js = "if(cur_frm.doc.name =='" + \
        attachment.attached_to_name + \
        "'){cur_frm.refresh()}"
    frappe.publish_realtime("eval_js", js, user=frappe.session.user)
