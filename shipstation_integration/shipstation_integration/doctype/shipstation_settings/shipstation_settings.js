// Copyright (c) 2020 Parsimony, LLC and contributors
// For license information, please see license.txt

function company_query(frm, cdt, cdn) {
    const row = frm.selected_doc || locals[cdt][cdn];
    return {
        filters: {
            "company": row.company,
            "is_group": 0
        }
    };
}

frappe.ui.form.on("Shipstation Settings", {
    setup: frm => {
        frm.set_query("shipstation_warehouses", { "shipstation_warehouse_id": ["!=", ""] });
        frm.set_query("cost_center", "shipstation_stores", company_query);
        frm.set_query("warehouse", "shipstation_stores", company_query);
        frm.set_query("tax_account", "shipstation_stores", company_query);
        frm.set_query("sales_account", "shipstation_stores", company_query);
        frm.set_query("expense_account", "shipstation_stores", company_query);
        frm.set_query("shipping_income_account", "shipstation_stores", company_query);
        frm.set_query("shipping_expense_account", "shipstation_stores", company_query);
        // frm.set_query("sales_order_item_field", "options_import", function() {
        //     return {
        //         query: "shipstation_integration.shipstation_integration.doctype.shipstation_settings.shipstation_settings.get_item_fields"
        //     };
        // });
    },

    after_save: frm => {
        frm.trigger("toggle_mandatory_table_fields");
    },

    refresh: frm => {
        frm.trigger("toggle_mandatory_table_fields");
        if (frm.doc.carrier_data) {
            let wrapper = $(frm.fields_dict["carriers_html"].wrapper);
            wrapper.html(frappe.render_template("carriers", { "carriers": frm.doc.__onload.carriers }));
        }
    },

    update_carriers_and_stores: frm => {
        frappe.show_alert("Updating Carriers and Stores")
        frm.call({
            doc: frm.doc,
            method: "update_carriers_and_stores",
            freeze: true
        }).done(() => { frm.reload_doc() })
    },

    get_items: frm => {
        frappe.show_alert("Getting Items");
        frm.call({
            doc: frm.doc,
            method: "get_items",
            freeze: true
        }).done((r) => { frappe.show_alert(r.message) })
    },

    get_orders: frm => {
        frappe.show_alert("Getting Orders");
        frm.call({
            doc: frm.doc,
            method: "get_orders",
            freeze: true
        })
    },

    get_shipments: frm => {
        frappe.show_alert("Getting Shipments");
        frm.call({
            doc: frm.doc,
            method: "get_shipments",
            freeze: true
        })
    },

    fetch_warehouses: frm => {
        frm.call({
            doc: frm.doc,
            method: "update_warehouses",
            freeze: true
        })
    },

    update_order_item_custom_fields: frm => {
        frm.call({
            doc: frm.doc,
            method: "update_order_item_custom_fields",
            freeze: true
        })
    },

    reset_warehouses: frm => {
        frm.set_value("shipstation_warehouses", []);
        frm.save();
    },

    toggle_mandatory_table_fields: frm => {
        frm.fields_dict.shipstation_stores.grid.toggle_reqd("company", !frm.is_new());
        frm.fields_dict.shipstation_stores.grid.toggle_reqd("warehouse", !frm.is_new());
        frm.fields_dict.shipstation_stores.grid.toggle_reqd("cost_center", !frm.is_new());
        frm.fields_dict.shipstation_stores.grid.toggle_reqd("shipping_income_account", !frm.is_new());
        frm.fields_dict.shipstation_stores.grid.toggle_reqd("shipping_expense_account", !frm.is_new());
        frm.fields_dict.shipstation_stores.grid.toggle_reqd("tax_account", !frm.is_new());
        frm.fields_dict.shipstation_stores.grid.toggle_reqd("sales_account", !frm.is_new());
        frm.fields_dict.shipstation_stores.grid.toggle_reqd("expense_account", !frm.is_new());
    }

});

// frappe.ui.form.on("Shipstation Options Import", {
//     form_render(frm, doctype, docname) {
//         // Render a select field for Sales Order Item Field instead of Data Input for better UX
//         let field = frm.cur_grid.grid_form.fields_dict.sales_order_item_field;
//         $(field.input).hide();

