# Review Receipt: our HackJunction 2026 submission

Our contribution is the Review Receipt system: evidence engine, model integration, receipt format, PR decision flow and walkthrough. Supplied code and prepared AI patches are demonstration material; attribution is in the README.

Challenge: Tieto, *Earned Trust in AI Code*. Question: how can AI review code made by AI so that humans can trust it?

## Recommendation

Do not ask humans to trust the AI reviewer. Ask them to trust **evidence they can check**, and make the AI reviewer produce it.

For each agent-written change, produce a **review receipt** that a named engineer can decide on without reading every line. The receipt answers four questions:

1. **What did the change claim to do, against which requirement?** We use local demo requirement IDs, such as R2283. The original sample identifiers remain in archived evidence for reproducibility.
2. **What was checked, by what, and what does that not cover?** Every executed check records its scope, status and limitations.
3. **What does the evidence support, and what remains risky or unknown?** A decision brief separates harness observations, AI interpretation and our connective explanation. Claim classifications are evidence links, not semantic verdicts.
4. **What must the human decide, and how deeply should they look?** Rules, not a score, name the depth. Acceptance requires explicit positions on unresolved risks and acknowledgements of unknowns; requesting changes or escalating needs only a reason. Source and diffs are optional corroboration.

AI gives advice. A named human decides, and the decision is bound to the exact head commit.

## Principles

1. **Three kinds of statement, never mixed.** Executed checks (written only by the harness), AI claims (proposed by a model, status computed), and AI refusals (questions for the human).
2. **A model's prose cannot become evidence.** The model never sets a status. The engine re-resolves each citation against git and computes the status.
3. **A claim is verified only through a named test that ran.** A whole-suite pass cannot verify a specific claim; that link goes to a human. We display this as **Test-backed**, not "true".
4. **Failed, skipped and not-run checks stay visible.** None becomes a pass.
5. **No trust or hallucination score.** Contradicted and unsupported are mechanical evidence-linkage results; a real citation and a passing test can still support a wrong interpretation.
6. **Route attention by named rules.** Every review depth lists the rules that fired and what was observed. Source is optional corroboration.
7. **Decisions are bound to a commit.** Changing the head SHA makes the receipt stale.
8. **Ownership stays human.** No automatic approval or merge. Escalation remains pending owner judgement, not acceptance or failure.

## One change, end to end: R2283

The change is an AI patch for the issue "generator and analyzer crash with `IndexOutOfRangeException` on a closed generic struct from a referenced assembly" (pinned base `32258fdb`, head `9df83c38`). The crash-only comparison uses a local hand-applied approximation of a reference fix; it does not execute the reference patch itself.

**Provenance.** The published page now uses [a fresh live model receipt](../examples/receipt-2283.live.json) without injected claims. Its eight claims include two test-backed (engine status `verified`), one contradicted, one unsupported and four source-only. The checks are real recorded runs reused for the exact pinned commits. The claims, refusals and out-of-requirement items in [the worked example](../examples/receipt-2283.example.json) are hand-written. A separate [model-generated receipt](../examples/receipt-2283.model.json) (DeepSeek, five bad claims injected on purpose) independently flagged the same diagnostic filter and docs additions.

**What the engine verified** (all runs: .NET SDK 8.0.402, `net8.0`, generator test project):

- The AI's 3 new tests **fail on the base source** with the reported crash and **pass on the head** (CHK3, CHK2). The patch fixes the reported crash.
- The existing generator tests still pass on the base (167) and the head (170, including the 3 new ones).

**What the AI found beyond the requirement:**

- The patch adds a filter that drops every diagnostic located outside the compilation. The issue only asks for the crash to stop.
- The patch adds README and `MsgPack004.md` text that the issue does not request.
- A third proposed item was withdrawn after source review: the `BothStringAndIntKeyAreNull` change is one of the two live unsafe declaration-reference sites the patch replaces, not extra scope. The raw model output remains archived unchanged rather than being rewritten to look better.
- We ran the AI's tests against a minimal fix of our own (the `FirstOrDefault()` reference-fix idea, applied by hand because the PR does not apply cleanly). One AI test fails there: it expects zero diagnostics but gets two `MsgPack004` errors for an unkeyed member of a referenced generic struct. The AI patch silences them. That is a behaviour change nobody asked for, and the receipt keeps it visible as comparison evidence, not a broken build.

**What the AI refused to decide:**

- Should the consuming project stop reporting `MsgPack004` for members of referenced types? Dropping the diagnostic hides a real problem in a dependency; keeping it can break a build over code the consumer cannot change. That is the maintainer's policy.
- Is the new documentation correct that the defining assembly reports these problems? That holds only if the defining assembly runs the analyzer, which the AI cannot know for a consumer's dependencies.

