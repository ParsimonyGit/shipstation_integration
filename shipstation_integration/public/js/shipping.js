if (!window.shipping)
	window.shipping = {};


shipping.shipstation = function (frm) {
	shipping._carrier_options();
	shipping.add_button(frm);
}

shipping.add_button = function (frm) {
	$(".btn").find(".fa-tags").closest('.btn').remove();

	if (frm.doc.docstatus !== 1) {
		return;
	}

	frm.add_custom_button("<i class='fa fa-tags'></i> Shipping Label", function () {
		shipping.dialog(frm);
	});
}

shipping._carrier_options = function () {
	frappe.call({
		method: "shipstation_integration.shipping.get_carrier_services",
		args: { company: frappe.user_defaults.company }
	}).done((r) => {
		if (r.message) {
			shipping.carrier_options = r.message;
		}
	})
}

shipping.dialog = function (frm) {
	let warnings = shipping.get_label_warnings(frm);
	let options = shipping.carrier_options.map(a => a.nickname).join('\n');
	let fields = [
		{ 'fieldname': 'warnings', 'fieldtype': 'HTML' },
		{ 'fieldname': 'sb0', 'fieldtype': 'Section Break' },
		{
			'fieldname': 'ship_method_type',
			'fieldtype': 'Select',
			'label': 'Carrier',
			'options': options,
			'onchange': function () {
				let values = d.get_values()
				if (values.ship_method_type) {
					let carrier = shipping.carrier_options.find(a => a.nickname === values.ship_method_type);
					let packages = carrier.packages.map(a => a.name).join('\n');
					d.set_df_property('package', 'options', packages);
					d.set_df_property('package', 'read_only', 0);
					let services = carrier.services.map(a => a.name).join('\n');
					d.set_df_property('service', 'options', services);
					d.set_df_property('service', 'read_only', 0);
				}
			}
		},
		{ 'fieldname': 'service', 'fieldtype': 'Select', 'label': 'Service', 'read_only': 1 },
		{ 'fieldname': 'package', 'fieldtype': 'Select', 'label': 'Package Type', 'read_only': 1 },
		{ 'fieldname': 'col_1', 'fieldtype': 'Column Break' },
		{ 'fieldname': 'gross_weight', 'fieldtype': 'Float', 'label': 'Gross Weight', 'description': 'Total Net Weight :' + frm.doc.total_net_weight },
		{ 'fieldname': 'total_packages', 'fieldtype': 'Int', 'label': 'Total Packages', 'description': 'Total number of items :' + frm.doc.total_qty },
	];

	let d = new frappe.ui.Dialog({
		title: __("Create and Attach Shipping Label"),
		fields: fields,
		primary_action: function () {
			d.hide();
			shipping.create_shipping_label(frm, d.get_values())
		}
	});

	d.fields_dict.warnings.$wrapper.html(warnings);
	d.show();
	d.$wrapper.find('.modal-dialog').css("width", "900px");
}

shipping.create_shipping_label = function (frm, values) {
	frappe.call({
		method: "shipstation_integration.shipping.create_shipping_label",
		args: { doc: frm.doc, values: values },
		freeze: true
	}).done((r) => {
		if (!r.exc) {
			frm.reload_doc();
		}
	});
}

shipping.get_label_warnings = function (frm) {
	let warnings = '';
	if (frm.doc.customer_address === undefined) {
		warnings += '<p style="color: red;">A customer address is required to create a label.</p>';
	}
	return warnings;
}