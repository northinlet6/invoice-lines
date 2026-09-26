"""Check invoice line items for arithmetic mistakes.

Reads a CSV of line items (description, quantity, unit_price, line_total)
and flags any row where quantity * unit_price does not match the stated
line_total, within a small tolerance for rounding. An optional per-row
tax_rate column is folded into the expected total when present.
"""

import argparse
import csv
import json
import sys
from decimal import Decimal, InvalidOperation

REQUIRED_COLUMNS = ("description", "quantity", "unit_price", "line_total")

CENT = Decimal("0.01")


class RowError(Exception):
    def __init__(self, row_number, message):
        super().__init__(message)
        self.row_number = row_number
        self.message = message


def parse_decimal(value, field_name, row_number):
    try:
        return Decimal(value.strip())
    except (InvalidOperation, AttributeError):
        raise RowError(row_number, f"invalid {field_name}: {value!r}")


def load_line_items(path):
    """Return (items, errors). items are valid rows; errors are unparsable rows.

    Reading continues past a bad row so one typo doesn't hide problems in
    the rest of the file.
    """
    items = []
    errors = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(
                f"invoice-lines: missing required column(s): {', '.join(missing)}"
            )
        has_tax_rate = "tax_rate" in (reader.fieldnames or [])
        for row_number, row in enumerate(reader, start=2):
            try:
                quantity = parse_decimal(row["quantity"], "quantity", row_number)
                unit_price = parse_decimal(row["unit_price"], "unit_price", row_number)
                line_total = parse_decimal(row["line_total"], "line_total", row_number)
                tax_rate = None
                if has_tax_rate:
                    raw_tax_rate = row.get("tax_rate")
                    if raw_tax_rate is not None and raw_tax_rate.strip():
                        tax_rate = parse_decimal(raw_tax_rate, "tax_rate", row_number)
                    else:
                        tax_rate = Decimal("0")
            except RowError as exc:
                errors.append({"row": exc.row_number, "message": exc.message})
                continue
            item = {
                "row": row_number,
                "description": row["description"].strip(),
                "quantity": quantity,
                "unit_price": unit_price,
                "line_total": line_total,
            }
            if tax_rate is not None:
                item["tax_rate"] = tax_rate
            items.append(item)
    return items, errors


def expected_total(item):
    """Quantity * unit price, plus tax if the row carries a tax_rate."""
    base = item["quantity"] * item["unit_price"]
    tax_rate = item.get("tax_rate")
    if tax_rate is None:
        return base
    return base * (1 + tax_rate)


def find_mismatches(items, tolerance):
    mismatches = []
    for item in items:
        expected = expected_total(item)
        difference = (expected - item["line_total"]).copy_abs()
        if difference > tolerance:
            mismatch = {
                "row": item["row"],
                "description": item["description"],
                "quantity": item["quantity"],
                "unit_price": item["unit_price"],
                "line_total": item["line_total"],
                "expected_total": expected.quantize(CENT),
                "difference": difference.quantize(CENT),
            }
            if "tax_rate" in item:
                mismatch["tax_rate"] = item["tax_rate"]
            mismatches.append(mismatch)
    return mismatches


def build_report(path, items, errors, mismatches, tolerance):
    subtotal = sum((item["line_total"] for item in items), Decimal("0")).quantize(CENT)
    expected_subtotal = sum(
        (expected_total(item) for item in items), Decimal("0")
    ).quantize(CENT)
    return {
        "file": path,
        "tolerance": str(tolerance),
        "row_count": len(items),
        "mismatches": mismatches,
        "errors": errors,
        "subtotal": str(subtotal),
        "expected_subtotal": str(expected_subtotal),
        "ok": not mismatches and not errors,
    }


def decimalize(value):
    """Make a report JSON-safe by turning Decimals into strings."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: decimalize(val) for key, val in value.items()}
    if isinstance(value, list):
        return [decimalize(val) for val in value]
    return value


def print_human_report(report):
    for error in report["errors"]:
        print(f"row {error['row']}: {error['message']}")

    for mismatch in report["mismatches"]:
        print(
            f"row {mismatch['row']}: {mismatch['description']!r} "
            f"expected {mismatch['expected_total']} but line_total is "
            f"{mismatch['line_total']} (off by {mismatch['difference']})"
        )

    print(f"checked {report['row_count']} line item(s) from {report['file']}")
    print(f"subtotal (as stated):  {report['subtotal']}")
    print(f"subtotal (recomputed): {report['expected_subtotal']}")
    if report["ok"]:
        print("no problems found")
    else:
        print(
            f"{len(report['mismatches'])} mismatch(es), "
            f"{len(report['errors'])} unreadable row(s)"
        )


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="invoice-lines",
        description="Check that invoice line items add up correctly.",
    )
    parser.add_argument("csv_file", help="path to a CSV of line items")
    parser.add_argument(
        "--tolerance",
        default="0.01",
        help="allowed rounding difference before a row counts as a mismatch (default: 0.01)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print a machine-readable JSON report instead of plain text",
    )
    args = parser.parse_args(argv)

    try:
        tolerance = Decimal(args.tolerance)
    except InvalidOperation:
        parser.error(f"--tolerance must be a number, got {args.tolerance!r}")

    try:
        items, errors = load_line_items(args.csv_file)
    except FileNotFoundError:
        message = f"invoice-lines: no such file: {args.csv_file}"
        if args.json:
            print(json.dumps({"error": message}))
        else:
            print(message, file=sys.stderr)
        return 2

    mismatches = find_mismatches(items, tolerance)
    report = build_report(args.csv_file, items, errors, mismatches, tolerance)

    if args.json:
        print(json.dumps(decimalize(report), indent=2))
    else:
        print_human_report(report)

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
