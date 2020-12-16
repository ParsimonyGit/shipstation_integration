frappe.ui.form.on("Delivery Note", {
	refresh: frm => {
		shipping.shipstation(frm);
	}
})
