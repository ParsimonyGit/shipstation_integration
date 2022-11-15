from typing import TYPE_CHECKING

import frappe
from frappe.utils import getdate, parse_addr

if TYPE_CHECKING:
    from erpnext.selling.doctype.sales_order.sales_order import SalesOrder
    from frappe.contacts.doctype.address.address import Address
    from frappe.contacts.doctype.contact.contact import Contact
    from shipstation.models import ShipStationAddress, ShipStationOrder
    from shipstation_integration.shipstation_integration.doctype.shipstation_store.shipstation_store import (
        ShipstationStore,
    )


def update_customer_details(
    existing_so: str, order: "ShipStationOrder", store: "ShipstationStore"
):
    existing_so_doc: "SalesOrder" = frappe.get_doc("Sales Order", existing_so)

    email_id, user_name = parse_addr(existing_so_doc.amazon_customer)
    if email_id:
        contact = create_contact(order, email_id)
        existing_so_doc.contact_person = contact.name

    existing_so_doc.update(
        {
            "shipstation_order_id": order.order_id,
            "shipstation_store_name": store.store_name,
            "shipstation_customer_notes": getattr(order, "customer_notes", None),
            "shipstation_internal_notes": getattr(order, "internal_notes", None),
            "marketplace_order_id": order.order_number,
            "delivery_date": getdate(order.ship_date),
            "has_pii": True,
            "integration_doctype": "Shipstation Settings",
            "integration_doc": store.parent,
        }
    )

    if order.bill_to and order.bill_to.street1:
        if existing_so_doc.customer_address:
            bill_address = update_address(
                order.bill_to,
                existing_so_doc.customer_address,
                order.customer_email,
                "Billing",
            )
        else:
            bill_address = create_address(
                order.bill_to,
                existing_so_doc.amazon_customer,
                order.customer_email,
                "Billing",
            )
            existing_so_doc.customer_address = bill_address.name
    if order.ship_to and order.ship_to.street1:
        if existing_so_doc.shipping_address_name:
            ship_address = update_address(
                order.ship_to,
                existing_so_doc.shipping_address_name,
                order.customer_email,
                "Shipping",
            )
        else:
            ship_address = create_address(
                order.ship_to,
                existing_so_doc.amazon_customer,
                order.customer_email,
                "Shipping",
            )
            existing_so_doc.shipping_address_name = ship_address.name

    existing_so_doc.flags.ignore_validate_update_after_submit = True
    existing_so_doc.run_method("set_customer_address")
    existing_so_doc.save()
    return existing_so_doc


def create_address(
    address: "ShipStationAddress", customer: str, email: str, address_type: str
):
    addr: "Address" = frappe.new_doc("Address")
    addr.append("links", {"link_doctype": "Customer", "link_name": customer})
    _update_address(address, addr, email, address_type)
    return addr


def update_address(
    address: "ShipStationAddress", address_name: str, email: str, address_type: str
):
    addr: "Address" = frappe.get_doc("Address", address_name)
    _update_address(address, addr, email, address_type)
    return addr


def _update_address(
    address: "ShipStationAddress", addr: "Address", email: str, address_type: str
):
    addr.address_type = address_type
    addr.address_line1 = address.street1
    addr.address_line2 = address.street2
    addr.address_line3 = address.street3
    addr.city = address.city
    addr.state = address.state
    addr.pincode = address.postal_code
    addr.country = frappe.get_cached_value("Country", {"code": address.country}, "name")
    addr.phone = address.phone
    addr.email = email
    try:
        addr.save()
        return addr
    except Exception as e:
        frappe.log_error(title="Error saving Shipstation Address", message=e)


def create_customer(order: "ShipStationOrder"):
    customer_id = (
        order.customer_id
        or order.customer_email
        or order.ship_to.name
        or frappe.generate_hash("", 10)
    )

    customer_name = (
        order.customer_email or order.customer_id or order.ship_to.name or customer_id
    )

    if frappe.db.exists("Customer", customer_name):
        return frappe.get_doc("Customer", customer_name)

    cust = frappe.new_doc("Customer")
    cust.shipstation_customer_id = customer_id
    cust.customer_name = customer_name
    cust.customer_type = "Individual"
    cust.customer_group = "ShipStation"
    cust.territory = "United States"
    cust.save()
    frappe.db.commit()

    email_id, user_name = parse_addr(customer_name)
    if email_id:
        customer_primary_contact = create_contact(order, email_id)
        if customer_primary_contact:
            cust.customer_primary_contact = customer_primary_contact.name

    if order.ship_to.street1:
        create_address(
            order.ship_to, customer_name, order.customer_email, "Shipping"
        ).name
    if order.bill_to.street1:
        create_address(
            order.bill_to, order.customer_username, order.customer_email, "Billing"
        ).name

    try:
        cust.save()
        return cust
    except Exception as e:
        frappe.log_error(title="Error saving Shipstation Customer", message=e)


def create_contact(order: "ShipStationOrder", customer_name: str):
    contact = frappe.get_value("Contact Email", {"email_id": customer_name}, "parent")
    if contact:
        return frappe._dict({"name": contact})
    cont: "Contact" = frappe.new_doc("Contact")
    cont.first_name = order.bill_to.name or "Not Provided"
    for char in "<>":
        cont.first_name = cont.first_name.replace(char, "")
    if customer_name:
        cont.append("email_ids", {"email_id": customer_name})
        cont.append("links", {"link_doctype": "Customer", "link_name": customer_name})
    try:
        cont.save()
        frappe.db.commit()
        return cont
    except Exception as e:
        frappe.log_error(title="Error saving Shipstation Contact", message=e)


def get_billing_address(customer_name: str):
    billing_address = frappe.db.sql(
        """
            SELECT `tabAddress`.name
            FROM `tabDynamic Link`, `tabAddress`
            WHERE `tabDynamic Link`.link_doctype = 'Customer'
            AND `tabDynamic Link`.link_name = %(customer_name)s
            AND `tabAddress`.address_type = 'Billing'
            LIMIT 1
        """,
        {"customer_name": customer_name},
        as_dict=True,
    )
    return billing_address[0].get("name") if billing_address else None
