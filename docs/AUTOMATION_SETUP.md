# Activate the judge demo

The repository contains the implementation. Until these settings are applied,
GitHub Pages remains a published snapshot and decisions still need the existing
manual operator flow. No human decision or new .NET evidence was created by this work.

## One-time setup

1. Create a GitHub App named `junction-review-receipt` (or change `automationLogin`
   and `receiptPublishers` in `docs/reviewers.json` to its actual bot login).
   Disable webhook delivery: Actions supplies events. Install it on only
   `nicholsss/junction` and `nicholsss/junction26-messagepack-csharp`.
2. Grant repository permissions: **Actions: read/write**, **Contents: read/write**,
   **Issues: read/write**, **Commit statuses: read/write**, and
   **Pull requests: read**. No organization or account permissions are needed.
   Generate its private key; keep it out of the repository.
3. In both repositories, set Actions variable `REVIEW_APP_ID` to its App ID and
   Actions secret `REVIEW_APP_PRIVATE_KEY` to the private key.
4. The committed policy is `"public_demo"`: any authenticated GitHub `User` can
   record an outcome on registered demo PR #1. Reviewers do not need advance registration.
   The latest valid human decision wins. This is labelled as public demo participation
   on the page; it never merges code. For restricted use, change `policy` to `"allowlist"`
   and fill `reviewers`, e.g. `{"judge-login": "Judge display name"}`. Display names
   are configured team labels, not independent identity verification.
5. Push the implementation to `junction/main`. The workflow code always checks out
   trusted `main`; it never checks out or runs PR-head code with App credentials.
6. Copy `.github/demo-pr-repo/review-events.yml` into
   `.github/workflows/review-events.yml` on the **default branch** of the PR repository.
   Its current default branch is `dependabot/nuget/develop/PolySharp-1.15.0`;
   check before installation. A workflow only on a review branch will not receive
   PR-comment events. The bridge handles registered demo PR #1 only.
7. In `junction` Settings → Pages, choose **GitHub Actions** as the publishing source.
   Allow `main` to deploy to the `github-pages` environment. Run the
   **Publish review workspace** workflow once. If Actions is restricted, allow the
   official `actions/*` used here. Source pushes by the App trigger publication;
   the processing workflow also explicitly dispatches publication for recovery.
8. Repost the current receipt using the documented `engine/pr.py post 1` operator
   command if its published digest no longer matches the checked-in receipt.
   `nicholsss` is explicitly trusted as the historical receipt publisher. Subsequent
   automation replies are authored by the App; they never impersonate a reviewer.

## How it runs

- A new `/receipt ...` PR comment wakes the bridge, which forwards repository, PR
  and comment identifiers. The worker fetches authoritative comment data from GitHub.
- Review processing is serialized because the demo writes one receipt and registry.
  GitHub can coalesce pending workflow runs; each worker sweeps new command comments
  in ID order with a persisted watermark, so a coalesced event does not lose a decision.
- In public-demo mode, any non-bot GitHub user can decide; allowlist mode restricts this. Commands must match the trusted
  receipt digest, exact base/head, structured acceptance rules, and registered PR.
- Edited comments are rejected; corrections require a new comment. Replays and older
  commands cannot overwrite newer recorded decisions. Invalid or unauthorized input
  does not reset a valid status. Posting order resolves conflicting valid decisions:
  the latest valid command wins, with every source comment retained in GitHub.
- The worker stores the receipt, current-head state and rendered HTML, then pushes
  them to `junction/main`. Status mappings remain success/failure/pending.
- PR `synchronize` events mark the new head pending and publish a stale warning.
  They **do not fabricate refreshed tests or claims**. Fresh evidence still needs
  the operator; generating evidence for arbitrary new commits is a separate feature.
- The page displays the last processing timestamp and source decision, disables
  stale drafting, and links to GitHub. It does not live-poll or show an unobserved
  "processing" state. Comments and workflow runs are the live processing surfaces.

## Judge acceptance test

Use a real second account. No registration is required in public-demo mode. Never post prepared human answers for it.

1. Review the page without opening code. Explain the intended fix and the two risks.
2. Post a reason-only request for changes. Confirm the App reply, failed
   `review-receipt` status, source-comment link and updated page.
3. Post a corrected acceptance with every position and unknown acknowledgement.
   Confirm success. Incomplete acceptance must explain what is missing and leave
   the recorded valid decision intact.
4. Escalate with a reason. Confirm pending owner judgement, not success.
5. Confirm a previously unknown human account can participate. Bot accounts and
   edited commands must be rejected. In allowlist mode, unknown accounts are rejected.
6. Deliver the same event twice and post two commands quickly: no duplicate decision
   or lost newer command. Re-running **Process demo review event** is a recovery path.
7. In an isolated demo revision, change the PR head. Confirm pending, a stale page
   warning and rejection of the old SHA. Restore/rebuild evidence before reuse.
8. If publication fails, inspect the run and rerun **Publish review workspace**.
   The persisted receipt and GitHub comment identify the decision independently.

## Remaining scope

No automatic merging; requiring the `review-receipt` status in branch protection
is an optional repository setting for a merge-gate demonstration. PRs 2–4 remain
triage-only. A general check runner and automatic model/evidence refresh are not built.
GitHub status, comment, git push and Pages deployment are separate API operations;
there is no atomic transaction across them. Failed runs need rerunning, and the
existing final-head check cannot eliminate GitHub's read/status race.

## Local verification

```sh
python3 -m pip install -r engine/requirements.txt
python3 -m unittest discover -s engine -p 'test_*.py'
node --test engine/test_decision.js
python3 schema/validate.py examples/receipt-2283.live.json
python3 engine/render.py
npm install
npx playwright install chromium
npm run test:browser
```
