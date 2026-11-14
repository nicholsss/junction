"""Tests for the walkthrough page generator. Run: python3 -m unittest engine/test_render.py

The page must let a reviewer reach a decision without reading source. These tests
check the no-code path, derived counts, optional-source isolation, and the shared
decision contract embedded in the generated page.
"""
import json
import re
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import decision  # noqa: E402
import render  # noqa: E402

RECEIPT = json.loads(render.RECEIPT.read_text())
MODEL = json.loads(render.MODEL_RUN.read_text())
TRIAGE = json.loads(render.TRIAGE.read_text())
PAGE = render.build(RECEIPT, MODEL, TRIAGE)
CONTRACT = decision.contract_from_receipt(RECEIPT)


class NoCodePathTests(unittest.TestCase):
    def test_main_path_starts_with_summary_and_outcome_before_supporting_evidence(self):
        order = ['id="overview"', 'id="decision"', 'id="refused"', 'id="found"', 'id="unknowns"',
                 'id="evidence"', 'id="brief"', 'id="classifications"', 'id="checks"', 'id="source"']
        positions = [PAGE.index(x) for x in order]
        self.assertEqual(positions, sorted(positions), order)

    def test_main_path_does_not_instruct_source_reading(self):
        self.assertNotIn("Read this first", PAGE)
        self.assertIn("Source is optional", PAGE)
        self.assertIn("Optional implementation evidence", PAGE)
        self.assertIn("Optional source focus", PAGE)
        self.assertIn("not a required reading list", PAGE)

    def test_every_brief_statement_has_provenance_and_its_references(self):
        provenance = {"harness": "Harness observation", "model": "AI interpretation",
                      "team": "Team explanation"}
        for statement in RECEIPT["decisionBrief"]:
            self.assertIn(render.e(statement["text"]), PAGE, statement["id"])
            self.assertIn(provenance[statement["provenance"]], PAGE, statement["id"])
            for ref in statement["evidenceRefs"]:
                self.assertIn(ref, PAGE, statement["id"])
        self.assertNotIn("human reviewer", PAGE.lower())

    def test_counts_are_derived_from_receipt_data(self):
        verified = sum(1 for c in RECEIPT["claims"] if c["status"] == "verified")
        head = next(c for c in RECEIPT["checks"] if c.get("revision") == "head" and c.get("tests"))
        fail = next(c for c in RECEIPT["checks"] if c.get("expected") == "failed" and c.get("role") != "probe")
        self.assertIn(f"<b>{verified} of {len(RECEIPT['claims'])}</b> AI claims are test-backed", PAGE)
        self.assertIn(f"<b>{head['counts']['passed']} passed of {head['counts']['total']}</b>", PAGE)
        self.assertIn(f"<b>{fail['counts']['failed']} failed of {fail['counts']['total']}</b>", PAGE)

    def test_classifications_are_explained_as_evidence_links_not_hallucinations(self):
        self.assertIn("not a trust score or a hallucination count", PAGE)
        self.assertIn("unproven, not proven false", PAGE)
        self.assertIn("runtime behaviour is not established", PAGE)
        for claim in RECEIPT["claims"]:
            self.assertIn(render.e(claim["statusReason"]), PAGE, claim["id"])

    def test_current_claim_and_check_evidence_is_listed(self):
        for c in RECEIPT["claims"]:
            self.assertIn(f'id="claim-{c["id"]}"', PAGE)
            block = re.search(rf'<details class="claim" id="claim-{c["id"]}".*?</summary>', PAGE, re.S).group(0)
            self.assertIn(f"s-{c['status']}", block, c["id"])
        for c in RECEIPT["checks"]:
            self.assertIn(f'id="check-{c["id"]}"', PAGE)
            shown = c["limitations"].replace("upstream PR #2305", "the reference patch")
            self.assertIn(render.e(shown), PAGE, c["id"])

    def test_tier_refusals_and_unknowns_are_shown(self):
        self.assertIn(render.TIER[RECEIPT["routing"]["tier"]], PAGE)
        for x in RECEIPT["refusals"]:
            self.assertIn(render.e(x["question"]), PAGE)
        for x in RECEIPT["unknowns"]:
            self.assertIn(render.e(x["text"]), PAGE)

    def test_decision_stays_pending_in_markup(self):
        self.assertEqual(RECEIPT["decision"]["status"], "pending")
        self.assertIn("Decision: pending", PAGE)
        self.assertIn("No decision selected.", PAGE)

    def test_not_run_check_stays_visible(self):
        self.assertIn("Not run", PAGE)

    def test_binds_to_head_sha(self):
        self.assertIn(RECEIPT["subject"]["headSha"], PAGE)
        self.assertIn(RECEIPT["subject"]["headSha"][:8], PAGE)


