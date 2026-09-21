import os
import tempfile
import unittest
from decimal import Decimal

from invoice_lines.cli import find_mismatches, load_line_items


def write_csv(lines):
    handle = tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, newline="", encoding="utf-8"
    )
    handle.write("\n".join(lines))
    handle.close()
    return handle.name


class LoadLineItemsTests(unittest.TestCase):
    def setUp(self):
        self.paths = []

    def tearDown(self):
        for path in self.paths:
            os.remove(path)

    def make_csv(self, lines):
        path = write_csv(lines)
        self.paths.append(path)
        return path

    def test_loads_valid_rows(self):
        path = self.make_csv(
            [
                "description,quantity,unit_price,line_total",
                "Widget A,10,1.50,15.00",
                "Widget B,2,3.00,6.00",
            ]
        )
        items, errors = load_line_items(path)
        self.assertEqual(errors, [])
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["row"], 2)
        self.assertEqual(items[0]["description"], "Widget A")
        self.assertEqual(items[0]["quantity"], Decimal("10"))
        self.assertEqual(items[0]["unit_price"], Decimal("1.50"))
        self.assertEqual(items[0]["line_total"], Decimal("15.00"))

    def test_missing_required_column_raises_system_exit(self):
        path = self.make_csv(
            [
                "description,quantity,unit_price",
                "Widget A,10,1.50",
            ]
        )
        with self.assertRaises(SystemExit):
            load_line_items(path)

    def test_unparsable_row_becomes_error_and_is_skipped(self):
        path = self.make_csv(
            [
                "description,quantity,unit_price,line_total",
                "Widget A,ten,1.50,15.00",
                "Widget B,2,3.00,6.00",
            ]
        )
        items, errors = load_line_items(path)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["description"], "Widget B")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["row"], 2)
        self.assertIn("quantity", errors[0]["message"])

    def test_strips_whitespace_from_description_and_numbers(self):
        path = self.make_csv(
            [
                "description,quantity,unit_price,line_total",
                " Widget A , 10 , 1.50 , 15.00 ",
            ]
        )
        items, errors = load_line_items(path)
        self.assertEqual(errors, [])
        self.assertEqual(items[0]["description"], "Widget A")
        self.assertEqual(items[0]["quantity"], Decimal("10"))


class FindMismatchesTests(unittest.TestCase):
    def test_no_mismatches_when_totals_match(self):
        items = [
            {
                "row": 2,
                "description": "Widget A",
                "quantity": Decimal("10"),
                "unit_price": Decimal("1.50"),
                "line_total": Decimal("15.00"),
            }
        ]
        self.assertEqual(find_mismatches(items, Decimal("0.01")), [])

    def test_flags_row_outside_tolerance(self):
        items = [
            {
                "row": 2,
                "description": "Widget A",
                "quantity": Decimal("25"),
                "unit_price": Decimal("4.00"),
                "line_total": Decimal("100.50"),
            }
        ]
        mismatches = find_mismatches(items, Decimal("0.01"))
        self.assertEqual(len(mismatches), 1)
        mismatch = mismatches[0]
        self.assertEqual(mismatch["row"], 2)
        self.assertEqual(mismatch["expected_total"], Decimal("100.00"))
        self.assertEqual(mismatch["difference"], Decimal("0.50"))

    def test_difference_within_tolerance_is_not_flagged(self):
        items = [
            {
                "row": 2,
                "description": "Widget A",
                "quantity": Decimal("3"),
                "unit_price": Decimal("0.10"),
                "line_total": Decimal("0.29"),
            }
        ]
        self.assertEqual(find_mismatches(items, Decimal("0.01")), [])

    def test_negative_difference_is_flagged_by_absolute_value(self):
        items = [
            {
                "row": 2,
                "description": "Widget A",
                "quantity": Decimal("1"),
                "unit_price": Decimal("10.00"),
                "line_total": Decimal("12.00"),
            }
        ]
        mismatches = find_mismatches(items, Decimal("0.01"))
        self.assertEqual(len(mismatches), 1)
        self.assertEqual(mismatches[0]["difference"], Decimal("2.00"))

    def test_multiple_items_only_mismatches_returned(self):
        items = [
            {
                "row": 2,
                "description": "Good",
                "quantity": Decimal("1"),
                "unit_price": Decimal("5.00"),
                "line_total": Decimal("5.00"),
            },
            {
                "row": 3,
                "description": "Bad",
                "quantity": Decimal("1"),
                "unit_price": Decimal("5.00"),
                "line_total": Decimal("6.00"),
            },
        ]
        mismatches = find_mismatches(items, Decimal("0.01"))
        self.assertEqual([m["row"] for m in mismatches], [3])


if __name__ == "__main__":
    unittest.main()
