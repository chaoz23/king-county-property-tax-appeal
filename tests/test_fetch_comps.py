import csv
import importlib.util
import pathlib
import tempfile
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "scripts" / "fetch_comps.py"
SPEC = importlib.util.spec_from_file_location("fetch_comps", MODULE_PATH)
fetch_comps = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch_comps)


class ResidentialBuildingTests(unittest.TestCase):
    def test_optional_integer_parser_distinguishes_missing_from_zero(self):
        self.assertIsNone(fetch_comps.parse_optional_int({}, "Bedrooms"))
        self.assertIsNone(fetch_comps.parse_optional_int({"Bedrooms": ""}, "Bedrooms"))
        self.assertEqual(fetch_comps.parse_optional_int({"Bedrooms": "0"}, "Bedrooms"), 0)

    def test_optional_integer_parser_can_use_alternate_header(self):
        row = {"Bedrooms": "invalid", "BEDROOMS": "3"}
        self.assertEqual(
            fetch_comps.parse_optional_int(row, "Bedrooms", "BEDROOMS"), 3
        )

    def test_loader_preserves_missing_optional_characteristics(self):
        fieldnames = [
            "Major",
            "Minor",
            "SqFtTotLiving",
            "YrBuilt",
            "BldgGrade",
            "Bedrooms",
            "BathFullCount",
            "Bath3qtrCount",
            "BathHalfCount",
        ]
        row = {
            "Major": "123456",
            "Minor": "789",
            "SqFtTotLiving": "1000",
            "YrBuilt": "1980",
            "BldgGrade": "7",
            "Bedrooms": "",
            "BathFullCount": "",
            "Bath3qtrCount": "",
            "BathHalfCount": "",
        }

        with tempfile.TemporaryDirectory(dir=pathlib.Path(__file__).parent) as directory:
            path = pathlib.Path(directory) / "EXTR_ResBldg.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerow(row)

            building = fetch_comps.load_resbldg(directory)["1234560789"]

        self.assertIsNone(building["bedrooms"])
        self.assertIsNone(building["bathrooms"])


if __name__ == "__main__":
    unittest.main()