class OptionalSourceTests(unittest.TestCase):
    def test_matching_snapshot_is_rendered_only_as_optional_drill_down(self):
        self.assertIn("Exact head source excerpt", PAGE)
        self.assertIn('id="source"', PAGE)
        self.assertIn("Source and diffs are corroboration, not a required step", PAGE)

    def test_stale_snapshot_hides_only_the_source_panel(self):
        stale = deepcopy(RECEIPT)
        stale["subject"]["headSha"] = "a" * 40
        page = render.build(stale, MODEL, TRIAGE)
        self.assertIn("Optional implementation evidence unavailable for this receipt", page)
        self.assertNotIn("Exact head source excerpt", page)
        self.assertIn('id="brief"', page)
        self.assertIn('id="decision"', page)
        self.assertIn("Source is optional", page)

    def test_missing_snapshot_does_not_fail_the_workspace(self):
        with patch.object(render, "load_snapshot", return_value=None):
            page = render.build(RECEIPT, MODEL, TRIAGE)
        self.assertIn("Optional implementation evidence unavailable for this receipt", page)
        self.assertIn('id="brief"', page)
        self.assertIn('id="decision"', page)


class SharedContractTests(unittest.TestCase):
    def test_page_embeds_the_receipt_contract_and_the_shared_validator(self):
        data = json.loads(re.search(r'<script id="rr-data" type="application/json">(.*?)</script>',
                                    PAGE, re.S).group(1))
        self.assertEqual(data["contract"], CONTRACT)
        self.assertEqual(data["unknowns"], CONTRACT["unknowns"])
        self.assertIn("DecisionContract", PAGE)
        self.assertIn("validateDecision", PAGE)

    def test_positions_and_findings_come_from_receipt_data(self):
        for refusal in CONTRACT["refusals"]:
            for position in refusal["positions"]:
                self.assertIn(f'value="{position["id"]}"', PAGE, position["id"])
        self.assertIn('value="accept_scope"', PAGE)
        self.assertIn('value="change_required"', PAGE)
        self.assertIn('value="needs_owner"', PAGE)
        for refusal in RECEIPT["refusals"]:
            self.assertIn(f'data-note-for="{refusal["id"]}"', PAGE)
        for finding in RECEIPT["outOfRequirement"]:
            self.assertIn(f'data-note-for="{finding["id"]}"', PAGE)
        self.assertNotIn("> Real<", PAGE)
        self.assertNotIn("Not real", PAGE)
        self.assertNotIn("AI findings rated", PAGE)

    def test_three_outcomes_and_no_preselection(self):
        for value in ("accept", "changes", "escalate"):
            self.assertIn(f'name="outcome" value="{value}"', PAGE)
        self.assertNotRegex(PAGE, r'name="outcome"[^>]*checked')
        self.assertNotRegex(PAGE, r'<option[^>]*\sselected')
        self.assertNotRegex(PAGE, r'type="checkbox"[^>]*checked')
        self.assertIn('id="copy-comment" disabled', PAGE)
        self.assertIn("Copy decision draft", PAGE)

    def test_comment_template_does_not_pre_acknowledge_unknowns(self):
        for unknown in RECEIPT["unknowns"]:
            self.assertIn(f'{unknown["id"]}: [acknowledged]', PAGE)
            self.assertNotIn(f'{unknown["id"]}: acknowledged', PAGE)
        self.assertIn('UNK1: [acknowledged]', render.decision_template(RECEIPT))

    def test_browser_never_signs_or_persists(self):
        self.assertNotIn("localStorage", PAGE)
        self.assertNotIn("Record decision", PAGE)
        self.assertNotIn("Download decision JSON", PAGE)

    def test_code_is_escaped(self):
        from html import unescape
        source = render.code_html('List<Diagnostic> value; // <script>alert(1)</script>')
        self.assertNotIn('<script>', source)
        self.assertIn('List<Diagnostic>', unescape(re.sub(r'<[^>]+>', '', source)))
        self.assertIn('&lt;', source)

    def test_each_field_can_show_its_own_error(self):
        for refusal in RECEIPT["refusals"]:
            self.assertIn(f'aria-describedby="err-{refusal["id"]}"', PAGE)
            self.assertIn(f'id="err-{refusal["id"]}"', PAGE)
        for finding in RECEIPT["outOfRequirement"]:
            self.assertIn(f'aria-describedby="err-{finding["id"]}"', PAGE)
            self.assertIn(f'id="err-{finding["id"]}"', PAGE)
        for unknown in RECEIPT["unknowns"]:
            self.assertIn(f'aria-describedby="err-{unknown["id"]}"', PAGE)
            self.assertIn(f'id="err-{unknown["id"]}"', PAGE)
        self.assertIn('aria-describedby="err-reason"', PAGE)
        self.assertIn('id="err-reason"', PAGE)
        self.assertIn('aria-describedby="err-outcome"', PAGE)
        self.assertIn('id="err-outcome"', PAGE)
        self.assertIn('id="first-error"', PAGE)

    def test_validation_marks_fields_and_preserves_input(self):
        self.assertIn("setAttribute('aria-invalid','true')", PAGE)
        self.assertIn("removeAttribute('aria-invalid')", PAGE)
        self.assertIn("focus({preventScroll:true})", PAGE)
        self.assertIn("fields need attention", PAGE)
        update_js = PAGE[PAGE.index("function update(){"):
                         PAGE.index("$('#decision').addEventListener('submit'")]
        self.assertNotIn(".value=", update_js, "validation must not clear the human's input")

    def test_mobile_layout_stacks_the_decision_controls(self):
        self.assertIn(".drow{flex-direction:column;align-items:stretch", PAGE)
        self.assertIn(".unknowns label{padding:8px 0}", PAGE)

    def test_escalation_is_shown_as_pending_owner_judgement(self):
        escalated = deepcopy(RECEIPT)
        escalated["decision"] = {
            "status": "escalated",
            "owner": "Actual Human (@teammate)",
            "reason": "A source-generator owner must judge the suppression policy.",
            "signedAt": "2026-11-14T10:00:00Z",
            "boundToHeadSha": RECEIPT["subject"]["headSha"],
        }
        page = render.build(escalated, MODEL, TRIAGE)
        self.assertIn("Decision: escalated, pending owner judgement", page)
        self.assertIn("Status: pending owner judgement", page)
        self.assertIn("stays pending owner judgement", page)


