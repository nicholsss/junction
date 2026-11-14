# Review Receipt submission: PR flow

Review Receipt is our HackJunction 2026 submission. Supplied sample code is demo material; attribution is in the README. Use local labels (`R2283`, etc.) and [our requirement snapshots](DEMO_REQUIREMENTS.md) in public discussions. Do not tag upstream issues or request upstream reviews. Preserve the current repository and PRs rather than detaching the fork.

The four [demo PRs](PULL_REQUESTS.md) are on `nicholsss/junction26-messagepack-csharp`. Their bases are the parents of the supplied AI commits. Requirement R2283 is demo PR #1; the local requirement ID is distinct from the demo PR number. The deadline is today (2026-11-14, Helsinki); no precise cutoff or signer has been supplied. No human decision has been recorded.

The [published walkthrough](https://nicholsss.github.io/junction/) uses `examples/receipt-2283.live.json`: a fresh DeepSeek run without injected claims, with per-test TRX evidence attached and the engine's schema/invariants validated. The `.model.json` fixture remains separate and is used only for the historical measurement experiment with five deliberately wrong claims. The real model run produced eight claims: two test-backed, one contradicted, one unsupported, four source-only. Two refusals and two outside-requirement items remain for a human; a third proposed outside-requirement item was withdrawn after source review because the recorded diff shows it is one of the two live unsafe declaration-reference sites, not extra scope. The raw proposal is preserved unchanged.

## Automated demo path

The repository now includes public-demo comment processing, stale-head detection and
Pages deployment workflows. They require the [one-time App and workflow setup](AUTOMATION_SETUP.md).
Any human GitHub account can participate on registered PR #1; no code is merged.
Until configured, the manual commands below remain the operational path.

## Operator commands

Prerequisites: Python 3 with `engine/requirements.txt` installed, authenticated `gh` with repository/status/Pages access, and the existing local `sample/` clone at the pinned commits. Raw `.trx` files are optional for reposts when per-test results are already in the live receipt. Never commit `.env` or raw machine-specific test logs.

```sh
python3 engine/pr.py post 1
python3 engine/pr.py post 2
python3 engine/pr.py post 3
python3 engine/pr.py post 4
```

`post` updates the existing `<!-- review-receipt -->` comment owned by the authenticated account, and posts a pending `review-receipt` status. Reposting explicitly returns the status to pending; run `decide` again to revalidate an existing human comment for that head. It checks the registered branch names, base and head; the recorded checks cannot be reused for a new revision. R2283 includes the full receipt; the other PRs are explicitly triage only and cannot be signed through this CLI. The live receipt is generated once if absent; reposting does not call the model again. To deliberately regenerate claims, archive the old receipt first and run `engine/propose.py` without `--inject-bad`, using `--raw-out evidence/propose-2283.live.raw.json`, then attach TRX evidence and finalize. Raw live proposal output is preserved in `evidence/propose-2283.live.raw.json`.

## Human action

The human can decide from the walkthrough's decision brief, material risks and unknowns, evidence classifications and checks without reading source or diffs. Source is optional corroboration. The human posts their own GitHub comment; the page can draft and copy it, but nothing on the page signs or sends a decision.

Acceptance uses stable positions and acknowledgements, not free-text answers:

```text
/receipt accept I accept the recorded suppression and documentation risks for this change.
Head: 9df83c38409c8bfad0517aebffe48211eda4a5b4
REF1: ref1_accept_suppression
REF2: ref2_accept_limitation
OOR1: accept_scope
OOR2: accept_scope
UNK1: acknowledged
UNK2: acknowledged
```

The walkthrough fills the recorded IDs and allowed values; replace only the reason and your own choices. Acceptance is valid only when every refusal and finding has an acceptance-compatible position and every unknown is acknowledged. A position with effect `changes_required` or `escalation_required` cannot be combined with accept.

Requesting changes or escalating needs only the human reason:

```text
/receipt changes The filter hides diagnostics the consumer cannot investigate.
Head: 9df83c38409c8bfad0517aebffe48211eda4a5b4
```

```text
/receipt escalate A source-generator owner must judge whether dependency diagnostics may be suppressed.
Head: 9df83c38409c8bfad0517aebffe48211eda4a5b4
```

Structured lines are optional for those outcomes. Append `-- your note` to a REF or OOR line to record an optional note; unknown, duplicate or malformed IDs are rejected with an actionable explanation. The authoritative rules live in `engine/decision.py`; the browser uses `engine/decision.js` against the same shared cases. Neither the browser nor the generated comment is a decision until a named human posts it in GitHub.

After that actual comment exists, the operator identifies its real author and runs:

```sh
python3 engine/pr.py decide 1 --human TEAMMATE_LOGIN --name 'Actual human name'
```

The CLI only accepts a GitHub `User` comment by that designated login, newer than the receipt comment, with a reason and the exact Head line. It excludes the receipt marker, checks the published receipt's evidence digest and re-reads the PR before applying the decision. It records the author's name/login, reason, structured positions, acknowledged unknown IDs, head SHA, source comment URL and GitHub comment timestamp; validates with the same Python decision contract, commits the receipt and rendered snapshot, then sets the mapped status. The operator-supplied name maps a person to the authenticated GitHub commenter; it is not independent identity verification. No teammate invitation is needed to comment on these public PRs.

Status mapping is distinct: `accepted` → GitHub `success`; `changes_requested` → `failure`; `escalated` → `pending`, displayed as "Escalated — pending owner judgement". Escalation is neither acceptance nor a finding that the change is defective.

With a single account, automation and the human have the same GitHub login. The CLI rejects that by default. Only after a real human posts their own comment can the operator explicitly use `--allow-same-account`. This is an acknowledged demo limitation, not evidence of independent review. Prefer a teammate's own account. No signer is assigned today.

Missing positions or acknowledgements produce an explanatory comment and leave pending. A different base or head produces a stale comment and pending on the new head. A decision for the old SHA never creates success for a new SHA. A fresh checkout/evidence run is required to cover a changed revision; editing receipt SHAs does not refresh evidence.

After an applied decision, publish the resulting commit and snapshot:

```sh
git push origin main
python3 engine/publish_pages.py
```

Pages uses `gh-pages` at `/`; that branch contains only the walkthrough and `.nojekyll`. The main branch retains source and receipt JSON. `publish_pages.py` never force-pushes. Re-run it after any decision or status change that should appear on the public page. GitHub and the page are snapshots until the CLI and publication run again.

## Verification and limits

```sh
python3 -m unittest engine/test_review.py engine/test_decision.py engine/test_render.py engine/test_pr.py
node --test engine/test_decision.js
python3 schema/validate.py examples/receipt-2283.live.json
python3 -m http.server 8765 --directory walkthrough
```

Tests mock GitHub for accepts, changes, escalation, missing or contradictory positions, missing acknowledgements, unknown/duplicate IDs, malformed structured lines, optional notes, placeholders, wrong/bot/same-account authors, stale base/head, a push during processing, comment escaping and upserts. No human decision was posted during tests. Earlier browser checks covered 1280px and 375px widths and comment-copy behavior; this change was not re-checked at those widths in a real browser. A local jsdom smoke test confirmed that acceptance remains gated, that changes and escalation need only a reason, that errors identify the field to fix without clearing typed input, and that escalation stays pending owner judgement. It is not part of the committed suite or a substitute for a real browser or a human usability study.

**Automation update:** event processing, push invalidation and Pages deployment code now exist, pending activation as documented in [setup](AUTOMATION_SETUP.md). Not built: automatic receipt/evidence refresh, a general check runner, or configured branch protection requiring `review-receipt`. The limitations below describe the manual path until activation. Without event automation a new commit has no successful receipt status, but a pending status/stale explanation is posted only when the CLI runs. The page does not live-poll GitHub. There is a small unavoidable read/status API race; no atomic GitHub head lock is claimed. Human sign-off and a live stale-after-push demonstration have not happened. Existing .NET checks were reused, not re-executed this session.

API references: [commit statuses](https://docs.github.com/en/rest/commits/statuses), [GitHub Pages configuration](https://docs.github.com/en/rest/pages/pages).
