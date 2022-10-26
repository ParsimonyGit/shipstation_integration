frappe.ui.form.on("Delivery Note", {
	refresh: frm => {
		shipping.shipstation(frm);

		if (frm.doc.docstatus === 1 && frm.doc.shipstation_order_id) {
			frm.add_custom_button(__('Fetch Shipment'), () => {
				frappe.call({
					method: "shipstation_integration.shipping.fetch_shipment",
					args: {
						"delivery_note": frm.doc.name
					},
					freeze: true,
					callback: function(r) {
						if (r.message) {
							frappe.msgprint(`A shipment was fetched from Shipstation and created at ${r.message}`)
						} else {
							frappe.msgprint(`No new shipment(s) were found against Shipstation ID: ${frm.doc.shipstation_order_id.bold()}`)
						}
					}
				});
			}).removeClass("btn-default").addClass("btn-primary");
		}
	}
})
