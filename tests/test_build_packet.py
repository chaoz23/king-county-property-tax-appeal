import importlib.util
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "scripts" / "build_packet.py"
SPEC = importlib.util.spec_from_file_location("build_packet", MODULE_PATH)
build_packet = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_packet)


def subject(notice_mailing_date=None):
    return {
        "assessed": {"assessment_year": 2026},
        "owner_inputs": {"notice_mailing_date": notice_mailing_date},
    }


class DeadlineTests(unittest.TestCase):
    def test_notice_date_after_july_controls_filing_deadline(self):
        result = build_packet.build_deadline(subject("2026-08-15"))

        self.assertIn("60-day deadline:** October 14, 2026", result)
        self.assertIn("Filing deadline (later of the two):** October 14, 2026", result)

    def test_july_first_controls_when_notice_window_ends_earlier(self):
        result = build_packet.build_deadline(subject("2026-05-01"))

        self.assertIn("60-day deadline:** June 30, 2026", result)
        self.assertIn("Filing deadline (later of the two):** July 01, 2026", result)

    def test_missing_notice_date_does_not_invent_filing_deadline(self):
        result = build_packet.build_deadline(subject())

        self.assertIn("Filing deadline: unresolved", result)
        self.assertIn("Do not rely on July 1 alone", result)
        self.assertNotIn("Filing deadline (later of the two)", result)

    def test_evidence_deadline_requires_actual_hearing_date(self):
        result = build_packet.build_deadline(subject("2026-08-15"))

        self.assertIn("unresolved until the BOE assigns the hearing date", result)
        self.assertIn("21 business days before the actual hearing date", result)
        self.assertNotIn("estimated hearing", result)
        self.assertNotIn("Evidence exchange deadline (est.)", result)


if __name__ == "__main__":
    unittest.main()
