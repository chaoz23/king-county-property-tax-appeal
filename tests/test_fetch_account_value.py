import importlib.util
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "scripts" / "fetch_account_value.py"
SPEC = importlib.util.spec_from_file_location("fetch_account_value", MODULE_PATH)
fetch_account_value = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch_account_value)


class BuildingDetailsTests(unittest.TestCase):
    def test_missing_boolean_fields_remain_unknown(self):
        html = """
        <table id="cphContent_DetailsViewPropTypeR">
          <tr><td>Total Square Footage</td><td>1,000</td></tr>
          <tr><td>Grade</td><td>7 Average</td></tr>
        </table>
        """

        result = fetch_account_value.parse_building_details(html)

        self.assertNotIn("views", result)
        self.assertNotIn("waterfront", result)


if __name__ == "__main__":
    unittest.main()
