import importlib.util
import pathlib
import unittest
from datetime import datetime


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


def subject_characteristics(**overrides):
    values = {
        "living_area_sqft": 1_000,
        "grade": 7,
        "year_built": 1980,
        "bedrooms": 3,
        "bathrooms": 2,
    }
    values.update(overrides)
    return {"characteristics": values}


def sale_comp(**building_overrides):
    building = {
        "sqft": 1_000,
        "grade": 7,
        "year_built": 1980,
        "bedrooms": 3,
        "bathrooms": 2,
    }
    building.update(building_overrides)
    return {
        "pin": "0000000001",
        "sale_price": 500_000,
        "sale_date": "2026-01-01",
        "building": building,
        "opposing_comp": False,
    }


class AdjustmentInputTests(unittest.TestCase):
    assessment_date = datetime(2026, 1, 1)

    def test_missing_subject_bed_and_bath_do_not_become_zero(self):
        subject = subject_characteristics()
        del subject["characteristics"]["bedrooms"]
        del subject["characteristics"]["bathrooms"]

        result = adjust_and_value.adjust_comp(
            subject, sale_comp(), self.assessment_date
        )

        categories = {item["category"] for item in result["adjustments"]}
        self.assertNotIn("Bedrooms", categories)
        self.assertNotIn("Bathrooms", categories)
        self.assertEqual(result["adjusted_price"], 500_000)

    def test_missing_comp_bed_and_bath_do_not_become_zero(self):
        result = adjust_and_value.adjust_comp(
            subject_characteristics(),
            sale_comp(bedrooms=None, bathrooms=None),
            self.assessment_date,
        )

        categories = {item["category"] for item in result["adjustments"]}
        self.assertNotIn("Bedrooms", categories)
        self.assertNotIn("Bathrooms", categories)
        self.assertEqual(result["adjusted_price"], 500_000)

    def test_missing_subject_living_area_fails_closed(self):
        subject = subject_characteristics()
        del subject["characteristics"]["living_area_sqft"]

        with self.assertRaisesRegex(ValueError, "subject living area"):
            adjust_and_value.adjust_comp(
                subject, sale_comp(), self.assessment_date
            )

    def test_missing_comp_grade_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "comp grade"):
            adjust_and_value.adjust_comp(
                subject_characteristics(),
                sale_comp(grade=None),
                self.assessment_date,
            )

    def test_explicit_zero_bedrooms_remains_a_real_value(self):
        result = adjust_and_value.adjust_comp(
            subject_characteristics(bedrooms=0),
            sale_comp(bedrooms=1),
            self.assessment_date,
        )

        bedrooms = next(
            item for item in result["adjustments"] if item["category"] == "Bedrooms"
        )
        self.assertEqual(bedrooms["amount"], -8_000)

    def test_missing_subject_view_does_not_become_no_view(self):
        result = adjust_and_value.adjust_comp(
            subject_characteristics(),
            sale_comp(view_utilization=1),
            self.assessment_date,
        )

        categories = {item["category"] for item in result["adjustments"]}
        self.assertNotIn("View", categories)
        self.assertEqual(result["adjusted_price"], 500_000)


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
