import frappe


def update_customer_details(existing_so, order):
    existing_so_doc = frappe.get_doc("Sales Order", existing_so)

    contact = create_contact(order, existing_so_doc.amazon_customer)
    existing_so_doc.contact_person = contact.name
    existing_so_doc.shipstation_order_id = order.order_id
    existing_so_doc.has_pii = True

    if order.bill_to.street1:
        bill_address = create_address(
            order.bill_to,
            existing_so_doc.amazon_customer,
            order.customer_email,
            'Billing'
        )
        existing_so_doc.customer_address = bill_address.name
    if order.ship_to.street1:
        ship_address = update_address(
            existing_so_doc.shipping_address_name,
            order.ship_to,
            order.customer_email,
            'Shipping'
        )
        existing_so_doc.shipping_address_name = ship_address.name
    existing_so_doc.flags.ignore_validate_update_after_submit = True
    existing_so_doc.run_method("set_customer_address")
    existing_so_doc.save()


def create_address(address, customer, email, address_type):
    addr = frappe.new_doc("Address")
    addr.append('links', {'link_doctype': 'Customer', 'link_name': customer})
    _update_address(addr, address, email, address_type)
    return addr


def update_address(address_name, address, email, address_type):
    addr = frappe.get_doc("Address", address_name)
    _update_address(addr, address, email, address_type)
    return addr


def _update_address(addr, address, email, address_type):
    addr.address_type = address_type
    addr.address_line1 = address.street1
    addr.address_line2 = address.street2
    addr.address_line3 = address.street3
    addr.city = address.city
    addr.state = address.state
    addr.pin_code = address.postal_code
    addr.country = frappe.get_cached_value('Country', {'code': address.country}, 'name')
    addr.phone = address.phone
    addr.email = email
    try:
        addr.save()
        return addr
    except Exception as e:
        frappe.log_error(title='Error saving Shipstation Address', message=e)


def create_customer(order):
    customer_id = order.customer_id or \
        order.customer_email or \
        order.ship_to.name or \
        frappe.generate_hash("", 10)

    customer_name = order.customer_email or \
        order.customer_id or \
        order.ship_to.name or \
        customer_id

    if frappe.db.exists('Customer', customer_name):
        return frappe.get_doc('Customer', customer_name)

    cust = frappe.new_doc('Customer')
    cust.shipstation_customer_id = customer_id
    cust.customer_name = customer_name
    cust.customer_type = 'Individual'
    cust.customer_group = 'ShipStation'
    cust.territory = 'United States'
    cust.save()
    frappe.db.commit()
    cust.customer_primary_contact = create_contact(order, customer_name).name
    if order.ship_to.street1:
        create_address(
            order.ship_to,
            customer_name,
            order.customer_email,
            'Shipping'
        ).name
    if order.bill_to.street1:
        create_address(
            order.bill_to,
            order.customer_username,
            order.customer_email,
            'Billing'
        ).name

    try:
        cust.save()
        return cust
    except Exception as e:
        frappe.log_error(title='Error saving Shipstation Customer', message=e)


def create_contact(order, customer_name):
    contact = frappe.get_value('Contact Email', {'email_id': customer_name}, 'parent')
    if contact:
        return frappe._dict({"name": contact})
    cont = frappe.new_doc('Contact')
    cont.first_name = order.bill_to.name if order.bill_to.name else 'Not Provided'
    if customer_name:
        cont.append('email_ids', {'email_id': customer_name})
        cont.append('links', {'link_doctype': 'Customer', 'link_name': customer_name})
    try:
        cont.save()
        frappe.db.commit()
        return cont
    except Exception as e:
        frappe.log_error(title='Error saving Shipstation Contact', message=e)


def get_billing_address(customer_name):
    billing_address = frappe.db.sql("""
    SELECT `tabAddress`.name
    FROM `tabDynamic Link`, `tabAddress`
    WHERE `tabDynamic Link`.link_doctype = 'Customer'
    AND `tabDynamic Link`.link_name = %(customer_name)s
    AND `tabAddress`.address_type = 'Billing'
    LIMIT 1
    """, {'customer_name': customer_name}, as_dict=True)
    return billing_address[0].get('name') if billing_address else None
