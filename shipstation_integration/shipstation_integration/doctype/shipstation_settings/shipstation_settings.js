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