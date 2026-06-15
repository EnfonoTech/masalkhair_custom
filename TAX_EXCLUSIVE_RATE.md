# Tax Exclusive Rate — Feature Guide

## What it does

By default in ERPNext, when `included_in_print_rate` is ticked on a tax row, every item's
entered `rate` is treated as tax-inclusive (customer price). The engine backs out the net rate automatically.

This feature adds a per-item override: for items marked **Tax Exclusive** in the Item master,
you enter the **net (pre-tax) rate** in the `Tax Excl. Rate` column. The system computes the
tax-inclusive `rate` automatically.

---

## Enable / Disable

Go to **Masalkhair Settings** (search in desk) → toggle **Enable Tax Exclusive Rate**.

| State    | Behavior |
|----------|----------|
| Enabled  | `Tax Excl. Rate` column visible; JS guards and server validation active |
| Disabled | All handlers inactive; column hidden; existing data untouched |

---

## Item Master Setup

Open the Item → tick **Tax Exclusive** checkbox (visible near *Is Sales Item*).

Once ticked, every Sales Invoice line for this item will:
- Fetch `tax_exclusive = 1` automatically (hidden field, via `fetch_from`)
- Require a value in `Tax Excl. Rate` before saving

---

## How the Calculation Works

```
rate = tax_exclusive_rate × (1 + tax_fraction)

tax_fraction = sum of (tax.rate / 100) for each tax row where:
  - included_in_print_rate = YES
  - charge_type = On Net Total
  - (uses Item Tax Template rate if item has one, else global tax rate)
```

**Example — VAT 15%, tax-exclusive item, net rate = 100:**

```
rate         = 100 × 1.15 = 115   ← entered in Rate column (computed)
net_rate     = 115 ÷ 1.15 = 100   ← ERPNext backs this out
tax          = 100 × 15%  = 15
customer pays = 115
```

---

## Discount Interaction

### Row-level discount (`discount_percentage`)

When a percentage discount is entered on the item row, it is applied to `tax_exclusive_rate`
(net rate), not to the final `rate`.

```
tax_exclusive_rate = price_list_rate × (1 − discount% / 100)
rate               = tax_exclusive_rate × (1 + tax_fraction)
```

### Document-level discount (`discount_amount` via `apply_discount_on`)

ERPNext distributes this proportionally to `item.discount_amount` per row without changing
`item.rate` or `item.discount_percentage`. Our logic is unaffected.

---

## Fields Added

| Doctype             | Field              | Type     | Purpose                                      |
|---------------------|--------------------|----------|----------------------------------------------|
| Item                | `tax_exclusive`    | Check    | Master flag — marks item as tax-exclusive     |
| Sales Invoice Item  | `tax_exclusive`    | Check    | Auto-fetched from Item; hidden               |
| Sales Invoice Item  | `tax_exclusive_rate` | Currency | Net rate entered by user; drives `rate`     |

---

## Validations

- Saving a Sales Invoice with a tax-exclusive item and no `Tax Excl. Rate` throws an error (both client and server side).
- Directly editing `Rate` on a tax-exclusive item shows an alert and reverts the change.

---

## After Changing Tax Rate

If the VAT rate on the Taxes table is changed after items are entered:
- Client: rates recompute automatically for all tax-exclusive items.
- Server: `before_validate` recomputes rates on every save as a safety net.
