// Copyright (c) 2023, Parsimony LLC and contributors
// For license information, please see license.txt

frappe.ui.form.on('Shipstation Item Field', {
	// refresh: function(frm) {

	// }
});

frappe.realtime.on('console_log', function(message) {
    console.log(message);
});