//         let $field_select = $(`<select class="form-control">`);
//         field.$input_wrapper.append($field_select);

//         let row = frappe.get_doc(doctype, docname);
//         let curr_value = null;
//         if (row.sales_order_item_field) {
//             curr_value = row.sales_order_item_field;
//         }

//         function update_fieldname_options() {
//             $field_select.find("option").remove();

//             // let link_fieldname = $doctype_select.val();
//             // if (!link_fieldname) return;
//             // let link_field = frm.doc.fields.find((df) => df.fieldname === link_fieldname);
//             // let link_doctype = link_field.options;
//             frappe.model.with_doctype("Sales Order Item", () => {
//                 let fields = frappe.meta
//                     .get_docfields(link_doctype, null, {
//                         fieldtype: ["not in", frappe.model.no_value_type],
//                     })
//                     .map((df) => ({
//                         label: `${df.label} (${df.fieldtype})`,
//                         value: df.fieldname,
//                     }));
//                 $field_select.add_options([{
//                         label: __("Select Field"),
//                         value: "",
//                         selected: true,
//                         disabled: true,
//                     },
//                     ...fields,
//                 ]);

//                 if (curr_value) {
//                     $field_select.val(curr_value);
//                 }
//             });
//         }

//         $field_select.on("change", () => {
//             let sales_order_item_field = $field_select.val();
//             row.sales_order_item_field = sales_order_item_field;
//             frm.dirty();
//         });

//         if (curr_value) {
//             update_fieldname_options();
//         }
//     },

//     // fields_add: (frm) => {
//     // 	frm.trigger("setup_default_views");
//     // },
// });


// frappe.ui.form.on("Shipstation Options Import", {
//     options_import_add: function(frm) {
//         var shipstation_option_name = frm.doc.shipstation_option_name || null;
//         return frappe.call({
//             method: "frappe.custom.doctype.custom_field.custom_field.get_fields_label",
//             args: { doctype: "Sales Order Item", fieldname: shipstation_option_name },
//             callback: function(r) {
//                 if (r) {
//                     var field_labels = r.message;
//                     //set_field_options("sales_order_item_field", field_labels);
//                     frappe.meta.get_docfield("Shipstation Options Import", "sales_order_item_field", frm.doc.name).options = [""].concat(field_labels);
//                     frm.refresh_field("sales_order_item_field");
//                     console.log(field_labels);
//                 }
//             },
//         });
//     },

//     shipstation_option_name: function(frm) {
//         var shipstation_option_name = frm.doc.shipstation_option_name || null;
//         return frappe.call({
//             method: "frappe.custom.doctype.custom_field.custom_field.get_fields_label",
//             args: { doctype: "Sales Order Item", fieldname: shipstation_option_name },
//             callback: function(r) {
//                 if (r) {
//                     // var field_labels = r.message;
//                     // console.log(field_labels);
//                     var field_labels = $.map(r.message, function(v) {
//                         return v.label;
//                     });
//                     set_field_options("sales_order_item_field", field_labels);

//                     if (in_list(field_labels, shipstation_option_name)) {
//                         frm.set_value("sales_order_item_field", shipstation_option_name);
//                     }
//                     frm.refresh_field("sales_order_item_field");
//                 }
//             },
//         });
//     },
// });

// frappe.ui.form.on("Shipstation Options Import", {
//     shipstation_option_name: function(cur_frm, cdt, cdn) {
//         doctype = "Sales Order Item"
//         let row = frappe.get_doc(cdt, cdn);
//         frappe.model.with_doctype(doctype, function() {
//             var options = $.map(frappe.get_meta(doctype).fields,
//                 function(d) {
//                     if (d.fieldname && frappe.model.no_value_type.indexOf(d.fieldtype) === -1) {
//                         return d.fieldname;
//                     }
//                     return null;
//                 }
//             );
//             // console.log("test options select field" + options);

//             frappe.meta.get_docfield("Shipstation Options Import", "sales_order_item_field", cur_frm.doc.name).options = [""].concat(options);

//             // frappe.model.set_value(cdt, cdn, "sales_order_item_field", options);

//             cur_frm.refresh_field("sales_order_item_field");

//         });
//     }
// });