**How a reviewer decides without reading code.** The walkthrough leads with an 11-statement decision brief in five sections: requirement intent, what the evidence supports, material risks, limits, and how reliable the AI's claims are. Each statement is tagged as a harness observation, AI interpretation or team explanation and links to the recorded check, claim, refusal, finding or unknown. The page derives its counts from the receipt: 2 of 8 claims are test-backed; the patch suite recorded 170 passed of 170; the same tests on base source recorded 3 failed of 170, which is the useful result. It shows exact classification reasons, every check's limits, two refusals with structured positions, two outside-requirement items, and two residual unknowns.

The human chooses **accept listed risks**, **request changes** or **escalate for code/domain review**. Acceptance needs an acceptance-compatible position for REF1 and REF2, `accept_scope` for OOR1 and OOR2, and acknowledgement of UNK1 and UNK2. Changes and escalation need only the reviewer's own reason. Source and diffs remain collapsed optional corroboration; a missing or stale code snapshot hides only that panel and cannot remove the decision path. The receipt records the decision as `pending`; no engineer has signed this one.

**The contrast: R2234.** The issue is one sentence with no expected behaviour. Claims cannot be traced to a requirement, so the receipt routes to standard review whatever the code looks like. The AI's tests also fix a broader crash than the one reported, and the reported regression is unproven.

**Triage across all four samples** (before any AI call, from requirement quality and diff shape): R2283 light, R2234 standard, R2129 full read (contested requirement, 458 changed source lines), R2297 full read (open product decision; its 222 generated files are a candidate for machine-checking instead of reading; that check is not built).

## What exists today

