# # Copyright (c) 2023, Parsimony LLC and contributors
# # For license information, please see license.txt

# # import frappe
# from frappe.model.document import Document

# class ShipstationItemField(Document):
	
# 	def db_insert(self, *args, **kwargs):
# 		pass

# 	def load_from_db(self):
# 		pass

# 	def db_update(self, *args, **kwargs):
# 		pass

# 	@staticmethod
# 	def get_list(args):
# 		pass

# 	@staticmethod
# 	def get_count(args):
# 		pass

# 	@staticmethod
# 	def get_stats(args):
# 		pass

import frappe
import json
from frappe.model.document import Document


class ShipstationItemField(Document):

	@staticmethod
	def get_list(args=None):
		# debug args
		# frappe.msgprint("args: " + str(args))
		# extract the search term from 'or_filters' in the args
		# such as something from 'or_filters': [['Shipstation Item Field', 'name', 'like', '%something%']], 
		or_filters = args.get("or_filters") if args else None
		search_text = ""
		if or_filters:
			search_text = or_filters[0][3].replace("%", "")
			frappe.msgprint("search_text: " + search_text)
		# field_list = [
		# 	{"name": f.fieldname, "fieldname": f.fieldname, "label": f.label}
		# 	for f in frappe.get_meta("Sales Order Item").fields
		# 	if f.fieldtype in ["Data", "Text", "Small Text", "Link", "Select"]
		# ]

		# field_list as list of tuples (fieldname, label)
		field_list = [
			(f.fieldname, f.label)
			for f in frappe.get_meta("Sales Order Item").fields
			if f.fieldtype in ["Data", "Text", "Small Text", "Link", "Select"]
		]

		if search_text:
			field_list = [
				f for f in field_list if search_text.lower() in f["fieldname"].lower() or search_text.lower() in f["label"].lower()
			]
		return field_list
	
	@staticmethod
	def get_count(args=None):
		return len(ShipstationItemField.get_list(args))
	
	@staticmethod
	def get_stats(args=None):
		return ShipstationItemField.get_list(args)

# debug the output from frappe.get_meta("Sales Order Item")
# print each meta object to the console
for field_object in frappe.get_meta("Sales Order Item").fields:
	print(str(field_object.as_dict()))