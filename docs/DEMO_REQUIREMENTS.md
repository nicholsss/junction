# Review Receipt demo requirements

These are local requirement snapshots for our HackJunction 2026 submission. The sample code is demonstration material; these cases do not request action in an external project. See the README for attribution. Historical IDs in receipt JSON preserve the recorded evidence; public demo labels use the R prefix.

## R2283

Generator and analyzer crash on a closed generic struct from a referenced assembly

Requirement quality: `strong`. Repro, expected behaviour and trigger matrix in the issue.

Acceptance criteria captured for this demo (derived criteria are our interpretation):

- **AC1 (stated)**: A [MessagePackObject] type with a member of a closed generic value type from a referenced assembly builds cleanly and gets a generated resolver.
- **AC2 (derived)**: The other trigger-matrix shapes (non-generic struct, generic or non-generic class, non-generic record struct) keep working as before.
- **AC3 (derived)**: No CS8785 or AD0001 warning is produced for these shapes.

[Open our demo PR](https://github.com/nicholsss/junction26-messagepack-csharp/pull/1)

## R2234

Analyzer does not work with SuppressSourceGeneration

Requirement quality: `weak`. One-sentence report, no expected behaviour.

Triage only. No deep receipt or acceptance decision has been produced.

[Open our demo PR](https://github.com/nicholsss/junction26-messagepack-csharp/pull/2)

## R2129

Generate a formatter for a type in a referenced assembly

Requirement quality: `contested`. Maintainer proposed surrogate types; design alignment unchecked.

Triage only. No deep receipt or acceptance decision has been produced.

[Open our demo PR](https://github.com/nicholsss/junction26-messagepack-csharp/pull/3)

## R2297

ExcludeFromCodeCoverage on generated code

Requirement quality: `open_decision`. Maintainer has not said whether the feature is wanted.

Triage only. No deep receipt or acceptance decision has been produced.

[Open our demo PR](https://github.com/nicholsss/junction26-messagepack-csharp/pull/4)

