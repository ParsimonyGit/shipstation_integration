frappe.ui.form.on("Sales Order", {
	refresh: (frm) => {
		shipping.shipstation(frm);
	}
})
