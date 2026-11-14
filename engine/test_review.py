"""Run: python3 -m unittest engine/test_review.py   (from the repo root)"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import review  # noqa: E402

SAMPLE = str(Path(__file__).parent.parent / "sample")
SHA = "9df83c38409c8bfad0517aebffe48211eda4a5b4"
F = "src/MessagePack.SourceGenerator/CodeAnalysis/TypeCollector.cs"


def claim(kind="behaviour", resolves=True, checks=(), tests=("t",)):
    return {"kind": kind, "citation": {"resolves": resolves}, "checkRefs": list(checks), "testRefs": list(tests)}


def check(cid, status, outcome=None, **kw):
    """A check whose only test, "t", has the given outcome."""
    return {"id": cid, "status": status, "tests": [{"name": "t", "outcome": outcome or status}] if status in ("passed", "failed") else [], **kw}


CHECKS = {
    "P": check("P", "passed"),
    "F": check("F", "failed"),
    "FX": check("FX", "failed", expected="failed"),
    "N": check("N", "not_run"),
    "SUITE": {"id": "SUITE", "status": "passed", "tests": [{"name": "other", "outcome": "passed"}]},
}


class ClaimStatus(unittest.TestCase):
    def status(self, **kw):
        return review.claim_status(claim(**kw), CHECKS)[0]

    def test_unresolved_citation_is_unsupported_even_with_passing_check(self):
        self.assertEqual(self.status(resolves=False, checks=["P"]), "unsupported")

    def test_behaviour_claim_without_check_is_unsupported(self):
        self.assertEqual(self.status(checks=[]), "unsupported")

    def test_a_check_that_did_not_run_cannot_support_a_claim(self):
        self.assertEqual(self.status(checks=["N"]), "unsupported")

    def test_passed_check_verifies(self):
        self.assertEqual(self.status(checks=["P"]), "verified")

    def test_expected_failure_verifies(self):
        self.assertEqual(self.status(checks=["FX"]), "verified")

    def test_unexpected_failure_contradicts(self):
        self.assertEqual(self.status(checks=["F"]), "contradicted")

    def test_one_bad_check_beats_a_good_one(self):
        self.assertEqual(self.status(checks=["P", "F"]), "contradicted")

    def test_suite_pass_without_a_named_test_needs_link_review(self):
        self.assertEqual(self.status(checks=["P"], tests=[]), "needs_link_review")

    def test_naming_a_test_the_check_did_not_run_is_unsupported(self):
        self.assertEqual(self.status(checks=["SUITE"], tests=["t"]), "unsupported")

    def test_invented_test_name_is_unsupported(self):
        self.assertEqual(self.status(checks=["P"], tests=["EverythingWorks"]), "unsupported")

    def test_code_fact_never_becomes_verified(self):
        self.assertEqual(self.status(kind="code_fact", checks=["P"]), "source_only")


class Citations(unittest.TestCase):
    def cite(self, **kw):
        return review.citation_resolves(SAMPLE, {"file": F, "sha": SHA, "startLine": 985, "endLine": 985, **kw})

    def test_real_line_resolves(self):
        self.assertTrue(self.cite())

    def test_line_past_end_does_not(self):
        self.assertFalse(self.cite(startLine=99999, endLine=99999))

    def test_missing_file_does_not(self):
        self.assertFalse(self.cite(file="nope.cs"))

    def test_wrong_revision_does_not(self):
        self.assertFalse(self.cite(sha="0" * 40))

    def test_reversed_range_does_not(self):
        self.assertFalse(self.cite(startLine=990, endLine=985))


class Routing(unittest.TestCase):
    BASE = {
        "requirement": {"quality": "strong"},
        "claims": [], "checks": [], "refusals": [], "outOfRequirement": [],
    }

    def tier(self, **over):
        r = copy.deepcopy(self.BASE)
        r.update(over)
        return review.route(r)["tier"]

    def test_clean_change_is_light(self):
        self.assertEqual(self.tier(), "light")

    def test_scope_creep_needs_standard(self):
        self.assertEqual(self.tier(outOfRequirement=[{"id": "OOR1"}]), "standard")

    def test_open_decision_needs_full_read(self):
        self.assertEqual(self.tier(requirement={"quality": "open_decision"}), "full_read")

    def test_failed_gate_needs_full_read(self):
        self.assertEqual(self.tier(checks=[{"id": "C", "status": "failed"}]), "full_read")

    def test_failed_probe_alone_does_not(self):
        self.assertEqual(self.tier(checks=[{"id": "C", "status": "failed", "role": "probe"}]), "light")

    def test_unlinked_claim_needs_standard(self):
        c = {"id": "CLM1", "status": "needs_link_review", "statusReason": "x",
             "citation": {"file": "f", "startLine": 1, "endLine": 1}}
        self.assertEqual(self.tier(claims=[c]), "standard")

    def test_every_tier_has_a_reason(self):
        r = copy.deepcopy(self.BASE)
        self.assertTrue(review.route(r)["reasons"])


class Assemble(unittest.TestCase):
    BASE = {
        "requirement": {"acceptanceCriteria": [{"id": "AC1"}]},
        "subject": {"headSha": SHA},
        "checks": [{"id": "CHK1", "status": "passed"}, {"id": "CHK2", "status": "not_run"}],
    }

    def build(self, **c):
        import propose
        claim = {"text": "t", "kind": "behaviour", "file": F, "startLine": 1, "endLine": 1, **c}
        return propose.assemble(self.BASE, {"claims": [claim]}, "m")[0]["claims"][0]

    def test_invented_and_not_run_check_refs_are_removed(self):
        self.assertEqual(self.build(checkRefs=["CHK1", "CHK2", "CHK9"])["checkRefs"], ["CHK1"])

    def test_code_fact_gets_no_check_refs(self):
        self.assertEqual(self.build(kind="code_fact", checkRefs=["CHK1"])["checkRefs"], [])

    def test_model_cannot_set_status(self):
        c = self.build(status="verified", checkRefs=["CHK1"])
        self.assertEqual(c["status"], "unsupported")  # placeholder until finalize computes it

    def test_malformed_claim_is_dropped(self):
        import propose
        parts, notes = propose.assemble(self.BASE, {"claims": [{"text": "no citation"}]}, "m")
        self.assertEqual((parts["claims"], len(notes)), ([], 1))


if __name__ == "__main__":
    unittest.main()
