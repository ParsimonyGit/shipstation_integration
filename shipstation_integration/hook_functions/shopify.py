import frappe


def validate_existing_shopify_document(doctype: str, shopify_order_number: int):
	"""
	Check if a Shipstation document already exists against a Shopify order.

	Args:
		doctype (str): The doctype to check an existing order against.
		shopify_order_number (int): The Shopify order number.

	Returns:
		(list(BaseDocument), BaseDocument, False): The document object if a
			Shipstation order already exists for the Shopify order, otherwise False.
			If Delivery Notes need to be checked, then all found delivery documents
			are returned.
	"""

	existing_docs = frappe.get_all(doctype,
		filters={
			"docstatus": 1,
			"marketplace": "Shopify",
			"marketplace_order_id": shopify_order_number
		})

	if existing_docs:
		if doctype == "Delivery Note":
			return [frappe.get_doc(doctype, doc.name) for doc in existing_docs]
		return frappe.get_doc(doctype, existing_docs[0].name)

	return False
