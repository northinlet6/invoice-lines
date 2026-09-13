# invoice-lines

Vendors and billing systems get line-item math wrong more often than you'd
expect: a unit price gets updated but the line total doesn't, a quantity
gets edited by hand, a spreadsheet formula points at the wrong cell. By the
time it reaches accounting the invoice just has a total that's off by some
amount nobody can explain.

`invoice-lines` checks a CSV export of invoice line items and tells you
exactly which rows don't add up, so you can catch it before the invoice
gets paid or sent.

## Usage

Input is a CSV with these columns: `description`, `quantity`, `unit_price`,
`line_total`.

```
description,quantity,unit_price,line_total
Consulting hours,10,150.00,1500.00
Widget A,25,4.00,100.50
Support retainer,1,500.00,500.00
```

Run it:

```
$ python -m invoice_lines.cli invoice.csv
row 2: 'Widget A' expected 100.00 but line_total is 100.50 (off by 0.50)
checked 3 line item(s) from invoice.csv
subtotal (as stated):  2100.50
subtotal (recomputed): 2100.00
1 mismatch(es), 0 unreadable row(s)
```

Or as JSON, for feeding into another script or a CI check:

```
$ python -m invoice_lines.cli invoice.csv --json
{
  "file": "invoice.csv",
  "tolerance": "0.01",
  "row_count": 3,
  "mismatches": [
    {
      "row": 2,
      "description": "Widget A",
      "quantity": "25",
      "unit_price": "4.00",
      "line_total": "100.50",
      "expected_total": "100.00",
      "difference": "0.50"
    }
  ],
  "errors": [],
  "subtotal": "2100.50",
  "expected_subtotal": "2100.00",
  "ok": false
}
```

Exit code is `0` when every row checks out, `1` if there are mismatches or
unreadable rows, `2` if the file itself can't be found.

Rounding differences of a cent or less are expected and ignored by default.
Adjust with `--tolerance`:

```
$ python -m invoice_lines.cli invoice.csv --tolerance 0.05
```

## Why not just eyeball it

For a five-line invoice, sure. This is for the case where someone hands you
a 200-line export and asks "does this total look right to you," and you'd
rather not add it up by hand.

## Requirements

Python 3.9+. No third-party dependencies.

## Status

Early. Currently handles the single case of `quantity * unit_price ==
line_total`. See the issues for what's planned next (tax lines, discounts,
multiple currencies).

## License

MIT, see LICENSE.
