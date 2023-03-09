from typing import Union

from shipstation.models import ShipStationItem, ShipStationOrderItem

import frappe


def get_item_alias(product: Union[ShipStationItem, ShipStationOrderItem]):
	# ref: https://github.com/ParsimonyGit/parsimony/
	# check if the Parsimony app is installed on the current site;
	# `frappe.db.table_exists` returns a false positive if any other
	# site on the bench has the Parsimony app installed instead
	if "parsimony" not in frappe.get_installed_apps():
		return

	sku = product.sku and product.sku.strip() or product.name and product.name[:140]
	if not sku:
		return

	item_aliases = frappe.get_all(
		"Item Alias",
		filters={"sku": sku},
		pluck="parent",
	)

	if item_aliases:
		return item_aliases[0]
