import frappe
from frappe.tests.utils import FrappeTestCase

from masalkhair_custom.masalkhair_custom.override.sales_invoice import _apply_exclusive_rates


class TestTaxExclusiveRates(FrappeTestCase):
    """The Tax Excl. Rate is the only price input on a tax-exclusive row.

    erpnext must not be left anything in the Discount and Margin section to layer on top
    of the grossed-up rate; these tests pin that down for the two ways it happened in
    production (MK-SI-26-00053 / MK-CN-26-00001).
    """

    def _build_invoice(self, item_code, tax_exclusive_rate, **item_overrides):
        doc = frappe.new_doc("Sales Invoice")
        doc.company = "Masa Al Khair"
        doc.currency = "SAR"
        doc.conversion_rate = 1
        doc.append(
            "taxes",
            {
                "charge_type": "On Net Total",
                "account_head": "VAT 15% - Output - M",
                "description": "VAT 15% - Output",
                "included_in_print_rate": 1,
                "rate": 15,
            },
        )
        row = doc.append(
            "items",
            {
                "item_code": item_code,
                "qty": 1,
                "tax_exclusive": 1,
                "tax_exclusive_rate": tax_exclusive_rate,
            },
        )
        row.update(item_overrides)
        return doc, row

    def test_rate_is_tax_exclusive_rate_grossed_up(self):
        doc, row = self._build_invoice("10196", 3.50)
        _apply_exclusive_rates(doc)

        self.assertEqual(row.rate, 4.02)
        self.assertEqual(row.price_list_rate, 4.02)

    def test_auto_stamped_margin_is_not_charged_twice(self):
        """erpnext stamps margin_type=Amount whenever the grossed-up rate exceeds the
        price-list rate (transaction.js). Left in place it is re-added as
        rate_with_margin = price_list_rate + margin, inflating every invoice."""
        doc, row = self._build_invoice(
            "10196", 3.50, margin_type="Amount", margin_rate_or_amount=0.54, rate_with_margin=4.56
        )
        _apply_exclusive_rates(doc)

        self.assertEqual(row.rate, 4.02)
        self.assertEqual(row.margin_type, "")
        self.assertEqual(row.margin_rate_or_amount, 0)
        self.assertEqual(row.rate_with_margin, 0)

    def test_negative_discount_from_credit_note_is_not_added_back(self):
        """make_return_doc clears pricing_rules, so calculate_margin() returns (0, 0) and
        leaves discount_amount = price_list_rate - rate below zero. erpnext then applies
        rate = rate_with_margin - discount_amount, i.e. it *adds* the discount."""
        doc, row = self._build_invoice(
            "10196",
            3.50,
            qty=-296,
            margin_type="Amount",
            margin_rate_or_amount=0.54,
            discount_amount=-0.54,
        )
        _apply_exclusive_rates(doc)

        self.assertEqual(row.rate, 4.02)
        self.assertEqual(row.discount_amount, 0)
        self.assertEqual(row.discount_percentage, 0)

    def test_non_tax_exclusive_rows_are_left_alone(self):
        # 0011 is not flagged tax_exclusive on the Item master, so the hook must skip it
        # and leave erpnext's genuine margin handling untouched.
        doc, row = self._build_invoice("0011", 0)
        row.tax_exclusive = 0
        row.rate = 11.00
        row.price_list_rate = 10.00
        row.margin_type = "Amount"
        row.margin_rate_or_amount = 1.00
        _apply_exclusive_rates(doc)

        self.assertEqual(row.rate, 11.00)
        self.assertEqual(row.price_list_rate, 10.00)
        self.assertEqual(row.margin_type, "Amount")
