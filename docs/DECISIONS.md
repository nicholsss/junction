# Decisions and lessons

## Initial direction

- Working name: Review Receipt.
- Build a reference implementation focused on evidence and human accountability.
- Begin with one small supplied agent-written change.
- Keep model claims separate from executed validation.
- Technology choices remain provisional until sample inspection.

## 2026-11-14: requirement IDs and lead sample

- Question: what are the requirement IDs, and which change leads the demo?
- Evidence observed: the challenge page names no separate requirements set. The four issue numbers are the IDs. #2283 has a repro, trigger matrix and expected behaviour, and upstream PR #2305 is a human fix. #2234 has a one-sentence report. The AI patch for #2283 adds a diagnostic-dropping filter that neither the issue nor PR #2305 has.
- Decision: use issue numbers as requirement IDs. Lead with #2283, show #2234 as the weak-requirement contrast, and use #2129 and #2297 in a triage view. Trade-off: #2283 needs a real IL-compiled test setup, so it is slightly heavier than #2234.
- Limitation: all findings come from reading diffs. No tests have run, and .NET is not installed.
- Next action: set up .NET 8.0.402 and run the checks listed in [review findings](REVIEW_FINDINGS.md).

## 2026-11-14: first test evidence

- Question: do the AI patches' new tests prove anything?
- Evidence observed: installed .NET 8.0.402 to `~/.dotnet`. Parent: 167 pass. #2283: all 3 new tests fail on the parent source with the reported crash, then pass. #2234: 4 of 8 new tests fail on the parent (duplicate and mixed keys, including a non-suppressed type), 4 already pass. The `ExecutionTests` project does not compile even on the parent.
- Decision: treat #2283 as verified for the reported crash only. Treat #2234 as "fixes a broader crash; reported regression unproven". Show the `ExecutionTests` check as unavailable, not passed.
- Failure or limitation: one environment, one run each, only the generator test project. The #2283 diagnostic-dropping concern is untested.
- Next action: test which diagnostics `ReportIfLocatedInCompilation` drops, and compare with upstream PR #2305.

## 2026-11-14: does the #2283 patch drop diagnostics?

- Question: does `ReportIfLocatedInCompilation` change which diagnostics users see?
- Evidence observed: with a hand-applied minimal fix on the parent, the AI candidate's tests give 169 of 170 passing. The failing one expects zero diagnostics but gets two MsgPack004 errors for an unkeyed member of a referenced generic struct. The AI patch silences them.
- Decision: record it as a scope decision for the human owner, not as a defect. The patch's reasoning (consumers cannot fix referenced code) is plausible, but the issue does not ask for it and its docs claim is unchecked.
- Failure or limitation: only one diagnostic kind tested. The minimal fix is our approximation of PR #2305, not the PR.
- Next action: compare against PR #2305 on the two-project repro, and use this case as the "AI found / human decides" example in the demo.

## 2026-11-14: engine without a model first

- Question: can status and routing be computed without trusting model text?
- Evidence observed: a Python engine resolves citations against git, derives claim status from claim kind and executed checks, and routes by named rules. On the #2283 example it reproduced the hand-written statuses exactly (source_only, verified, verified, unsupported, contradicted).
- Decision: claims get a `kind`, checks get `expected` and `role`. Reason: the first routing run sent #2283 to full read because a comparison probe's failure was treated as a broken build. That probe's result is the finding, so probes are now separate from gates. Trade-off: authors must label checks correctly, and a mislabelled probe could hide a real failure.
- Failure or limitation: the engine proves a citation exists, not that it supports the text. Thresholds are guesses. No model is involved yet, so hallucinated claims have not been exercised.
- Next action: add the model call that proposes claims, and feed deliberately bad claims through the engine.

## 2026-11-14: first model run

- Question: can a model propose claims without the engine believing its prose?
- Evidence observed: DeepSeek V4.1 Flash returned 8 claims, 2 refusals, 3 out-of-requirement items and 5 unknowns for #2283 in one call (4.5k tokens in, 1.3k out). All 8 citations resolved. It found the diagnostic-suppression scope change on its own and listed the unrun repro as an unknown. Of the 3 injected bad claims, the engine marked 2 `unsupported` and 1 `contradicted`.
- Decision: keep the model advisory. Statuses stay computed. Check references the model invents, or attaches to code-only claims, are stripped and noted.
- Failure or limitation: the engine marked one model claim `verified` on the strength of the whole suite passing, which is a weak link between claim and check. The engine cannot judge relevance. Also fixed a validator rule that wrongly rejected an unresolved-citation claim that cited a passed check.
- Next action: require each claim-to-check link to name the specific test, or have the human confirm links; run the same step on #2234.

