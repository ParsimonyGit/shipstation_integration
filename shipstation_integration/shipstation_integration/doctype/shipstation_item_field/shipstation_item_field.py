# Copyright (c) 2023, Parsimony LLC and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document


class ShipstationItemField(Document):

	def get_list(self, args):
		return get_item_fields()

def get_item_fields(search_text=None):
	field_list = [
		{"name": f.fieldname, "fieldname": f.fieldname, "label": f.label}
		for f in frappe.get_meta("Sales Order Item").fields
		if f.fieldtype in ["Data", "Text", "Small Text", "Link", "Select"]
	]
	if search_text:
		field_list = [
			f for f in field_list if search_text.lower() in f["fieldname"].lower() or search_text.lower() in f["label"].lower()
		]
	return field_list