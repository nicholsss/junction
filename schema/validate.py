#!/usr/bin/env python3
"""Validate a receipt against the JSON Schema, then check the invariants a schema cannot express.

Usage: python3 schema/validate.py examples/receipt-2283.example.json
Needs: pip install jsonschema
"""
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "engine"))
import decision  # noqa: E402


def _duplicates(values):
    seen, dupes = set(), set()
    for value in values:
        (dupes if value in seen else seen).add(value)
    return sorted(dupes)


def invariant_errors(r):
    errs = []
    checks = {c["id"]: c for c in r["checks"]}
    acs = {a["id"] for a in r["requirement"]["acceptanceCriteria"]}
    claims = {c["id"]: c for c in r["claims"]}
    refusals = {x["id"]: x for x in r["refusals"]}
    findings = {x["id"]: x for x in r["outOfRequirement"]}
    unknowns = {x["id"]: x for x in r["unknowns"]}

    for label, ids in (
        ("acceptance criterion", [a["id"] for a in r["requirement"]["acceptanceCriteria"]]),
        ("check", [c["id"] for c in r["checks"]]),
        ("claim", [c["id"] for c in r["claims"]]),
        ("refusal", [x["id"] for x in r["refusals"]]),
        ("outside-requirement item", [x["id"] for x in r["outOfRequirement"]]),
        ("unknown", [x["id"] for x in r["unknowns"]]),
        ("decision-brief statement", [x["id"] for x in r.get("decisionBrief", [])]),
    ):
        for duplicate in _duplicates(ids):
            errs.append(f"{label} id is duplicated: {duplicate}")

    known_refs = set(acs) | set(checks) | set(claims) | set(refusals) | set(findings) | set(unknowns)
    for statement in r.get("decisionBrief", []):
        if not statement["text"].strip():
            errs.append(f"{statement['id']}: decision-brief text is empty")
        for ref in statement["evidenceRefs"]:
            if ref not in known_refs:
                errs.append(f"{statement['id']}: unknown evidence reference {ref}")

    for c in r["checks"]:
        if c["status"] != "not_run" and not c.get("outputRef"):
            errs.append(f"{c['id']}: executed check has no outputRef")
        if c["status"] == "not_run" and (c.get("counts") or c.get("outputRef")):
            errs.append(f"{c['id']}: not_run check must not carry results")

    for c in r["claims"]:
        cid = c["id"]
        for a in c["requirementRefs"]:
            if a not in acs:
                errs.append(f"{cid}: unknown acceptance criterion {a}")
        for k in c["checkRefs"]:
            if k not in checks:
                errs.append(f"{cid}: unknown check {k}")
            elif checks[k]["status"] == "not_run":
                errs.append(f"{cid}: cites {k}, which was not run")
        for t in c["testRefs"]:
            if c["status"] != "unsupported" and not any(x["name"] == t for k in c["checkRefs"] for x in checks.get(k, {}).get("tests", [])):
                errs.append(f"{cid}: names test {t}, which no cited check ran")
        if c["citation"]["startLine"] > c["citation"]["endLine"]:
            errs.append(f"{cid}: citation range is reversed")
        if c["status"] == "verified":
            if not c["checkRefs"]:
                errs.append(f"{cid}: verified without any check")
            if c["kind"] == "behaviour" and not c["testRefs"]:
                errs.append(f"{cid}: behaviour claim verified without a named test")
            if not c["citation"]["resolves"]:
                errs.append(f"{cid}: verified with a citation that does not resolve")
        if c["status"] == "source_only" and any(
            checks.get(k, {}).get("status") == "passed" for k in c["checkRefs"]
        ):
            errs.append(f"{cid}: source_only but cites a passed check")
        if not c["citation"]["resolves"] and c["status"] != "unsupported":
            errs.append(f"{cid}: citation does not resolve, so status must be unsupported")

    for x in r["refusals"]:
        for k in x.get("relatedClaims", []):
            if k not in claims:
                errs.append(f"{x['id']}: unknown claim {k}")
        for k in x.get("relatedChecks", []):
            if k not in checks:
                errs.append(f"{x['id']}: unknown check {k}")
        positions = x.get("positions", [])
        for duplicate in _duplicates([p["id"] for p in positions]):
            errs.append(f"{x['id']}: duplicate position {duplicate}")
        if positions and not any(p["effect"] == "accept_compatible" for p in positions):
            errs.append(f"{x['id']}: no position is compatible with acceptance")

    d = r["decision"]
    for position in d.get("refusalPositions", []):
        refusal = refusals.get(position["refusalId"])
        if refusal is None:
            errs.append(f"decision: unknown refusal {position['refusalId']}")
        elif position["positionId"] not in {p["id"] for p in refusal.get("positions", [])}:
            errs.append(f"decision: {position['refusalId']} has no recorded position {position['positionId']}")
    for duplicate in _duplicates([p["refusalId"] for p in d.get("refusalPositions", [])]):
        errs.append(f"decision: duplicate refusal position {duplicate}")
    for position in d.get("findingPositions", []):
        if position["findingId"] not in findings:
            errs.append(f"decision: unknown outside-requirement item {position['findingId']}")
    for duplicate in _duplicates([p["findingId"] for p in d.get("findingPositions", [])]):
        errs.append(f"decision: duplicate finding position {duplicate}")
    for ref in d.get("acceptedUnknownRefs", []):
        if ref not in unknowns:
            errs.append(f"decision: unknown residual unknown {ref}")
    for duplicate in _duplicates(d.get("acceptedUnknownRefs", [])):
        errs.append(f"decision: duplicate acknowledged unknown {duplicate}")

    if d["status"] != "pending":
        if d.get("boundToHeadSha") != r["subject"]["headSha"]:
            errs.append("decision: signed revision differs from the head commit; receipt is stale")
        contract = decision.contract_from_receipt(r)
        action = {"accepted": "accept", "changes_requested": "changes", "escalated": "escalate"}[d["status"]]
        for error in decision.validate_decision(
                action, d.get("reason", ""),
                [{"refusalId": p["refusalId"], "positionId": p["positionId"]} for p in d.get("refusalPositions", [])],
                [{"findingId": p["findingId"], "positionId": p["positionId"]} for p in d.get("findingPositions", [])],
                d.get("acceptedUnknownRefs", []), contract):
            errs.append("decision: " + error["message"])
    return errs


def main(path):
    receipt = json.loads(Path(path).read_text())
    schema = json.loads((HERE / "receipt.schema.json").read_text())
    errs = [f"schema: {'/'.join(map(str, e.absolute_path))}: {e.message}"
            for e in Draft202012Validator(schema).iter_errors(receipt)]
    if not errs:
        errs = invariant_errors(receipt)
    for e in errs:
        print("FAIL", e)
    print("OK" if not errs else f"{len(errs)} problem(s)")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
