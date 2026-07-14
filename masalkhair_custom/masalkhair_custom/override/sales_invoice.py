import frappe
from frappe.utils import flt, cint


def before_validate(doc, method=None):
    if not _is_enabled():
        return
    _apply_exclusive_rates(doc)


def validate(doc, method=None):
    if not _is_enabled():
        return
    _validate_exclusive_rates(doc)


def _is_enabled():
    return frappe.db.get_single_value("Masalkhair Settings", "enable_tax_exclusive_rate")


def _validate_exclusive_rates(doc):
    errors = []
    for idx, item in enumerate(doc.items):
        if cint(item.get("tax_exclusive")) and not flt(item.get("tax_exclusive_rate")):
            errors.append(
                f"Row {idx + 1}: {item.item_name or item.item_code} "
                f"— Tax Excl. Rate is required for tax-exclusive items."
            )
    if errors:
        frappe.throw("<br>".join(errors), title="Tax Exclusive Rate Missing")


def _apply_exclusive_rates(doc):
    for item in doc.items:
        # fetch_from only works in the browser; fetch from Item master when missing
        if not cint(item.get("tax_exclusive")):
            item.tax_exclusive = cint(
                frappe.db.get_value("Item", item.item_code, "tax_exclusive") or 0
            )

        if not cint(item.tax_exclusive):
            continue

        # When tax_exclusive_rate is not set, derive it from item.rate.
        # If taxes are included in the print rate the incoming item.rate is already
        # the inclusive (gross) price, so we must extract the exclusive (net) rate by
        # dividing.  Only when there are no included taxes is item.rate already net.
        if not flt(item.get("tax_exclusive_rate")):
            tax_fraction = _get_item_tax_fraction(doc, item)
            if tax_fraction > 0:
                item.tax_exclusive_rate = flt(item.rate / (1 + tax_fraction))
            else:
                item.tax_exclusive_rate = flt(item.rate)

        tax_fraction = _get_item_tax_fraction(doc, item)
        item.rate = flt(item.tax_exclusive_rate * (1 + tax_fraction))
        item.price_list_rate = item.rate  # keep price_list_rate in sync so discount stays 0
        item.amount = flt(item.rate * item.qty)


def _get_item_tax_fraction(doc, item):
    import json

    item_tax_map = {}
    if item.get("item_tax_rate"):
        try:
            item_tax_map = json.loads(item.item_tax_rate)
        except (ValueError, TypeError):
            pass

    fraction = 0.0
    for tax in doc.taxes or []:
        if not tax.included_in_print_rate:
            continue
        if tax.charge_type != "On Net Total":
            continue

        tax_rate = (
            flt(item_tax_map[tax.account_head])
            if tax.account_head in item_tax_map
            else flt(tax.rate)
        )
        fraction += tax_rate / 100

    return fraction