## 2026-11-14: claims must name a test

- Question: should a passing whole suite be able to verify a specific claim?
- Evidence observed: in the first model run, a claim about out-of-compilation diagnostics was marked `verified` because the 170-test suite passed. Nothing showed that any test touched that claim.
- Decision: checks now carry per-test results parsed from raw `.trx` files, and a behaviour claim is verified only through a named test that ran with the right outcome. Citing a check with no named test gives `needs_link_review` and routes to standard. Trade-off: fewer claims reach `verified`, and the model has to do more work in the prompt.
- Evidence after: the fixture still computes its original statuses. The model run (13 claims, 5 injected bad ones) gave 3 verified, 1 contradicted by a probe, 1 `needs_link_review`, 4 unsupported and 4 source-only. Invented test names and the true-but-suite-only claim were both caught. With the earlier prompt the model wrote every real claim as `code_fact` and nothing was verified, so the prompt now asks for a behaviour claim per acceptance criterion.
- Failure or limitation: relevance of a named test is still judged by the model. `expected` is per check, so one model claim that cited a probe was marked contradicted for a reason unrelated to its meaning.
- Next action: run the same step on #2234, then write the concept card.

## 2026-11-14: concept card review

- Question: does the concept card claim more than the evidence shows?
- Evidence observed: reading it against the repo found four overclaims: what the human can skip after reading (it covered shapes we never ran), who found what (the worked example's claims are hand-written, the model run is separate), machine-checking of generated files (not built), and a line range of 1444 where the diff says 1443.
- Decision: state provenance in the card (real runs versus hand-written versus model-generated), narrow "what the human can skip" to the reported crash shape, and mark unbuilt parts as not built.
- Failure or limitation: the measurement table still has one row with a number. The other five are plans, not results.
- Next action: close the log and, if time allows, add a seeded-defect corpus to get more rows with real numbers.

## 2026-11-14: lessons so far

What we would tell the next team, in order of how much it changed our design:

1. **A passing run is not support for a claim.** Our first model run marked a claim `verified` because the whole 170-test suite passed. Fix: a behaviour claim is verified only through a named test that ran with the outcome the check expects. The cost is fewer verified claims and more human attention, on purpose.
2. **A failing check is not always a failure.** The minimal-fix comparison fails one test by design, and the first routing run sent #2283 to full read because of it. Fix: checks carry `expected` and `role` (gate or probe). The risk moved to labelling, since a mislabelled probe could hide a real failure.
3. **Models write prose that sounds like review.** Given freedom, the model labelled every real claim a code description, so nothing was testable. A model also cannot be trusted with status or check references: the engine strips invented ones and computes status itself.
4. **Existence is not relevance.** The engine proves a citation or test name exists and ran. It cannot prove the test tests what the claim says. We state this as a limit instead of hiding it behind the word "verified".
5. **Weak requirements cap what any reviewer can verify.** #2234 is one sentence, so claims cannot be traced to a criterion whatever the code looks like. The receipt routes it to standard and says why.
6. **Our own writing overclaimed more than the code did.** The review of the concept card found four overstatements. Reading the text against the repo before submitting is worth the time.
7. **The real finding was a scope question.** The AI patch for #2283 fixes the reported crash and also silences diagnostics nobody asked about. A maintainer has to decide that, and the receipt turns it into a question with an owner.

What we did not do: no human pilot, no review-time measurement, no check runner, no UI, no deep receipt for #2234, and the #2283 decision is still `pending`. The only measured result is that 5 of 5 injected bad claims were caught on one change, plus 3 of 8 real claims verified. That says the mechanism works on one case; it does not say it generalises.

## 2026-11-14: walkthrough page

- Question: can a reviewer see, in a few minutes, what to trust, what to check and who decides?
- Evidence observed: `engine/render.py` renders one static page (`walkthrough/index.html`) from the receipt JSON, with three views: queue of the four samples (triage tier, and the tier after evidence for #2283: light to standard), the #2283 receipt (read-this-first list, requirement-to-claim table, claims with an evidence chain, a fail-then-pass table of the new tests, checks, findings, refusals, decision bar) and measurement. Checked in the browser pane at 1280 and 375 wide: no console errors, no horizontal overflow on the page. Decision form tested end to end (locks until every refusal is answered and finding rated, confirms, saves, records seconds to decision); test data cleared afterwards. 8 render tests check head SHA, claim statuses copied from the receipt, pending decision, and the measurement numbers.
- Decision: hand-written HTML and CSS with a small JS, no framework. Status colours are colour-blind safe with a text label and icon each; review tiers use one blue hue in three steps, not a traffic light. Only three charts, all stacked bars or a table. A decision is saved in the browser only and the receipt file stays `pending` until a person downloads and commits it.
- Failure or limitation: not checked with a screen reader or a contrast tool. No decision has been signed. The queue's owner column says "Not assigned". The model-run claims table on the measurement view is read from the model receipt, which includes five deliberately wrong claims.
- Next action: a real sign-off on #2283, the demo script, and (if time) the seeded-defect corpus.

## 2026-11-14: real PR integration (implementation record)

- Observed: the user authorized the fork, branch pushes, four PRs, receipt comments/statuses and GitHub Pages. Each demo PR targets its AI commit's parent. PR links are in `docs/PULL_REQUESTS.md`.
- Implemented: `engine/pr.py` upserts a marked comment and sets pending; pure functions parse actual human commands, require refusal answers for accept, enforce a designated GitHub User, and bind decisions to the exact base/head. Tests use mocked GitHub and never post a human sign-off. A second PR read catches pushes during processing.
- Evidence: a fresh non-injected #2283 model run, attached recorded TRX tests and validated engine output: 2 verified, 1 contradicted, 1 unsupported, 4 source-only, with 2 questions. The injected model experiment remains separate for Measurement. No .NET runs were repeated.
- Verification: 62 unit tests pass; live schema validation passes. Browser verification at 1280px and 375px found and fixed long-identifier grid overflow; final receipt width matches each viewport and no console errors were observed. Each PR has exactly one receipt comment and a pending status; no decision comment exists.
- Page: PR links/statuses, a copyable GitHub comment draft and published snapshot replace browser-local decisions. Source and scope citations are included in Read this first. No decision can be recorded by the browser.
- Limits: no actual human has signed; no signer assigned. A single login cannot demonstrate independent review. A real stale-after-push demonstration is not performed; stale behavior is covered by mocks. A pull_request Action, model-key secret integration, required-status branch protection and automatic publication are not built. This entry records implementation facts, not a product-policy decision or approval of the sample change.
- Next human action: read REF1/REF2 and post a real decision if ready. The operator can then run `decide` and republish. Deadline supplied as today; no precise cutoff.

## Log template

For each meaningful decision or experiment, record:

- Question or hypothesis
- Evidence observed
- Decision and trade-off
- Failure or limitation
- Next action

## 2026-11-14: submission ownership and local demo presentation

The user confirmed that Review Receipt is our HackJunction submission. Public demo surfaces now use local R-prefixed requirement labels and our own requirement snapshots, without upstream issue links or review requests. The README attributes the supplied sample code and distinguishes it from our review system. Original licenses, authorship, pinned commits and historical receipt evidence are retained. The technical fork relationship is kept to preserve the four PRs and their receipt comments; no detachment or recreation was performed. The handoff now records this agreed scope. No human sign-off or new test-run evidence was created by this presentation change.

## 2026-11-14: focused review reference

- Observed failure: repeating requirements, findings, claims and checks made the reviewer reconstruct the conclusion and leave the page to inspect code.
- Design decision: default to one change, its consequential diagnostic-suppression risk, observed and unproven evidence, source excerpt and a small source-backed behavior path. Keep the complete diff and audit trail expandable. This deliberately avoids an unverified dependency graph.
- Human interaction: explicit risk positions replace repeated prose answers; one reason explains the outcome. Nothing is preselected. Requesting changes does not require resolving policy questions; accepting requires explicit positions and residual-risk reasoning. Only an actual GitHub comment by a named human can become a decision.
- Evidence integrity: copied code comes from pinned git commits; renderer rejects a mismatched snapshot. Display-only substitutions omit upstream issue URLs in test comments. Archived source and test results are unchanged. Test-backed labels clarify that named-test execution does not prove semantic relevance.
- Limits: no usability or time-saving measurement, no new .NET execution, no complete impact analysis, and no valid human sign-off. The page is still a published reference snapshot.
- Attribution correction: new Pages commits no longer add the inherited inaccurate Claude trailer. Existing public commits are untouched.

## 2026-11-14: evidence-led review without required code reading

- Scope: make R2283 the one complete evidence-led decision path; the other three samples remain triage-only. A human must be able to reach any available outcome without reading source or diffs. Optional implementation evidence stays collapsed and cannot gate rendering; a missing or stale code snapshot hides only that panel with a warning.
- Presentation: lead with a structured decision brief, material risks and unknowns, AI evidence classifications, executed checks and the human decision. Counts derive from recorded checks. Brief statements carry provenance and evidence references; team-authored connective prose is neither AI output nor reviewer testimony. No second AI summary run is needed. The GitHub receipt comment must expose the same decision-critical evidence as the walkthrough.
- Claim limits: preserve the archived live model claims and mechanical statuses. Show exact status reasons and limitations rather than calling contradicted or unsupported claims hallucinations. In particular, CLM7's mixed probe expectations and CLM8's missing exact test-name link are not semantic verdicts. Atomic/per-link claim evidence is future work, not part of this implementation scope.
- Human outcomes: accept listed risks, request changes, or escalate. Acceptance requires every refusal and finding to have an acceptance-compatible position and every unknown to be acknowledged by ID. Requesting changes needs a concrete reason; escalation needs the missing expertise or evidence in the reviewer's own words. Non-acceptance does not require completing acceptance fields. Escalation is stored as `escalated`, remains pending in GitHub, and does not imply either acceptance or a defect.
- Contract: refusals define stable position IDs and decision effects; findings use accept scope, change required or needs owner judgement instead of real/not real. Unknown acknowledgements use IDs such as `UNK1`. Add `/receipt escalate`; retain the existing accept/changes command style. The browser drafts only human-entered positions and never signs.
- Validation and freshness: receipt-hosted rules feed small JavaScript and Python validators exercised by shared JSON contract cases and error codes; the CLI remains authoritative. Decision-bearing brief and option changes affect the receipt fingerprint and require renewed consent, while layout-only changes do not. The walkthrough remains a pinned snapshot, and `decide` revalidates current PR state.
- Status: the design was approved through the interview; implementation has not started. No new test result, AI receipt, human finding assessment or human sign-off was created. The new root GLOSSARY.md records the agreed domain language.

## 2026-11-14: evidence-led review implementation record

- Implemented: `decisionBrief` in the receipt and schema; refusal `positions` with stable IDs and acceptance effects; structured `refusalPositions`, `findingPositions` and `acceptedUnknownRefs`; the `escalated` outcome; `engine/decision.py`, `engine/decision.js` and shared JSON contract cases; structured `/receipt accept|changes|escalate` parsing, persistence and status mapping in `engine/pr.py`; the rebuilt no-code walkthrough; and a GitHub comment carrying the same decision brief, classification meanings, check limits, positions and unknowns.
- Observed verification: 105 tests passed, 1 failed and 0 errored across `test_review`, `test_decision`, `test_render` and `test_pr`. The single failure is `test_real_line_resolves`, which needs the deliberately ignored `sample/` checkout; it is an environment gap, not a regression. `jsonschema` was installed in a git-ignored project `.venv`, and all three receipts validate. Both the Python and Node decision-contract suites pass. A local jsdom smoke test confirmed that acceptance stays blocked until every required position and acknowledgement is chosen, that changes and escalation enable with a reason alone, that errors identify the field to fix without clearing input, and that escalation remains pending owner judgement. That smoke test is not a committed suite and is not a substitute for human usability testing.
- Source handling: the renderer treats the pinned source snapshot as optional. A matching base and head show a collapsed source panel; a missing or mismatched snapshot replaces only that panel with a warning. The decision brief, classifications, checks and form remain usable. The checked-in walkthrough matches `render.build`.
- Evidence correction: the third proposed outside-requirement item (the `BothStringAndIntKeyAreNull` change) was withdrawn after source review because the recorded diff shows it is one of the two live unsafe declaration-reference sites the patch replaces, not extra scope. The raw model output in `evidence/propose-2283.live.raw.json` was not edited. The live receipt remains pending; no human decision or new .NET run was created.
- Limitations: mechanical claim classifications remain evidence-linkage results, not semantic verdicts or hallucination scores. The decision contract enforces completeness, not the quality of a human reason. The page is still a pinned snapshot, not a live GitHub feed. Production event automation, branch protection and a measurement of review time or human decision quality remain unbuilt.


## 2026-11-14 — compact review and public-demo event automation

The main review view now prioritizes the intended change, recorded evidence and
outcome. Material risk consequences and unknowns remain visible; detailed claims,
checks and provenance explanations move behind supporting-evidence disclosures.
Source highlighting is generated with Pygments and remains optional.

The user requested participation by unknown judges: `public_demo` therefore lets
any authenticated GitHub human record a demo outcome on registered PR #1. This is
explicit on the page and never triggers a merge. Restricted `allowlist` mode remains
available. Bot authors, edited commands, invalid positions, replayed decisions and
stale base/head evidence are rejected independently of the browser.

Actions implementation uses a GitHub App across the engine/Pages and demo PR
repositories. It persists a comment watermark and sweeps GitHub comment history to
recover coalesced pending events. Installation and secrets are a separate activation
step; no live workflow success or human sign-off is claimed by this implementation.
