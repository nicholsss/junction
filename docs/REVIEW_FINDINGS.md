# Review findings so far

Status: diff reading plus a first set of test runs (2026-11-14, .NET SDK 8.0.402, `MessagePack.SourceGenerator.Tests`, `net8.0`). Items marked "Read; not run" are still unverified observations. Source: `git show` on the sample branches, upstream PR #2305 and the test runs below.

## Test results

Reproduce with `evidence/run-checks.sh` (needs the SDK pinned in `sample/global.json`). Raw logs are written to `evidence/*.log`, which is git-ignored.

| Run | Result |
| --- | --- |
| Parent `32258fdb`, existing tests | 167 passed, 0 failed |
| #2283 candidate `9df83c38`, all tests | 170 passed, 0 failed (3 new) |
| #2283 new tests on parent source | 3 of 3 fail, with the `IndexOutOfRangeException` from the issue |
| #2234 candidate `9007cee1`, all tests | 175 passed, 0 failed (8 new) |
| #2234 new tests on parent source | 4 of 8 fail |
| #2234 `ExecutionTests` project | Does not compile, on the candidate **and** on the untouched parent |

What this supports:

- **#2283:** the new tests reproduce the reported crash on the parent and pass with the patch. Fail-then-pass is demonstrated. The diagnostic-dropping filter has not been tested.
- **#2234:** the four failing tests are the duplicate and mixed key cases, with `ArgumentException` ("An item with the same key has already been added") and `InvalidOperationException` ("Nullable object must have a value") from the analyzer. One of the four uses a plain `[MessagePackObject]` with no suppression, so the crash is not specific to suppressed types. The other four new tests already pass on the parent and show nothing about the reported bug. The "worked in 3.1.0, broke in 3.1.1" symptom itself is not shown to be what was fixed.
- **Unavailable check:** the `ExecutionTests` build failure is an existing setup problem, not caused by the patch, so the runtime test for suppressed types could not run. Report it as unavailable, not passed or failed.

## #2283: AI patch `9df83c38`

| Observation | Kind | Status |
| --- | --- | --- |
| Replaces unsafe `DeclaringSyntaxReferences[0]` at the two live crash sites in `TypeCollector.cs` (`BothStringAndIntKeyAreNull`, `MemberNeedsKey`) | Source reference | Read; not run |
| The third `[0]` site in the file is commented-out code, so it needs no change | Source reference | Read |
| Adds `ReportIfLocatedInCompilation`, which drops every diagnostic whose location is not in the compilation being analyzed | Scope concern | Not in the issue. **Tested, see "Behaviour difference" below**: it drops MsgPack004 for unkeyed members of a referenced type |
| Adds README and `MsgPack004.md` text claiming problems in referenced types are reported by the defining assembly | Unverified claim | Holds only if that assembly runs the analyzer. Not checked |
| New tests compile the library to real IL, so the referenced type is a genuine metadata symbol | Source reference | Read; matches how PR #2305 says the bug must be reproduced |
| Reference fix PR #2305 only swaps `[0]` for `FirstOrDefault()` (+5 / -3 in source), so the diagnostic is still reported with no location | Comparison | Read |

**Behaviour difference (tested):** run with `evidence/run-minimal-fix-check.sh`. We applied a minimal fix to the parent (`FirstOrDefault()` instead of `[0]` at the two live crash sites, the same idea as PR #2305 but applied by hand, because the PR does not apply cleanly to the parent) and ran the AI candidate's tests against it. 169 of 170 pass. The one failure is `ClosedGenericStruct_FromMetadataReference_UnkeyedMember`: with the minimal fix the analyzer reports **two MsgPack004 diagnostics** (reported as errors in the test harness) for an unkeyed member of a referenced generic struct. The AI patch reports none, and its own test asserts zero diagnostics.

So the AI patch makes a policy choice the issue does not ask for. There is a case for it: the consumer cannot fix a diagnostic in code they don't own. There is a case against it: a real problem in a dependency is silenced and the README now says someone else reports it, which holds only if the defining assembly runs the analyzer. The issue's stated expectation (clean build for a correct `Item<T>`) is met by both versions.

**Decision for the human owner:** accept the diagnostic-dropping policy (and its docs claim), or ask for the smaller change that only stops the crash?

## #2234: AI patch `9007cee1`

| Observation | Kind | Status |
| --- | --- | --- |
| Skips adding a member when its int or string key already exists, and `continue`s on mixed key kinds, in both member loops of `TypeCollector.cs` | Source reference | Read; not run |
| Adds about 230 lines of tests in two files | Source reference | Read |
| Adds a README section describing which diagnostics apply to suppressed types | Unverified claim | Not requested by the issue |

**Tested:** 4 of the 8 new tests fail on the parent because the analyzer throws on duplicate or mixed keys, and all pass with the patch. The other 4 pass on the parent. The crash also affects ordinary (non-suppressed) types, so the patch fixes a broader bug than the issue title. Whether this is the regression the reporter saw is still unproven.

**Decision for the human owner:** the requirement does not say how duplicate or mixed keys should behave.

## #2129 and #2297: triage notes

- **#2297**: 237 files, mostly regenerated snapshots. The template change is small. The maintainer has not decided the feature is wanted, so the AI should route this to a human decision, not review it as a mechanical change.
- **#2129**: adds a `GeneratedMessagePackFormatter` attribute and analyzers MsgPack019 to MsgPack022 in 28 files. Design alignment with the maintainer's surrogate-type suggestion is **unchecked**.

## Checks still to run

1. For #2283, other diagnostic kinds that `ReportIfLocatedInCompilation` may drop beyond MsgPack004 are untested. Only the unkeyed-member case was checked.
2. Compare the #2283 patch with PR #2305 itself, on the repro from the issue (two projects, `dotnet build`). The hand-applied minimal fix above is an approximation.
3. Find out why `ExecutionTests` does not compile on the parent, so the #2234 runtime test can run. Time-box this.
4. Run the check for #2129 and #2297 only if time allows. Their requirement questions are about maintainer intent, not test results.

Done: SDK installed in `~/.dotnet` (outside the repo), parent baseline, candidate runs, and fail-then-pass runs for #2283 and #2234.
