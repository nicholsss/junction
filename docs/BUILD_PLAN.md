# Build plan

Target: a complete reference demonstration in 4–6 hours, assuming model access and sample tooling are available.

## Candidate ideas

1. **Review Receipt (recommended):** requirement-linked review evidence, explicit unknowns and human sign-off. Best coverage of the brief within the time limit.
2. **Requirement Coverage Map:** map acceptance criteria to changed code and tests. Useful as the receipt's main visual, but code references alone do not prove correctness.
3. **Reviewer Cross-Examination:** a second model challenges review claims and asks for evidence. Optional extension; agreement between models is not verification.

## Milestones

- Hour 1: inspect the supplied sample repository, choose a small change, document its requirement and establish which checks can run.
- Hour 2: define the receipt schema and build the requirement/change/evidence interface using clearly labelled fixture data.
- Hour 3: integrate model-generated claims with validated file references. Handle missing evidence and model failures explicitly.
- Hour 4: attach actual check outputs, implement human decision recording and complete one end-to-end walkthrough.
- Hour 5: evaluate a supported claim, an unsupported claim and a failed/skipped check. Check revision binding and source links.
- Hour 6: polish the demo, write the concept card and lessons, record results and prepare submission materials.

## Acceptance criteria

- A receipt identifies the requirement and exact code revision.
- Claims link to real locations in the selected revision.
- AI-generated prose cannot manufacture a successful check result.
- Skipped, failed and unavailable checks are visibly different.
- A human can see what needs attention and why.
- A human decision records the owner, reason and residual risk.
- The walkthrough and README let another person reproduce the demonstration.

## Evaluation

Compare a manual walkthrough with receipt-assisted review on the selected example. Record time, correct findings, unsupported claims and unresolved questions. Report sample size and limitations; do not extrapolate a single example into a production trust claim.

## Scope limits

Defer general GitHub integration, arbitrary repository uploads, automatic merging, multi-user authentication, model training and production deployment infrastructure until the core demonstration works.
