# Review Receipt

Our HackJunction 2026 submission for Tieto's **Earned Trust in AI Code** challenge.

We built Review Receipt: the evidence engine, receipt schema, model integration, PR decision flow, and walkthrough. The supplied MessagePack code is the material we use to demonstrate and evaluate that system.

**Status:** real [demo PRs](docs/PULL_REQUESTS.md) have receipt comments and pending `review-receipt` statuses. R2283 uses a fresh model receipt without injected claims; the other three are triage only. The [published walkthrough](https://nicholsss.github.io/junction/) drafts comments for the human to post in GitHub. `engine/pr.py` applies a named human's actual decision to the exact head SHA. No human has signed. Production event automation, branch protection and a general check runner are **not built**. See [PR flow and operator commands](docs/PR_FLOW.md), [demo script](docs/DEMO_SCRIPT.md) and [concept card](docs/CONCEPT_CARD.md).

## The problem

AI can write changes faster than engineers can review them. A confident review summary does not establish that a change satisfies its requirement. Engineers need checkable evidence, explicit unknowns and clear ownership of the decision.

## Our concept

Turn one agent-written code change and its requirement into a review receipt that a named engineer can inspect and sign.

The receipt connects claims to code and actual checks, shows what remains unverified, and directs human attention to the parts that need it. AI provides advice; the human owns the decision.

Example: an AI reviewer claims a regression is covered by tests. The receipt links the relevant test and records whether it actually ran. If it did not run, that claim stays unverified.

## Six-hour demo scope

1. Select one prepared agent-written change and its requirement.
2. Show the intent, changed files and a concise behaviour summary.
3. Generate review claims linked to file/line evidence and requirement IDs.
4. Record actual validation results separately from AI interpretations.
5. Show verified findings, unresolved concerns and checks that were not performed.
6. Ask a named human to accept the listed risks, request changes or escalate, recording their reason and any required structured positions.

Start with one supplied repository and one change. Support a second contrasting example only after the complete flow works.

## Principles

- Evidence before confidence: no unexplained numerical trust scores.
- Distinguish a model claim, a source reference and an executed check.
- Every check records its scope, status and limitations.
- Missing evidence stays visible; failed or skipped checks cannot become passes.
- Identify the exact base and head commits reviewed; a changed revision invalidates the receipt.
- Route human attention by demonstrated risk and uncertainty.
- A named human makes the final decision. No automatic approval or merge.
- Use synthetic or cleared sample data only.

## Proposed receipt

A draft machine-readable form exists: [schema](schema/receipt.schema.json), [validator](schema/validate.py) and a [worked example for R2283](examples/receipt-2283.example.json). See [the schema notes](docs/RECEIPT_SCHEMA.md).

| Section | Contents |
| --- | --- |
| Identity | Requirement ID, repository, base/head commits, reviewer |
| Intent | Expected behaviour and acceptance criteria |
| Change | Affected files and behaviour |
| Evidence | Claim, source location, validation result and limitations |
| Attention | Findings and questions requiring human review |
| Unknowns | Unchecked paths, missing tests and assumptions |
| Decision | Human owner, outcome, reason, structured positions and acknowledged unknowns |

## Challenge deliverables

- Concept card: recommendation, principles, trade-offs and limits.
- Reference implementation and live walkthrough of one agent-written change.
- Traceability from requirements to evidence.
- Explicit examples of what AI found and refused to decide.
- Short decisions/lessons log and demo presentation or video.
- Measurement plan: review time, finding validity, human routing, and downstream reverts/incidents. A hackathon demo cannot establish long-term reliability.

## Working technical direction

Python 3 standard library plus `jsonschema`; static HTML/JSON/Markdown for any UI.

## Model access

The model that proposes claims and refusals is DeepSeek V4.1 Flash (`deepseek-4-1-flash-1017`) through Verda's OpenAI-compatible endpoint. We call it with plain HTTPS from the standard library, with no AI SDK, because we need one endpoint and JSON output, and the engine validates the result anyway. The model never sets a claim's status; the engine computes it.

Put the key in `.env` (git-ignored; see `.env.example` for the other variables):

```
VERDA_API_KEY=your-key
```

## Demo environment and attribution

Our [four demo PRs](docs/PULL_REQUESTS.md), [local requirement snapshots](docs/DEMO_REQUIREMENTS.md), receipt comments, commit statuses and [walkthrough](https://nicholsss.github.io/junction/) belong to our submission environment. Local IDs such as `R2283` identify demonstration cases.

The sample code and prepared AI changes were supplied for the challenge through [the MessagePack sample repository](https://github.com/te-industry-tech-office/junction26-messagepack-csharp).

The sample repository remains technically a GitHub fork to preserve the existing PRs and comments.

See [the concept card](docs/CONCEPT_CARD.md), [PR flow](docs/PR_FLOW.md), [demo script](docs/DEMO_SCRIPT.md) and [decision log](docs/DECISIONS.md).
