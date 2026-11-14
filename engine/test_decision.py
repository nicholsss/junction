"""Shared decision-contract tests. Run: python3 -m unittest engine/test_decision.py

The same JSON cases are executed by engine/test_decision.js. Neither test posts,
persists or invents a human decision.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import decision  # noqa: E402

CASES = json.loads((Path(__file__).parent / "decision-contract-cases.json").read_text())


def codes(errors):
    return sorted(error["code"] for error in errors)


class SharedCases(unittest.TestCase):
    def test_every_case_matches_the_shared_expectation(self):
        for case in CASES["cases"]:
            with self.subTest(case=case["name"]):
                data = case["input"]
                errors = decision.validate_decision(
                    data["action"], data["reason"], data.get("refusalPositions"),
                    data.get("findingPositions"), data.get("acknowledgedUnknowns"),
                    CASES["contract"])
                self.assertEqual(codes(errors), sorted(case["errors"]), case["name"])
                self.assertEqual(not errors, case["valid"], case["name"])

    def test_every_error_has_a_message(self):
        for case in CASES["cases"]:
            data = case["input"]
            for error in decision.validate_decision(
                    data["action"], data["reason"], data.get("refusalPositions"),
                    data.get("findingPositions"), data.get("acknowledgedUnknowns"),
                    CASES["contract"]):
                self.assertTrue(error["message"].strip(), case["name"])


class ReceiptContract(unittest.TestCase):
    def test_live_receipt_contract_has_positions_for_every_refusal(self):
        receipt = json.loads((Path(__file__).parent.parent / "examples/receipt-2283.live.json").read_text())
        contract = decision.contract_from_receipt(receipt)
        self.assertEqual([r["id"] for r in contract["refusals"]],
                         [r["id"] for r in receipt["refusals"]])
        for refusal in contract["refusals"]:
            self.assertTrue(refusal["positions"], refusal["id"])
            effects = {p["effect"] for p in refusal["positions"]}
            self.assertIn("accept_compatible", effects, refusal["id"])
            self.assertTrue(effects <= set(decision.EFFECTS), refusal["id"])
        self.assertEqual(contract["findings"], [x["id"] for x in receipt["outOfRequirement"]])
        self.assertEqual(contract["unknowns"], [x["id"] for x in receipt["unknowns"]])

    def test_accept_against_live_receipt_requires_known_ids(self):
        receipt = json.loads((Path(__file__).parent.parent / "examples/receipt-2283.live.json").read_text())
        contract = decision.contract_from_receipt(receipt)
        errors = decision.validate_decision("accept", "I accept the recorded risks.", [], [], [], contract)
        self.assertIn("refusal_position_missing", codes(errors))
        self.assertIn("finding_position_missing", codes(errors))
        self.assertIn("unknown_missing", codes(errors))

    def test_format_errors_is_stable_and_readable(self):
        errors = [{"code": "reason_missing", "message": "A reason is required."},
                  {"code": "unknown_missing", "message": "UNK1: acknowledge."}]
        self.assertEqual(decision.format_errors(errors), "A reason is required. UNK1: acknowledge.")


if __name__ == "__main__":
    unittest.main()
