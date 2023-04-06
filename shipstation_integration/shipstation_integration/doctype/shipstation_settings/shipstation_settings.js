// Copyright (c) 2020 Parsimony, LLC and contributors
// For license information, please see license.txt

function company_query(frm, cdt, cdn) {
  const row = frm.selected_doc || locals[cdt][cdn];
  return {
    filters: {
      company: row.company,
      is_group: 0,
    },
  };
}

function set_item_field_options(frm) {
  let options_arr = [];
  // delete the "Sales Order Item" doctype meta from locals, to force a reload of the field list
  delete locals.DocType['Sales Order Item'];
  // loads the "Sales Order Item" doctype meta into locals
  frappe.model.with_doctype("Sales Order Item", () => {
    const fieldlist = frappe.get_meta("Sales Order Item").fields;
    // This filters for "Data", "Text", "Small Text", "Link", and "Select."
    const filtered_fieldlist = fieldlist.filter((field) => {
      return ["Data", "Text", "Small Text", "Link", "Select"].includes(field.fieldtype);
    });
    // This maps fieldname and value.
    options_arr = filtered_fieldlist.map((field) => {
      return { value: field.fieldname, label: field.label };
    });
    // This alphanumerically sorts the array by label.
    options_arr = options_arr.sort((a, b) => {
      return a.label.localeCompare(b.label);
    });
    // This updates the individual row's "item_field" field.
    frm.fields_dict.shipstation_options.grid.update_docfield_property("item_field", "options", options_arr);
  });
};

async function update_order_item_custom_fields_on_remove(frm) {
  const opts = {
    doc: frm.doc,
    method: "update_order_item_custom_fields",
    args: { removed_item_custom_fields: locals.removed_item_custom_fields },
    freeze: true,
  };
  await frm.call(opts);
  set_item_field_options(frm);
};

frappe.ui.form.on("Shipstation Settings", {
  setup: (frm) => {
    frm.set_query("shipstation_warehouses", {
      shipstation_warehouse_id: ["!=", ""],
    });
    frm.set_query("cost_center", "shipstation_stores", company_query);
    frm.set_query("warehouse", "shipstation_stores", company_query);
    frm.set_query("tax_account", "shipstation_stores", company_query);
    frm.set_query("sales_account", "shipstation_stores", company_query);
    frm.set_query("expense_account", "shipstation_stores", company_query);
    frm.set_query(
      "shipping_income_account",
      "shipstation_stores",
      company_query,
    );
    frm.set_query(
      "shipping_expense_account",
      "shipstation_stores",
      company_query,
    );
    set_item_field_options(frm);
  },

  on_update: (frm) => {
    update_order_item_custom_fields_on_remove(frm);
  },

  after_save: (frm) => {
    frm.trigger("toggle_mandatory_table_fields");
    update_order_item_custom_fields_on_remove(frm);
  },

  refresh: (frm) => {
    frm.trigger("toggle_mandatory_table_fields");
    if (frm.doc.carrier_data) {
      const wrapper = $(frm.fields_dict.carriers_html.wrapper);
      wrapper.html(
        frappe.render_template("carriers", {
          carriers: frm.doc.__onload.carriers,
        }),
      );
    };
  },

  update_carriers_and_stores: (frm) => {
    frappe.show_alert("Updating Carriers and Stores");
    frm
      .call({
        doc: frm.doc,
        method: "update_carriers_and_stores",
        freeze: true,
      })
      .done(() => {
        frm.reload_doc();
      });
  },

  get_items: (frm) => {
    frappe.show_alert("Getting Items");
    frm
      .call({
        doc: frm.doc,
        method: "get_items",
        freeze: true,
      })
      .done((r) => {
        frappe.show_alert(r.message);
      });
  },

  get_orders: (frm) => {
    frappe.show_alert("Getting Orders");
    frm.call({
      doc: frm.doc,
      method: "get_orders",
      freeze: true,
    });
  },

  get_shipments: (frm) => {
    frappe.show_alert("Getting Shipments");
    frm.call({
      doc: frm.doc,
      method: "get_shipments",
      freeze: true,
    });
  },

  fetch_warehouses: (frm) => {
    frm.call({
      doc: frm.doc,
      method: "update_warehouses",
      freeze: true,
    });
  },

  reset_warehouses: (frm) => {
    frm.set_value("shipstation_warehouses", []);
    frm.save();
  },

  toggle_mandatory_table_fields: (frm) => {
    frm.fields_dict.shipstation_stores.grid.toggle_reqd(
      "company",
      !frm.is_new()
    );
    frm.fields_dict.shipstation_stores.grid.toggle_reqd(
      "warehouse",
      !frm.is_new()
    );
    frm.fields_dict.shipstation_stores.grid.toggle_reqd(
      "cost_center",
      !frm.is_new()
    );
    frm.fields_dict.shipstation_stores.grid.toggle_reqd(
      "shipping_income_account",
      !frm.is_new()
    );
    frm.fields_dict.shipstation_stores.grid.toggle_reqd(
      "shipping_expense_account",
      !frm.is_new()
    );
    frm.fields_dict.shipstation_stores.grid.toggle_reqd(
      "tax_account",
      !frm.is_new()
    );
    frm.fields_dict.shipstation_stores.grid.toggle_reqd(
      "sales_account",
      !frm.is_new()
    );
    frm.fields_dict.shipstation_stores.grid.toggle_reqd(
      "expense_account",
      !frm.is_new()
    );
  },
});

frappe.ui.form.on("Shipstation Item Custom Field", {
  before_item_custom_fields_remove: (frm, cdt, cdn) => {
    const deleted_row = frappe.get_doc(cdt, cdn);
    // Check if there are rows in the shipstation options table that have the deleted fieldname in their "item_field" field.
    const deleted_row_in_use = frm.doc.shipstation_options.find((row) => {
      return row.item_field === deleted_row.fieldname;
    }) !== undefined;
    if (deleted_row_in_use && deleted_row.fieldname) {
      frappe.throw(__(`Cannot delete field ${deleted_row.label} because it is in use.`));
    } else {
      locals.removed_item_custom_fields = locals.removed_item_custom_fields || [];
      locals.removed_item_custom_fields.push(deleted_row.fieldname);
    };
  },
});