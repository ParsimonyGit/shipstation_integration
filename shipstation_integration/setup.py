import frappe
from frappe import _


def setup(company):
    """
    Currently unused, can be used when shipstation creds are injected at setup
    """
    if not frappe.db.exists("Shipstation Store", {"company": company}):
        frappe.throw(_("Please setup a Shipstation store for {}".format(company)))

    store = frappe.get_doc('Shipstation Store', {"company": company})
    settings = frappe.get_doc('Shipstation Settings', store.parent)
    company_doc = frappe.get_doc("Company", company)

    if not store.warehouse:
        store.warehouse = frappe.get_single_value("Stock store", 'default_warehouse')
    if not store.expense_account:
        store.expense_account = company_doc.expense_account
    if not store.sales_account:
        store.sales_account = company_doc.sales_account
    if not store.tax_account:
        store.tax_account = frappe.get_value("Account", {'account_name': "Inventory Purchases", 'company': company})

    try:
        settings.update_carriers()
        settings.update_stores()
        settings.create_webhooks()
    except Exception as e:
        frappe.log_error(
            title="Inventory Error: Error setting up Shipstation", message=e
        )
