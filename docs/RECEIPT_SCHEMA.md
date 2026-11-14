# Receipt schema (draft v0.1)

Files: [`schema/receipt.schema.json`](../schema/receipt.schema.json), [`schema/validate.py`](../schema/validate.py), and a worked example, [`examples/receipt-2283.example.json`](../examples/receipt-2283.example.json).

```bash
python3 schema/validate.py examples/receipt-2283.example.json   # needs: pip install jsonschema
```

## Core idea

Four kinds of statement are kept in separate lists, so a model's prose cannot become evidence:

| Kind | List | Who writes it |
| --- | --- | --- |
| Something that was executed | `checks` | The harness only. Has status, scope, limitations and a raw log path. |
| Something the AI asserts | `claims` | The model proposes text and a citation. The validator sets `citation.resolves` and `status`. |
| Something the AI will not decide | `refusals` | The model, with a reason and the positions a human may choose. The human records one explicit position. |
| How the evidence reads without source | `decisionBrief` | Harness observations, archived AI interpretation and team-authored connective explanation, each with provenance and references. No statement is human testimony. |

## Sections

- **requirement:** the issue number as ID, its quality rating, and acceptance criteria marked `stated` (in the issue) or `derived` (ours, not authoritative).
- **subject:** repository, branch and the full base and head SHAs. A receipt is about exactly this range.
- **decisionBrief:** optional plain-language statements in five sections (`intent`, `supported`, `risk`, `limit`, `reliability`). Each statement has one provenance: `harness` (recorded observation), `model` (archived AI interpretation) or `team` (explanation authored for this presentation). `evidenceRefs` point only at recorded checks, claims, refusals, outside-requirement items, unknowns or acceptance criteria.
- **checks:** status is one of `passed`, `failed`, `skipped`, `unavailable`, `not_run`. A `failed` check is sometimes the useful result (a new test failing on base source proves it detects the bug), so the scope field says what the check shows.
- **claims:** each has a file and line citation at a pinned SHA, links to acceptance criteria and checks, and a status: `verified`, `source_only`, `unsupported`, `needs_link_review` or `contradicted`, with a stated reason. `verified` is displayed as **Test-backed**: it records an evidence link, not semantic truth.
- **refusals:** what the AI would not decide, plus optional `positions`. Each position has a stable `id`, a human-readable `label` and an `effect`: `accept_compatible`, `changes_required` or `escalation_required`. A refusal that offers positions must offer at least one acceptance-compatible position.
- **outOfRequirement, unknowns:** what the change does beyond the requirement, and what was not checked. Outside-requirement items use the finding positions `accept_scope`, `change_required` and `needs_owner`; unknowns are acknowledged by ID when accepting.
- **routing:** a tier (`light`, `standard`, `full_read`) with named rules and what was observed, plus optional source focus. No numeric score.
- **decision:** `pending`, `accepted`, `changes_requested` or `escalated`. A non-pending decision records the named owner, reason, structured `refusalPositions`, `findingPositions`, `acceptedUnknownRefs` (acceptance only) and the head SHA the owner signed. `refusalAnswers` and `acceptedResidualRisk` remain readable for historical receipts but are not produced for new decisions.

## Rules the validator enforces beyond the schema

1. An executed check must have a raw log; a `not_run` check must carry no results.
2. A `verified` claim must cite at least one check and a citation that resolves.
3. A claim cannot cite a check that was not run.
4. A `source_only` claim cannot cite a passed check.
5. A `verified` behaviour claim must name at least one test, and every named test must appear in a cited check's `tests`.
6. A claim whose citation does not resolve must be `unsupported`.
7. IDs are unique within each list, and every `decisionBrief.evidenceRefs` value resolves to a recorded item.
8. Refusal position IDs are unique, and any refusal that records positions offers at least one that permits acceptance.
9. A decision references only recorded refusals, positions, findings and unknowns, without duplicates, and is bound to the current head SHA.
10. An `accepted` decision passes the shared decision contract: a non-placeholder human reason, an acceptance-compatible position for every refusal and every finding, and an acknowledgement for every unknown. `changes_requested` and `escalated` require the human reason but not the acceptance fields.

## Engine (no model calls yet)

[`engine/review.py`](../engine/review.py) does the deterministic parts. Run from the repo root, with the sample cloned in `sample/`:

```bash
python3 engine/review.py finalize examples/receipt-2283.example.json   # re-resolve citations, recompute statuses and routing, validate
python3 engine/review.py triage                                        # cheap pre-AI routing of the four branches
python3 -m unittest engine/test_review.py                              # 27 tests of the rules
```

**Claim status is computed, never written by the author.** Claims have a `kind`:

| Kind | Rule |
| --- | --- |
| `code_fact` (describes the cited code) | `source_only` if the citation resolves, otherwise `unsupported`. It can never become `verified`. |
| `behaviour` (asserts run-time behaviour) | `unsupported` with no executed check, or if it names a test that no cited check ran. `needs_link_review` if it cites a check but names no test: the suite passing does not show this claim is exercised, so a human must confirm the link. `verified` if every named test ran with the outcome the check says supports the claim. `contradicted` if a named test had the opposite outcome. A check that did not run counts for nothing. |

