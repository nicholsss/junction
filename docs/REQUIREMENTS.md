# Requirements

The requirement ID for each sample change is its upstream GitHub issue number. Tieto's brief promises a separate requirements set and code standards, but none was linked on the challenge page when checked on 2026-11-14. If one is supplied, map it onto these IDs rather than replacing them.

Source: [MessagePack-CSharp issues](https://github.com/MessagePack-CSharp/MessagePack-CSharp/issues). Issue text was read on 2026-11-14. Issue text is the only requirement; anything a patch adds beyond it is a claim to review, not a requirement.

Common base for the two small samples: `32258fdb` ("Bump PolySharp from 1.14.1 to 1.15.0"). The patches are commits on branches in the [Tieto sample repo](https://github.com/te-industry-tech-office/junction26-messagepack-csharp).

## #2283: crash on closed generic struct from a referenced assembly (lead demo)

Issue: [#2283](https://github.com/MessagePack-CSharp/MessagePack-CSharp/issues/2283). Candidate: branch `ju26-issue-2283`, head `9df83c38409c8bfad0517aebffe48211eda4a5b4`.

**Requirement quality: strong.** Has a two-project repro, expected and actual behaviour, a trigger matrix, a stack trace and a suspected cause.

**Stated expected behaviour:** a clean build, with a generated resolver in the consuming project.

**Trigger matrix (type `Item` in a referenced assembly, used as a member of a `[MessagePackObject]`):**

| `Item` declared as | Reported result |
| --- | --- |
| `record struct Item<T>` | crash |
| `struct Item<T>` | crash |
| `struct Item` | ok |
| `record struct Item` | ok |
| `class Item<T>` | ok |
| `record class Item<T>` | ok |

**Acceptance checks implied by the issue:**

1. The two crash rows build cleanly and produce a generated resolver.
2. The four "ok" rows are unchanged.
3. No `CS8785` or `AD0001` warning is produced for these shapes.

**Not stated:** whether diagnostics about members of referenced types must still be reported. Any behaviour change there is outside the requirement.

**Reference fix for comparison:** upstream PR [#2305](https://github.com/MessagePack-CSharp/MessagePack-CSharp/pull/2305), open and by a human contributor.

## #2234: analyzer does not work with SuppressSourceGeneration (second demo)

Issue: [#2234](https://github.com/MessagePack-CSharp/MessagePack-CSharp/issues/2234). Candidate: branch `ju26-issue-2234`, head `9007cee1163c4a274fd60c3cc20c21ae63622786`.

**Requirement quality: weak.** The whole report: the analyzer does not work if `SuppressSourceGeneration = true`; it started in 3.1.1 and still worked in 3.1.0. No repro, no expected behaviour, no comments.

**Acceptance checks that can be derived (derived by us, not stated):**

1. The analyzer does not crash on a `[MessagePackObject(SuppressSourceGeneration = true)]` type.
2. Contract diagnostics still appear for such a type.

**Not stated, so any claim about it needs human judgement:** which diagnostics must stay suppressed, how duplicate or mixed keys should behave, and whether the README text the patch adds is wanted.

## #2129: generate a formatter for a type in a referenced assembly (triage only)

Issue: [#2129](https://github.com/MessagePack-CSharp/MessagePack-CSharp/issues/2129). Candidate: branch `ju26-issue-2129`, head `083afd994c1c9a994cb2cd5aa0b6ad805a621457`.

**Requirement quality: contested.** A feature request with six comments. The maintainer rejected a key-dictionary approach and suggested surrogate types. Open question for review: does the 28-file patch follow that direction? Not yet checked.

## #2297: ExcludeFromCodeCoverage on generated code (triage only)

Issue: [#2297](https://github.com/MessagePack-CSharp/MessagePack-CSharp/issues/2297). Candidate: branch `ju26-issue-2297`, head `a0aa5ab2de7f5a669d97e37184a89034c1de82b6`.

**Requirement quality: open product decision.** A contributor offered a PR and asked the maintainer whether to accept it or point users to coverage-tool configuration. No answer was posted. Whether the feature is wanted is a human decision the AI must not make.
