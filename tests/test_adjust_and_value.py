import importlib.util
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "scripts" / "adjust_and_value.py"
SPEC = importlib.util.spec_from_file_location("adjust_and_value", MODULE_PATH)
adjust_and_value = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adjust_and_value)


def comp(adjusted_price, *, opposing=False, gross_adj_pct=0):
    return {
        "adjusted_price": adjusted_price,
        "gross_adj_pct": gross_adj_pct,
        "opposing_comp": opposing,
    }


class ReconcileTests(unittest.TestCase):
    def test_includes_opposing_comp_in_range_and_weighted_average(self):
        result = adjust_and_value.reconcile([
            comp(400_000),
            comp(500_000),
            comp(700_000, opposing=True),
        ])

        self.assertEqual(result["indicated_range_low"], 400_000)
        self.assertEqual(result["indicated_range_high"], 700_000)
        self.assertEqual(result["weighted_average"], 533_333)
        self.assertEqual(result["comp_count"], 3)

    def test_opposing_flag_does_not_remove_comp_from_opinion(self):
        result = adjust_and_value.reconcile([
            comp(400_000),
            comp(500_000),
            comp(600_000),
            comp(300_000, opposing=True),
        ])

        self.assertEqual(result["opinion_of_value"], 350_000)
        self.assertIn("lower 2 adjusted comps", result["opinion_basis"])

    def test_requires_at_least_one_adjusted_comp(self):
        with self.assertRaisesRegex(ValueError, "at least one adjusted comp"):
            adjust_and_value.reconcile([])


if __name__ == "__main__":
    unittest.main()
