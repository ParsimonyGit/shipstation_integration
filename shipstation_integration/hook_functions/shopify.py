import frappe


def validate_existing_shopify_document(shop_name: str, doctype: str, shopify_order_number: int):
	"""
	Reference application: https://github.com/ParsimonyGit/shopify_integration.

	Return Shipstation document(s) against a Shopify order, if they exist and were
	created via Shipstation.

	To allow for multiple Shopify store connections, the shop must be first linked
	to a Shipstation store via the "Shopify Store" field.

	Args:
		shop_name (str): The name of the Shopify configuration for the store.
		doctype (str): The doctype to check an existing order against.
		shopify_order_number (int): The Shopify order number.

	Returns:
		list(BaseDocument) | BaseDocument: The document object if a Shipstation
			order exists for the Shopify order, otherwise an empty list. If
			Delivery Notes need to be checked, then all found delivery documents
			are returned.
	"""

	shopify_docs = []

	existing_docs = frappe.get_all(doctype,
		filters={
			"docstatus": 1,
			"marketplace": "Shopify",
			"marketplace_order_id": shopify_order_number
		},
		fields=["name", "shipstation_store_name"])

	for doc in existing_docs:
		shopify_store = frappe.db.get_value("Shipstation Store", doc.shipstation_store_name, "shopify_store")
		if shopify_store and shopify_store == shop_name:
			shopify_docs.append(doc)

	if shopify_docs:
		if doctype == "Delivery Note":
			return [frappe.get_doc(doctype, doc.name) for doc in shopify_docs]
		return frappe.get_doc(doctype, shopify_docs[0].name)

	return shopify_docs
