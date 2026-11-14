# Implementation plan: evidence-led review without required code reading

Status: implemented and verified as recorded in [the decision log](DECISIONS.md#2026-11-14-evidence-led-review-implementation-record). This plan did not create evidence, change a PR decision, or fabricate human answers. Remaining limitations are listed in that record.

Related decisions: [DECISIONS.md](DECISIONS.md#2026-11-14-evidence-led-review-without-required-code-reading) and [GLOSSARY.md](../GLOSSARY.md).

## Outcome

For R2283, a reviewer must be able to understand the requirement, observed evidence, material risks, AI limitations and residual unknowns, then accept, request changes or escalate without reading source code. Source and diffs remain optional corroboration. R2234, R2129 and R2297 remain triage-only.

The implementation must not create a trust or hallucination score, infer semantic correctness from mechanical claim statuses, or manufacture human answers and sign-offs.

## Delivery order

### 1. Establish the baseline and shared decision contract

Files:

- Add `engine/decision.py`.
- Add `engine/decision-contract-cases.json`.
- Add `engine/test_decision.py`.
- Add `engine/test_decision.js` for the browser validator when Node.js is available.

Work:

1. Run the existing unit and schema checks before changing them. Separate pre-existing environment failures from regressions.
2. Define the receipt-independent decision input: action, human reason, refusal positions, finding positions and acknowledged unknown IDs.
3. Define stable validation error codes for malformed commands, unknown or duplicate IDs, missing reasons, incomplete acceptance and acceptance-incompatible positions.
4. Implement one pure Python validator used by the authoritative CLI. It must not access GitHub, write receipts or invent defaults.
5. Encode valid and invalid examples as shared JSON cases. Include accept/changes/escalate outcomes and exact expected error codes.

Acceptance rules:

- `accept`: a non-empty human reason; exactly one valid position for every refusal and outside-requirement item; every position compatible with acceptance; every unknown acknowledged exactly once.
- `changes`: a concrete non-empty human reason. Acceptance-only fields are optional; supplied IDs and positions must still be valid.
- `escalate`: a non-empty human explanation of the missing expertise or evidence. Owner assignment is optional and must not be invented.
- Supplied positions never silently choose or rewrite the requested non-acceptance outcome.
- An accept containing a change-required or owner-judgement position is rejected in both interfaces.

### 2. Extend the receipt model without rewriting evidence history

Files:

- `schema/receipt.schema.json`
- `schema/validate.py`
- `docs/RECEIPT_SCHEMA.md`
- `examples/receipt-2283.live.json`
- Fixture-specific test data only where required

Work:

1. Add a structured `decisionBrief` containing short statements with stable IDs, text, provenance and evidence references. Use explicit origins such as harness observation, model interpretation and team explanation.
2. Validate that brief references resolve to existing requirement criteria, checks, claims, refusals, outside-requirement items or unknowns. Do not store duplicated check or claim counts that can drift.
3. Populate the R2283 brief from already recorded material. Do not run another model or add unsupported consumer-impact claims. Preserve `evidence/propose-2283.live.raw.json` unchanged.
4. Add structured positions to every refusal: stable position ID, plain-language label and decision effect (`accept_compatible`, `changes_required` or `escalation_required`). Capture the positions currently hard-coded in the renderer; do not assign them on the human's behalf.
5. Extend decision data with:
   - `escalated` as a status;
   - refusal positions and optional human notes;
   - finding positions (`accept_scope`, `change_required`, `needs_owner`) and optional human notes;
   - `acceptedUnknownRefs` for accepted unknown IDs.
6. Stop using `acceptedResidualRisk` as a duplicate of the whole reason in newly generated decisions. Keep historical artifacts readable; do not rewrite archived evidence merely to make it look new.
7. Investigate the different OOR3 and `docs/REVIEW_FINDINGS.md` descriptions of the `BothStringAndIntKeyAreNull` site. Reconcile them from source evidence or explicitly distinguish the two reference frames; do not silently choose a convenient narrative.
8. Keep the existing mechanical claim statuses and exact `statusReason` values. Document that CLM7 and CLM8 are evidence-linkage examples, not semantic hallucination verdicts.

Verification:

- The live receipt validates and remains pending.
- All new references resolve and all IDs are unique.
- No brief statement is attributed to a human reviewer.
- Old model, example and measurement receipts retain their historical roles.

### 3. Make the GitHub decision path authoritative and consistent

Files:

- `engine/pr.py`
- `engine/test_pr.py`
- `docs/PR_FLOW.md`

Work:

1. Extend comment parsing to `/receipt accept <reason>`, `/receipt changes <reason>` and `/receipt escalate <reason>`.
2. Parse stable lines such as `REF1: position-id`, `OOR1: accept_scope` and `UNK1: acknowledged`. Reject unknown, duplicate and malformed structured lines with actionable errors.
3. Route parsed input through `engine/decision.py`; remove acceptance behaviour based on English prefixes such as `Require `.
4. Persist the validated positions, acknowledgements and human reason. Escalation has no inferred owner.
5. Map receipt outcomes distinctly: accepted → GitHub `success`, changes requested → `failure`, escalated/unreviewed → `pending`. Display escalation as `Escalated—pending owner judgement`, not accepted or defective.
6. Preserve the existing protections: designated human login, non-bot author, same-account policy, exact full head SHA, base/head freshness, evidence digest and final PR re-read.
7. Include the same decision brief, check limitations, claim-status meanings and reasons, unknowns, finding choices and refusal positions in the GitHub receipt comment. Do not require opening the walkthrough or source to discover a caveat.
8. Preserve actual citation revisions when generating source links.
9. Remove the inaccurate hard-coded Claude attribution trailer from new decision commits. Do not rewrite existing public history.

Verification:

- Reuse every shared decision-contract case in the Python tests.
- Test hand-written comments as well as generated-looking comments, especially `accept` combined with a change-required position.
- Test all three status mappings, stale evidence and the existing human-authority controls.
- Mock GitHub in unit tests. Do not post a real decision.

### 4. Rebuild the walkthrough around the no-code decision brief

Files:

- `engine/render.py`
- `engine/test_render.py`
- `walkthrough/index.html` (generated)

Work:

1. Present the main path in this order:
   - decision brief;
   - material risks and unknowns;
   - AI evidence classifications and exact limitations;
   - executed checks and their scope;
   - human decision.
2. Derive test and claim counts from receipt data at render time. Show provenance beside team explanations, model interpretations and harness observations.
3. Replace the over-broad crash headline with wording limited to the tested scenarios. Qualify diagnostic suppression to the observed `MsgPack004` comparison and preserve the minimal-fix approximation caveat.
4. Replace source-oriented `Read this first` guidance with decision-critical concerns. Keep file/line focus only as optional drill-down.
5. Put source excerpts and full diffs in collapsed sections labelled as optional implementation evidence.
6. Isolate source-snapshot handling from the main workspace:
   - matching SHA → optional source can be opened;
   - missing or mismatched SHA → hide that panel and show `Optional implementation evidence unavailable for this receipt`;
   - never render stale excerpts as current and never fail the no-code workspace because optional code is absent.
7. Explain test-backed, contradicted, unsupported and source-only as evidence-linkage classifications, not hallucination counts. Show the exact reason for each current R2283 claim.
8. State that the page is a pinned snapshot rather than live PR state. Final freshness remains a CLI responsibility.
9. Keep detailed claims, receipt mechanics and raw evidence below the decision path, with all existing escaping intact.

Verification:

- Every decision-critical caveat is present in normal HTML text, not only a source block or expanded diff.
- Removing or staling the optional code snapshot leaves the brief, evidence and decision form usable.
- The main path never instructs the reviewer to inspect code.
- Generated HTML matches `render.build`; no outcome, position or acknowledgement is preselected.

### 5. Connect browser drafting to the same rules

Files:

- Add `engine/decision.js` and inline it into the generated static page.
- `engine/render.py`
- `engine/test_render.py`
- `engine/test_decision.js`
- `engine/decision-contract-cases.json`

Work:

1. Render refusal options from receipt data instead of hard-coded R2283 JavaScript options.
2. Render finding positions as `Accept scope`, `Change required` and `Needs owner judgement`; remove transient `Real`/`Not real` ratings and any implication that they create measurements.
3. Add individual unknown acknowledgements for acceptance. Do not require them for changes or escalation.
4. Add the third outcome, `Escalate for code/domain review`, with the appropriate explanation prompt and pending-state wording.
5. Implement the same pure validation rules and error codes in JavaScript. Run both validators against the shared JSON cases without adding a server or runtime dependency to the CLI.
6. Generate comments containing only positions, acknowledgements, outcome and reason entered by the human.
7. Enable copying only when the current draft passes local validation. Keep the CLI's independent validation authoritative and preserve the statement that copying is not signing.
8. Test keyboard/mobile presentation and ensure errors identify the fields requiring attention without erasing the human's input.

Verification:

- Browser and CLI pass the same valid cases and reject the same invalid cases with the same error codes.
- No valid draft can contain unanswered required acceptance items or contradictory acceptance positions.
- Reason-only changes and escalation drafts remain possible.
- No browser path posts, persists locally, approves or merges a decision.

### 6. Regenerate, document and verify the submission

Files:

- `docs/CONCEPT_CARD.md`
- `docs/DEMO_SCRIPT.md`
- `docs/NEXT_SESSION.md`
- `docs/DECISIONS.md`
- `README.md` only if current-status wording changes
- `walkthrough/index.html` (generated)

Work:

1. Update the concept card's principles and trade-offs with evidence-led review, explicit residual-risk acknowledgement and escalation; retain the existing limitations and avoid claiming semantic hallucination detection.
2. Update the recording script to demonstrate the decision brief without opening source, then show optional source only to explain that it is corroboration.
3. Record actual implementation evidence and remaining limitations in the decision log. Do not claim time savings, usability validation or human acceptance without a real measurement or named decision.
4. Regenerate the checked-in walkthrough and verify it against the renderer.
5. Only after verification, use the existing authorized publication/PR operator flows if explicitly requested. Do not fabricate a human comment to exercise `decide` end to end.

Final verification:

```sh
python3 -m unittest engine/test_review.py engine/test_decision.py engine/test_render.py engine/test_pr.py
node --test engine/test_decision.js
python3 schema/validate.py examples/receipt-2283.live.json
python3 engine/render.py
python3 schema/validate.py examples/receipt-2283.live.json
git diff --check
```

If Node.js or Python `jsonschema` is unavailable, record that limitation instead of claiming the corresponding check passed. Install third-party dependencies only in an isolated environment inside the project when implementation requires them. Missing `sample/` citation fixtures and other baseline environment failures must be reported separately, not hidden by deleting tests.

## Definition of done

- A reviewer can reach all three outcomes from the browser and GitHub evidence without reading code.
- Source and diff failure cannot remove the no-code decision path.
- Decision-critical prose has provenance; counts are derived; AI classifications are not presented as semantic truth.
- Acceptance requires all structured positions and unknown acknowledgements; changes and escalation retain their lighter requirements.
- Browser and CLI enforce the same contract, while only the authenticated CLI applies a decision.
- Escalation remains visibly pending and never becomes acceptance or failure.
- R2283 remains pending until a real named human posts a valid decision. The other samples remain triage-only.
- Automated checks pass where their dependencies are available, generated HTML is current, and unavailable checks are disclosed accurately.

## Explicit non-goals for this implementation

- Atomic/per-evidence-link claim semantics or a new model proposal run.
- Deep receipts for the other three demonstration PRs.
- Production event automation, branch protection, automatic approvals or merges.
- A continuously live Pages feed, browser authentication or a backend validation service.
- New .NET test results, human-study metrics or a claimed hallucination-detection rate.