| Part | State |
| --- | --- |
| Receipt schema and validator with invariant checks | Built. [Schema notes](RECEIPT_SCHEMA.md) |
| Engine: citation resolution, claim status, routing rules, triage | Built; see test commands in [PR flow](PR_FLOW.md) |
| Model step: DeepSeek V4.1 Flash proposes claims, refusals, unknowns | Built; run on R2283 |
| Per-test evidence parsed from raw `.trx` logs | Built for R2283 |
| Check runner | **Not built.** Check results are recorded from `evidence/` scripts |
| Walkthrough page: decision brief, risks, classifications, checks, optional source, PR comment draft | Built and [published](https://nicholsss.github.io/junction/); decisions happen in GitHub |
| Four demo PRs, receipt comment upsert and exact-head commit statuses | Built; [PR links](PULL_REQUESTS.md), [CLI instructions](PR_FLOW.md) |
| Fresh model receipt without injected claims | Built for R2283; two test-backed, one contradicted, one unsupported, four source-only claims; two refusals, two findings and two unknowns |
| Shared browser/CLI decision contract | Built; both validators run the same JSON cases. Acceptance requires positions and acknowledgements; changes and escalation need only a reason |
| Human decision ingestion | Built and tested with mocked GitHub; no actual human sign-off yet |
| pull_request Action and required-status branch protection | **Not built.** Operator runs the CLI and republishes snapshots |
| Receipts for R2234, R2129, R2297 | Triage only; no deep receipt |

## Trade-offs

- **Fewer verified claims, more human attention.** Requiring a named test keeps `verified` honest but pushes the link between claim and test to a person. That is deliberate.
- **A no-code decision path, with source still available.** The brief, risks, classifications and unknowns carry the decision; source is optional corroboration. The cost is that the brief is authored prose and could omit a concern that only a diff would reveal, so citations remain available for drilling down.
- **Rules over a score.** Rules can be argued with and tuned. A score hides who decided what. The cost is that thresholds are guesses until measured.
- **Deterministic engine, advisory model.** The model adds coverage (it found the scope change unprompted), but the engine decides statuses. The cost is that the model's claims are only as good as its choice of claim.
- **Probes versus gates.** A comparison run (like the minimal-fix probe) is reported through the claims it contradicts and does not fail the build. A mislabelled probe could hide a real failure.
- **Escalation is a real outcome.** A reviewer who cannot resolve a question can route it without pretending to accept or reject. The cost is that "pending owner judgement" can look like no progress if no owner is available.

## Limits

- **Relevance is not proven.** The engine checks that a named test exists and ran, not that it tests what the claim says. `verified` means "a named test had the outcome the check needs".
- **Classifications are not semantic verdicts.** `contradicted` and `unsupported` are evidence-linkage results. They are not hallucination counts, and the page shows no trust score. CLM7 and CLM8 in the live receipt are examples of a mixed probe expectation and an inexact test-name link, not proof that the prose is false.
- **Citations prove existence, not support.** A citation that resolves points at real lines; whether those lines say what the claim says is not checked, so code claims reach `source_only` at most.
- **Outcome expectations belong to the check, not the claim.** One real model claim was marked contradicted only because it also cited a probe that fails.
- **One repository, one environment.** Single runs on .NET 8.0.402 and `net8.0`. The two-project repro from the issue was not run, and the `ExecutionTests` project does not compile even on the untouched base.
- **The minimal fix is our local approximation of a reference fix**, not the PR.
- **Thresholds are untuned.** The 400-line limit is a guess.
- **No code-free usability or time-saving result.** The browser path was exercised with a local jsdom smoke test and the renderer's tests, not a human study. A real named decision has not been recorded.
- **Hackathon scope.** None of this establishes long-term reliability.

## Failure modes and how they are handled

| Failure mode | Handling | Residual risk |
| --- | --- | --- |
| Model invents a citation | Re-resolved against git; claim becomes `unsupported` | A real line that does not support the claim passes |
| Model claims "tests pass" with no run | No executed check, so `unsupported` | None for this case |
| Model cites the whole suite for a specific claim | `needs_link_review`, standard tier | Human must judge the link |
| Model invents a test name | Name not in any cited check, so `unsupported` | None for this case |
| Model attaches a passing check to a code-only claim | Check references stripped and noted | None |
| Failed or skipped check read as a pass | Statuses are separate; not-run checks are listed in routing reasons | Reader ignores the listing |
| Fail-then-pass misread as a broken build | Checks have `expected` and `role` (gate or probe) | Mislabelled probe |
| Requirement too weak to trace claims to | Routes to standard; claims cannot be traced to stated criteria | Derived criteria are ours and labelled as such |
| Change grows after sign-off | Decision binds to the head SHA; a different head is stale | None |
| Reviewer rubber-stamps | Acceptance requires every refusal and finding position plus every unknown acknowledgement; changes and escalation need a reason | A reviewer can still write a thin reason or click through |

## Measurement

The hackathon demo can only show the first row. The rest is the plan.

| Question | Measure | Today |
| --- | --- | --- |
| Do claims hold up? | Share of model claims classified as test-backed, contradicted, unsupported or needs-link-review, on seeded bad claims and real ones | Historical fixture: all 5 injected bad claims held from verified; 3 of 8 uncontaminated claims verified. Live R2283 run: 2 of 8 test-backed |
| Does it save review time? | Time to decision with a receipt versus a plain diff, on the same changes | Not measured |
| Does it catch real defects? | Planted defects found by reviewers with a receipt versus without | Not measured |
| Does it mislead? | "False reassurance" rate: reviewers who accept a defective change because the receipt looked clean | Not measured |
| Is routing right? | Agreement between tier and an expert's judgement of how deep the review needed to be, per change | Not measured |
| Does it matter later? | Reverts, hotfixes and incidents on accepted changes | Not measured; needs months |

Proposed first experiment: six agent-written changes, three with a planted defect, reviewed by pairs of engineers with and without a receipt. Record time, defects caught and false reassurance.

## Decisions and lessons

See [the decision log](DECISIONS.md). Notable: the engine's first routing run sent R2283 to full read because a comparison probe was counted as a broken build (fixed with `role`); the first model run marked a claim `verified` because the whole suite passed (fixed with named tests); the model first wrote every real claim as a code description and verified nothing (prompt now asks for behaviour claims per acceptance criterion).

## Evidence-led reference presentation

The page opens on R2283 and presents the decision brief first: intent, supported evidence, material risks, limits, and claim reliability, each statement carrying provenance and evidence references. Next come the structured risks and unknowns, evidence classifications with exact reasons, executed checks with scope and limits, and the human decision. Source excerpts and diffs moved into a collapsed **Optional implementation evidence** panel; if the snapshot is missing or does not match the base and head, only that panel is replaced by a warning. A reviewer can reach accept, request changes or escalate without opening code.

Acceptance requires an acceptance-compatible position for both refusals, `accept_scope` for both findings, and acknowledgement of both unknowns. Changes and escalation need only the human's reason. Invalid drafts mark the exact field that needs attention, say why, offer a jump to the first one and keep the human's input; on narrow screens the controls stack. The browser and CLI use the same contract cases; only the authenticated CLI applies a decision. Nothing is preselected and no human decision is simulated. The GitHub receipt comment carries the same decision-critical brief, classifications, limits, positions and unknowns so the reviewer does not need to open the page to discover a caveat. The UX change has not been measured for time savings, and R2283 remains pending.