class SubmissionTests(unittest.TestCase):
    def test_measurement_numbers_match_the_model_receipt(self):
        inj = [c for c in MODEL["claims"] if str(c.get("modelNote", "")).startswith("INJECTED")]
        self.assertEqual(len(inj), 5)
        self.assertTrue(all(c["status"] != "verified" for c in inj))
        real_ver = sum(1 for c in MODEL["claims"] if c not in inj and c["status"] == "verified")
        self.assertIn(f"<b>{real_ver} of {len(MODEL['claims']) - len(inj)}</b> real claims were verified", PAGE)

    def test_submission_uses_local_requirements(self):
        self.assertIn("HackJunction 2026", PAGE)
        self.assertIn(render.REQUIREMENTS_URL + "#r2283", PAGE)
        self.assertNotIn("github.com/MessagePack-CSharp/", PAGE)
        self.assertNotIn("github.com/te-industry-tech-office/", PAGE)
        for rid in ("#2283", "#2234", "#2129", "#2297"):
            self.assertNotIn(rid, PAGE)

    def test_all_triage_rows_present(self):
        for t in TRIAGE:
            self.assertIn(render.local_requirement_id(t["id"]), PAGE)

    def test_checked_in_page_matches_the_renderer(self):
        if not render.OUT.exists():
            self.skipTest("walkthrough page not generated")

        def normalized(text):
            return "\n".join(line.rstrip() for line in text.splitlines()) + "\n"

        self.assertEqual(normalized(render.OUT.read_text()), normalized(PAGE),
                         "regenerate walkthrough/index.html")


if __name__ == "__main__":
    unittest.main()
