# Tieto resources inspected

Inspected on 2026-11-14 through GitHub issue bodies, branch listings and Git patches. Tests have not been executed. The local shell has no `dotnet` executable; the sample pins .NET SDK 8.0.402 with patch roll-forward.

## Official inputs

- [Challenge](https://hackjunction.app/participate/45/challenges/351)
- [Sample repository](https://github.com/te-industry-tech-office/junction26-messagepack-csharp)

The brief asks teams to make their own copy before working on the sample. A read-only inspection clone currently lives at `/tmp/junction-tieto-samples`; make a durable project-owned copy before modifying or executing it. The source repository's default branch is a Dependabot branch, so explicitly select a challenge branch rather than trusting the default checkout.

## Available changes

| Issue | Requirement | Branch head inspected | Patch size |
| --- | --- | --- | --- |
| [2234](https://github.com/MessagePack-CSharp/MessagePack-CSharp/issues/2234) | Analyzer must still work when SuppressSourceGeneration is true | `9007cee1163c4a274fd60c3cc20c21ae63622786` | 4 files, +262 / -4 |
| [2283](https://github.com/MessagePack-CSharp/MessagePack-CSharp/issues/2283) | Avoid generator/analyzer crashes for closed generic structs from referenced assemblies | `9df83c38409c8bfad0517aebffe48211eda4a5b4` | 4 files, +225 / -3 |
| [2129](https://github.com/MessagePack-CSharp/MessagePack-CSharp/issues/2129) | Generate a formatter for an external type without adding MessagePack to the defining project | `083afd994c1c9a994cb2cd5aa0b6ad805a621457` | 28 files, +1034 / -9 |
| [2297](https://github.com/MessagePack-CSharp/MessagePack-CSharp/issues/2297) | Decorate generated code with ExcludeFromCodeCoverage | `a0aa5ab2de7f5a669d97e37184a89034c1de82b6` | 237 files, +1383 / -9 |

Sizes describe the tip commit against its parent, not a comparison against the repository's default branch.

> Update 2026-11-14: the lead demonstration is now #2283, not #2234. Its requirement is far clearer and an upstream human PR (#2305) gives a comparison. See [requirements](REQUIREMENTS.md) and [review findings](REVIEW_FINDINGS.md). The section below is kept as the earlier analysis of #2234, now the second demonstration. The sample is cloned into the git-ignored `sample/` folder, so the `/tmp` clone mentioned above is no longer needed.

## Earlier recommendation: #2234

The issue report is short: analyzer behaviour regressed after version 3.1.0 when source generation is suppressed. The patch adds documentation, analyzer tests and runtime execution tests, and changes duplicate/mixed-key handling in TypeCollector.

Useful review questions:

- Does the original failure reproduce on the parent revision?
- Do the new tests pass at the candidate revision?
- Do contract diagnostics still appear while generation-only diagnostics stay suppressed?
- Does the runtime fallback work without generating a formatter?
- Why are duplicate/mixed-key changes necessary, and can they affect ordinary generated types?

The issue itself does not specify every diagnostic's expected behaviour. Treat the patch's expanded documentation as implementation claims to validate, rather than independent requirements from the reporter.

## Second demonstration: #2283

This issue has a detailed two-project reproduction and a useful trigger matrix: generic versus non-generic, struct versus class, referenced assembly versus local source. The patch changes source-location handling and diagnostic reporting. Review both crash prevention and the possibility of unintentionally dropping diagnostics. This is a strong follow-up once one receipt works end to end.

## Deferred

#2129 expands API and generator behaviour substantially. #2297 is conceptually simple but changes many generated snapshots. Both are useful future scaling examples; neither is the fastest first walkthrough.

## Next steps

1. Create a durable copy of the selected sample with its license intact.
2. Pin base to the selected head's parent and record both full SHAs.
3. Inspect project/test instructions before setting up .NET.
4. Capture actual baseline and candidate check output; until then display validation as not run.
5. Build the first receipt around the requirement, precise evidence and remaining uncertainty.
