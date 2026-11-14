"""The human decision contract, independent of GitHub and of the browser.

One pure validator is used by the authoritative CLI; engine/decision.js implements
the same rules for early feedback in the walkthrough. Both are exercised by the
same cases in engine/decision-contract-cases.json.

The receipt supplies the contract: the positions each refusal offers and whether
each position permits acceptance, plus the finding and unknown IDs that exist.

Nothing here writes a receipt, invents a position, assigns an owner or signs.
"""
from __future__ import annotations

import re

ACTIONS = ("accept", "changes", "escalate")
FINDING_POSITIONS = ("accept_scope", "change_required", "needs_owner")
EFFECTS = ("accept_compatible", "changes_required", "escalation_required")

# Only the exact templates the project renders count as placeholders. A broad
# bracket check would reject legitimate bracketed domain text in a real reason.
PLACEHOLDERS = (
    "[your answer]",
    "[your reason]",
    "[reason]",
    "[choose a position]",
    "[choose your position]",
    "[your reason and residual risk]",
    "[reason, including residual risk]",
    "[refusal position]",
    "[finding position]",
    "[acknowledge]",
)
BRACKET_ONLY = re.compile(r"^\s*\[[^\]]*\]\s*$")


def contract_from_receipt(receipt):
    """The decision-relevant shape of a receipt. No evidence is reinterpreted."""
    return {
        "refusals": [
            {
                "id": refusal["id"],
                "positions": [
                    {"id": p["id"], "label": p["label"], "effect": p["effect"]}
                    for p in refusal.get("positions", [])
                ],
            }
            for refusal in receipt.get("refusals", [])
        ],
        "findings": [item["id"] for item in receipt.get("outOfRequirement", [])],
        "unknowns": [unknown["id"] for unknown in receipt.get("unknowns", [])],
    }


def _error(code, message):
    return {"code": code, "message": message}


def is_placeholder(text):
    lowered = text.strip().casefold()
    return bool(BRACKET_ONLY.match(text)) or any(p in lowered for p in PLACEHOLDERS)


def _position_entries(values):
    """Yield (id, position) pairs from a list of {id, position} mappings.

    Position ids are stored under refusalId/findingId in the receipt, but the
    shared contract and both validators use the simpler id/position shape.
    """
    for value in values or []:
        if not isinstance(value, dict):
            yield None, None
            continue
        key = value.get("refusalId", value.get("findingId", value.get("id")))
        position = value.get("positionId", value.get("position"))
        yield key, position


def validate_decision(action, reason, refusal_positions, finding_positions,
                      acknowledged_unknowns, contract):
    """Return a list of {code, message} errors. An empty list means valid."""
    errors = []
    if action not in ACTIONS:
        return [_error("outcome_invalid",
                       "Outcome must be accept, changes or escalate.")]

    reason = reason if isinstance(reason, str) else ""
    if not reason.strip():
        errors.append(_error("reason_missing", "A non-empty human reason is required."))
    elif is_placeholder(reason):
        errors.append(_error("reason_placeholder",
                             "Replace the template placeholder in the reason with your own words."))

    refusals = {item["id"]: item for item in contract.get("refusals", [])}
    findings = set(contract.get("findings", []))
    unknowns = set(contract.get("unknowns", []))
    seen_refusals, seen_findings, seen_unknowns = set(), set(), set()

    for refusal_id, position_id in _position_entries(refusal_positions):
        if refusal_id not in refusals:
            errors.append(_error("refusal_unknown",
                                 f"{refusal_id or '?'}: not a refusal in this receipt."))
            continue
        if refusal_id in seen_refusals:
            errors.append(_error("refusal_duplicate",
                                 f"{refusal_id}: a position was given more than once."))
            continue
        seen_refusals.add(refusal_id)
        options = {p["id"]: p for p in refusals[refusal_id]["positions"]}
        option = options.get(position_id)
        if option is None:
            allowed = ", ".join(options) or "none recorded"
            errors.append(_error("refusal_position_unknown",
                                 f"{refusal_id}: '{position_id}' is not a recorded position. "
                                 f"Choose one of: {allowed}."))
            continue
        if action == "accept" and option["effect"] != "accept_compatible":
            errors.append(_error("refusal_position_incompatible",
                                 f"{refusal_id}: '{position_id}' does not permit acceptance; "
                                 f"it requires {option['effect'].replace('_', ' ')}."))

    for finding_id, position_id in _position_entries(finding_positions):
        if finding_id not in findings:
            errors.append(_error("finding_unknown",
                                 f"{finding_id or '?'}: not an outside-requirement item in this receipt."))
            continue
        if finding_id in seen_findings:
            errors.append(_error("finding_duplicate",
                                 f"{finding_id}: a position was given more than once."))
            continue
        seen_findings.add(finding_id)
        if position_id not in FINDING_POSITIONS:
            errors.append(_error("finding_position_unknown",
                                 f"{finding_id}: '{position_id}' is not a recorded finding position. "
                                 f"Choose one of: {', '.join(FINDING_POSITIONS)}."))
            continue
        if action == "accept" and position_id != "accept_scope":
            errors.append(_error("finding_position_incompatible",
                                 f"{finding_id}: '{position_id}' does not permit acceptance; "
                                 "choose accept_scope."))

    for unknown_id in acknowledged_unknowns or []:
        if unknown_id not in unknowns:
            errors.append(_error("unknown_unknown",
                                 f"{unknown_id or '?'}: not an unknown in this receipt."))
            continue
        if unknown_id in seen_unknowns:
            errors.append(_error("unknown_duplicate",
                                 f"{unknown_id}: acknowledged more than once."))
            continue
        seen_unknowns.add(unknown_id)

    if action == "accept":
        for refusal_id in refusals:
            if refusal_id not in seen_refusals:
                errors.append(_error("refusal_position_missing",
                                     f"{refusal_id}: a position is required to accept."))
        for finding_id in contract.get("findings", []):
            if finding_id not in seen_findings:
                errors.append(_error("finding_position_missing",
                                     f"{finding_id}: a position is required to accept."))
        for unknown_id in contract.get("unknowns", []):
            if unknown_id not in seen_unknowns:
                errors.append(_error("unknown_missing",
                                     f"{unknown_id}: acknowledge this residual unknown to accept."))
    return errors


def format_errors(errors):
    return " ".join(error["message"] for error in errors)
