import json
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from evals.scoring import results_match

GOLDEN_SET = Path(__file__).resolve().parents[1] / "evals" / "golden_set.json"


class ResultsMatchTests(unittest.TestCase):
    def test_extra_columns_and_rounding_are_accepted(self):
        expected = [(Decimal("64.5745032041311516"),)]
        self.assertTrue(results_match(expected, [(64.57,)]))
        self.assertTrue(results_match([(9470, Decimal("1086.19"))], [(9470, "Ann", "Lee", 1086.19)]))

    def test_wrong_values_or_row_counts_fail(self):
        self.assertFalse(results_match([(863,)], [(864,)]))
        self.assertFalse(results_match([(1,), (2,)], [(1,), (2,), (3,)]))
        self.assertFalse(results_match([(4.427,)], [(4.4,)]))  # rounded too far

    def test_order_matters_only_for_rankings(self):
        expected = [("Toronto", 1283), ("Montreal", 1279)]
        swapped = [("Montreal", 1279), ("Toronto", 1283)]
        self.assertTrue(results_match(expected, swapped, ordered=False))
        self.assertFalse(results_match(expected, swapped, ordered=True))

    def test_values_are_normalized(self):
        self.assertTrue(results_match([("credit_card",)], [(" Credit_Card ",)]))
        self.assertTrue(results_match([(date(2026, 1, 1),)], [("2026-01-01",)]))
        self.assertFalse(results_match([(True,)], [(1,)]))


class GoldenSetTests(unittest.TestCase):
    def test_golden_set_is_well_formed(self):
        items = json.loads(GOLDEN_SET.read_text(encoding="utf-8"))
        ids = [item["id"] for item in items]
        self.assertEqual(len(ids), len(set(ids)), "item ids must be unique")
        for item in items:
            self.assertIn(item["kind"], {"sql", "safety", "route"}, item["id"])
            routes = item["route"] if isinstance(item["route"], list) else [item["route"]]
            self.assertTrue(set(routes) <= {"sql", "etl", "chat"}, item["id"])
            if item["kind"] == "sql":
                self.assertTrue(item.get("reference_sql"), item["id"])