Each check says what outcome would support a claim (`expected`, default `passed`; the AI's new tests run on base source are expected to `fail`) and its `role`: a `gate` must pass, a `probe` is run to learn something, and a surprise is reported through the claims it contradicts.

## Shared decision contract

[`engine/decision.py`](../engine/decision.py) is the authoritative validator for human decisions. [`engine/decision.js`](../engine/decision.js) implements the same rules for draft feedback in the walkthrough. Both are exercised by the same valid and invalid cases in [`engine/decision-contract-cases.json`](../engine/decision-contract-cases.json), including contradictory acceptance positions, missing acknowledgements, unknown IDs, duplicates, placeholders and reason-only changes or escalation.

```bash
python3 -m unittest engine/test_decision.py
node --test engine/test_decision.js
```

The browser can only enable copying when a draft passes its local copy of the contract; it never posts, stores or signs. `engine/pr.py` revalidates the actual human comment in Python before persisting anything.

**Routing is rules, not a score.** The tier is the highest tier any rule asks for, and each rule that fired is listed with what was observed:

| Rule | Tier |
| --- | --- |
| Requirement is an open product decision | full read |
| A gate check that should pass failed | full read |
| More than 400 changed source lines (tests, docs and generated files excluded; triage only) | full read |
| Requirement contested or weak | standard |
| A claim is contradicted or unsupported | standard |
| A claim cites a check but names no test (`needs_link_review`) | standard |
| The change goes beyond the requirement | standard |
| The AI refused to decide something | standard |
| None of the above | light |

Skipped, unavailable and not-run checks are listed in the reasons but do not change the tier by themselves.

**Triage on the four samples** (pre-AI, from requirement quality and diff shape only): #2283 light, #2234 standard, #2129 full read (contested, 458 source lines), #2297 full read (open decision; 222 generated files can be machine-checked instead of read). The deep receipt for #2283 then raises it from light to standard because of the contradicted claim and the scope change, which shows the second pass catching what the first could not.

## Named tests (the claim-to-check link)

A check carries `tests`, the per-test results parsed from the raw `.trx` log by [`engine/trx.py`](../engine/trx.py) (`python3 engine/trx.py attach RECEIPT CHK1=evidence/trx/CHK1.trx ...`, which refuses if the counts disagree with the check). A claim carries `testRefs`. [`evidence/run-trx.sh`](../evidence/run-trx.sh) regenerates the four #2283 runs with per-test output.

## Model step

[`engine/propose.py`](../engine/propose.py) sends the requirement, the executed checks and a line-numbered diff to DeepSeek V4.1 Flash (JSON mode, temperature 0, plain `urllib`, key from `.env`). The model proposes claims, refusals, out-of-requirement items and unknowns. It never sets a status. The script strips check references that are invented, not run, or attached to a `code_fact`, then `finalize` computes everything else.

```bash
python3 engine/propose.py examples/receipt-2283.example.json --inject-bad   # writes examples/receipt-2283.model.json
python3 engine/review.py finalize examples/receipt-2283.model.json
```

`--inject-bad` appends five deliberately wrong claims: a fake line, no check, a failing named test, an invented test name, and a true claim that cites only the whole suite. The engine marked them `unsupported`, `unsupported`, `contradicted`, `unsupported` and `needs_link_review`. The raw model response is kept in `evidence/propose-2283.raw.json`.

## Limits of this draft

- The example's claims, refusals and out-of-requirement items are **hand-written**, marked `provenance.claimsSource: "fixture"`. The checks are real runs. Claim statuses and routing are computed by the engine and agree with what we first wrote by hand.
- The engine checks that a citation points at real lines in that revision. It does not check that the lines support the claim's text. That is why a `code_fact` can only reach `source_only`.
- Which test backs a claim is still the model's say-so. The engine checks that the named test exists and ran, not that it tests what the claim says. Whether a named test is relevant is a human judgement, so `verified` means "a named test had the outcome the check needs", not "the claim is true".
- Mechanical claim statuses are evidence-linkage classifications, not semantic verdicts. A `contradicted` or `unsupported` claim is not thereby a hallucination, and no trust or hallucination score exists. The live R2283 receipt's CLM7 and CLM8 illustrate this: a mixed probe expectation and an inexact test-name link, respectively.
- Acceptance completeness is defined by the shared decision contract, not by the number of prose answers. A human can still write a thin reason; the validator does not judge its quality.
- `expected` belongs to the check, not the claim. A model claim about a test's content that also cited the CHK4 probe was marked `contradicted` because that test fails there. The test did detect a behaviour difference, but the claim was not about that. Per-claim expectations are not modelled.
- It does not run checks. Check results are recorded by hand from `evidence/` for now.
- The thresholds (400 lines, the rule table) are untuned guesses and are meant to be argued about.
- The walkthrough is a pinned snapshot, not live PR state. Source and diffs are optional: a missing or stale code snapshot hides only that panel and never blocks the decision path. Final freshness is checked by `engine/pr.py decide`.
- Draft status: field names may change once a model produces the claims.
