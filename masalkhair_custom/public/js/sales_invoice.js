frappe.ui.form.on("Sales Invoice", {
    refresh: function (frm) {
        frappe.db.get_single_value("Masalkhair Settings", "enable_tax_exclusive_rate").then(function (val) {
            frm._masalkhair_tax_exclusive_enabled = cint(val);
            if (frm.fields_dict.items && frm.fields_dict.items.grid) {
                frm.fields_dict.items.grid.update_docfield_property(
                    "tax_exclusive_rate", "hidden", !cint(val)
                );
                frm.fields_dict.items.grid.refresh();
            }
        });
    },

    validate: function (frm) {
        if (!masalkhair_is_enabled(frm)) return;
        let errors = [];
        (frm.doc.items || []).forEach(function (item, idx) {
            if (cint(item.tax_exclusive) && !flt(item.tax_exclusive_rate)) {
                errors.push(
                    __("Row {0}: {1} — Tax Excl. Rate is required for tax-exclusive items.", [
                        idx + 1,
                        item.item_name || item.item_code,
                    ])
                );
            }
        });
        if (errors.length) {
            frappe.throw(errors.join("<br>"), __("Tax Exclusive Rate Missing"));
        }
    },
});

frappe.ui.form.on("Sales Invoice Item", {
    rate: function (frm, cdt, cdn) {
        if (!masalkhair_is_enabled(frm)) return;
        let item = locals[cdt][cdn];

        if (!cint(item.tax_exclusive)) {
            if (flt(item.tax_exclusive_rate)) {
                let computed = masalkhair_compute_inclusive_rate(frm, item);
                if (flt(item.rate) !== computed) {
                    frappe.model.set_value(cdt, cdn, "tax_exclusive_rate", 0);
                }
            }
            return;
        }

        let discounted_pl = flt(
            item.price_list_rate * (1 - flt(item.discount_percentage) / 100),
            precision("rate", item)
        );

        // Item just fetched from the price list: Rate still holds the raw price-list value
        // and no Tax Excl. Rate has been entered yet. The price-list rate IS the exclusive
        // rate for tax-exclusive items — route it into Tax Excl. Rate (which grosses Rate
        // up by tax) instead of silently leaving the un-grossed value sitting in Rate.
        if (!flt(item.tax_exclusive_rate) && flt(item.rate) === discounted_pl) {
            frappe.model.set_value(cdt, cdn, "tax_exclusive_rate", discounted_pl);
            return;
        }

        let expected_rate = flt(item.tax_exclusive_rate)
            ? masalkhair_compute_inclusive_rate(frm, item)
            : flt(item.price_list_rate);

        if (flt(item.rate) !== expected_rate) {
            frappe.show_alert({
                message: __(
                    "{0} is a tax-exclusive item. Please enter the Tax Excl. Rate instead of editing Rate directly.",
                    [item.item_name || item.item_code]
                ),
                indicator: "orange",
            });
            frappe.model.set_value(cdt, cdn, "rate", expected_rate);
        }
    },

    tax_exclusive_rate: function (frm, cdt, cdn) {
        if (!masalkhair_is_enabled(frm)) return;
        let item = locals[cdt][cdn];

        if (!flt(item.tax_exclusive_rate)) {
            frappe.model.set_value(cdt, cdn, "rate", flt(item.price_list_rate));
            return;
        }

        let inclusive_rate = masalkhair_compute_inclusive_rate(frm, item);
        frappe.model.set_value(cdt, cdn, "rate", inclusive_rate);
    },

    discount_percentage: function (frm, cdt, cdn) {
        if (!masalkhair_is_enabled(frm)) return;
        let item = locals[cdt][cdn];
        if (!cint(item.tax_exclusive)) return;

        let discounted_net = flt(
            item.price_list_rate * (1 - flt(item.discount_percentage) / 100),
            precision("tax_exclusive_rate", item)
        );
        frappe.model.set_value(cdt, cdn, "tax_exclusive_rate", discounted_net);
    },
});

frappe.ui.form.on("Sales Taxes and Charges", {
    rate: function (frm) {
        if (!masalkhair_is_enabled(frm)) return;
        masalkhair_reapply_all_exclusive_rates(frm);
    },
    included_in_print_rate: function (frm) {
        if (!masalkhair_is_enabled(frm)) return;
        masalkhair_reapply_all_exclusive_rates(frm);
    },
});

function masalkhair_is_enabled(frm) {
    // undefined = setting not yet fetched; default to enabled
    return frm._masalkhair_tax_exclusive_enabled !== 0;
}

function masalkhair_reapply_all_exclusive_rates(frm) {
    (frm.doc.items || []).forEach(function (item) {
        if (!flt(item.tax_exclusive_rate)) return;
        let inclusive_rate = masalkhair_compute_inclusive_rate(frm, item);
        if (inclusive_rate && flt(item.rate) !== inclusive_rate) {
            frappe.model.set_value(item.doctype, item.name, "rate", inclusive_rate);
        }
    });
}

function masalkhair_compute_inclusive_rate(frm, item) {
    let fraction = masalkhair_get_tax_fraction(frm, item);
    return flt(item.tax_exclusive_rate * (1 + fraction), precision("rate", item));
}

function masalkhair_get_tax_fraction(frm, item) {
    let fraction = 0.0;

    let item_tax_map = {};
    if (item.item_tax_rate) {
        try {
            item_tax_map = JSON.parse(item.item_tax_rate);
        } catch (e) {}
    }

    (frm.doc.taxes || []).forEach(function (tax) {
        if (!tax.included_in_print_rate) return;
        if (tax.charge_type !== "On Net Total") return;

        let tax_rate =
            item_tax_map[tax.account_head] !== undefined
                ? flt(item_tax_map[tax.account_head])
                : flt(tax.rate);

        fraction += tax_rate / 100;
    });

    return fraction;
}
