# Current handoff: our HackJunction submission

Review Receipt is our HackJunction 2026 submission for Tieto's Earned Trust in AI Code challenge. This handoff replaces the previous fork-and-PR setup plan.

## Presentation and scope agreed with the user

- Present Review Receipt as our work: engine, schema/validator, model integration, PR receipts and decisions, and walkthrough.
- The supplied MessagePack code and prepared AI changes are demo material, with brief attribution in README.md. Preserve licenses, original authorship and historical evidence.
- Use local demo IDs R2283, R2234, R2129 and R2297. Do not tag/link upstream issues in demo PR titles, descriptions, comments or the walkthrough, and do not request action from upstream maintainers. Link docs/DEMO_REQUIREMENTS.md for requirement snapshots.
- Keep our existing repository, PRs, receipt comments and statuses. Keep the technical fork relationship: detaching can discard PR/comment metadata. Do not detach, delete, recreate or rewrite sample history for appearance.
- Raw receipts retain historical identifiers/source URLs for provenance. Format local labels at presentation boundaries; do not rewrite recorded checks or measurement evidence.
- Automatic Codex reviews are disabled for the demo repository. Do not re-enable them or make changes to the user's other repositories.

## Current environment

- Source: github.com/nicholsss/junction, local engine/ and walkthrough/.
- Demo PR repository: nicholsss/junction26-messagepack-csharp. R2283 → PR 1, R2234 → PR 2, R2129 → PR 3, R2297 → PR 4. Registry: docs/pull-requests.json.
- Live site: https://nicholsss.github.io/junction/ from gh-pages. Render with python3 engine/render.py; publish with python3 engine/publish_pages.py.
- R2283 live receipt: examples/receipt-2283.live.json, model-generated without injected claims, recorded per-test evidence attached, an 11-statement decision brief, two refusals with structured positions, two outside-requirement items, two unknowns, pending human decision. A third proposed outside-requirement item was withdrawn after source review; the raw model output is preserved. Other PRs are triage only.
- Historical measurement receipt: examples/receipt-2283.model.json, with five deliberately injected claims; use only for the labelled measurement experiment.
- CLI: python3 engine/pr.py post 1 (upserts the same receipt comment and sets pending). Actual human decisions are applied with decide 1 --human LOGIN --name 'Real name', then pushed and republished. Accept, changes and escalate use structured positions; see docs/PR_FLOW.md.
- The user authorized this demo's branch pushes, PRs, receipt comments/statuses and Pages. Do not repeat authorization requests for the same scope. Ask only for genuinely new consequential actions.
- Deadline supplied as today, 2026-11-14 Helsinki; no exact cutoff or signer assigned.

## Non-negotiable evidence rules

Never fabricate metrics, test runs, sign-offs or human answers. Never record a decision on anyone's behalf. No trust score. Keep R2283 pending until a real named human posts their decision. A different PR head invalidates old evidence; production pull_request automation and required-status branch protection are not built. The page is a published snapshot, not a live GitHub feed.

The .env model key is git-ignored: never print or publish it. Do not publish emails, home-directory paths or raw machine-specific logs in PR comments. evidence/pr2305.diff remains deliberately untracked; do not commit it without asking. Use accurate commit attribution; do not append the inherited Claude trailer to Codex work. Existing public history has not been rewritten.

## Verification

Run `python3 -m unittest engine/test_review.py engine/test_decision.py engine/test_render.py engine/test_pr.py`, `node --test engine/test_decision.js`, and `python3 schema/validate.py examples/receipt-2283.live.json`. The last observed result was 105 passed, 1 failure and 0 errors: the single failure is `test_real_line_resolves`, which needs the deliberately ignored `sample/` checkout. `jsonschema` is installed in the project-local `.venv`, which is git-ignored. Verify published content matches the render; use HTTP for browser checks. Existing .NET runs are recorded evidence, not fresh runs in this session.

Next work: the approved evidence-led, no-code-read design in [docs/IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) has been implemented and verified as above. A real human decision can be recorded only if/when supplied; arrange and record the genuine human portion using docs/DEMO_SCRIPT.md. Do not perform the human portion yourself. Re-run the citation test only when a real `sample/` checkout is available.

## Evidence-led reference UX

The default view is now Review R2283: decision brief first, then material risks and unknowns, evidence classifications with exact reasons, executed checks with limits, and the human decision. Each brief statement carries provenance (`harness`, `model`, `team`) and evidence references; counts are derived from receipt data. The brief is not a second AI summary and no statement is attributed to a human reviewer.

Source excerpts and diffs moved into a collapsed **Optional implementation evidence** panel. The renderer compares the snapshot's base and head with the receipt; a mismatch or missing file hides only that panel and shows a warning. The no-code path still renders. `walkthrough/data/r2283-code.json` remains the pinned source snapshot.

The browser and `engine/pr.py` use the same decision contract, exercised by `engine/decision-contract-cases.json` in both Python and Node. Acceptance requires an acceptance-compatible position for every refusal, `accept_scope` for every finding, and acknowledgement of every unknown. Changes and escalation need only a human reason. Escalation is stored as `escalated`, displayed as pending owner judgement and mapped to GitHub `pending`.

No outcome, position or acknowledgement is preselected. Validation marks the specific refusal, finding, unknown, outcome or reason field that needs attention, explains why, offers a jump to the first one, and never clears what the human typed. On narrow screens the decision controls stack vertically. Drafting never posts, persists or signs. The GitHub receipt comment exposes the same decision-critical brief, classifications, limits, positions and unknowns. Authenticated submission remains in GitHub, and the named human decision remains pending.


## Public judge demo and compact UX update

- The renderer now starts with change/evidence summaries and the decision outcome;
  technical evidence is expandable. Risks stay visible, with acceptance controls
  shown only for acceptance. Provenance labels have their own row; source/diffs
  use build-time Pygments highlighting with no browser runtime dependency.
- `engine/automation.py` processes exact fetched GitHub comment IDs, validates the
  shared contract and current base/head, and sweeps a persisted comment watermark
  to recover coalesced Actions events. Invalid/replayed comments cannot clear a
  valid outcome. `public_demo` permits any human GitHub account on PR #1.
- Actions worker, event bridge template and Pages deployment are implemented.
  **Not activated:** GitHub App registration, repository secrets, bridge installation
  and Pages source setting are still required. See `AUTOMATION_SETUP.md`.
- Python and browser checks cover the changes. No human decision, new .NET test
  evidence, automatic merge or live end-to-end judge run has been created.
