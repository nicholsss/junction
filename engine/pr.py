#!/usr/bin/env python3
"""Publish receipts and apply explicit human PR comments. No automatic approval.

post PR [--repo OWNER/REPO]
decide PR --human LOGIN --name 'Full name' [--allow-same-account]
Network access is confined to GitHub methods; rendering and decisions are pure.
"""
import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import decision
import review

MARKER = '<!-- review-receipt -->'
REPO = 'nicholsss/junction26-messagepack-csharp'
PAGE = 'https://nicholsss.github.io/junction/'
REGISTRY = ROOT / 'docs/pull-requests.json'
LIVE = ROOT / 'examples/receipt-2283.live.json'


def md(value):
    """Escape untrusted model text for a Markdown table/comment, no raw HTML."""
    import html
    return html.escape(str(value)).replace('|', '&#124;').replace('\n', '<br>').replace('`', '&#96;')


def local_requirement_id(value):
    """Use local requirement labels rather than cross-project issue references."""
    return 'R' + value.lstrip('#') if value.startswith('#') else value


def fingerprint(receipt):
    data = {k: v for k, v in receipt.items() if k != 'decision'}
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


CHECK_LABEL = {'passed': 'Passed', 'failed': 'Failed', 'not_run': 'Not run',
               'skipped': 'Skipped', 'unavailable': 'Unavailable'}
DECISION_LABEL = {'pending': 'Pending — no named human decision',
                  'accepted': 'Accepted by the named human',
                  'changes_requested': 'Changes requested by the named human',
                  'escalated': 'Escalated — pending owner judgement'}
GITHUB_STATUS = {'accepted': 'success', 'changes_requested': 'failure', 'escalated': 'pending'}


def status_for(decision_data):
    return GITHUB_STATUS.get(decision_data['status'], 'pending')


def refusal_position_lines(refusal):
    return '; '.join(f'{p["id"]} — {p["label"]} ({p["effect"].replace("_", " ")})'
                     for p in refusal.get('positions', []))


def render_comment(receipt, page=PAGE):
    s, routing, d = receipt['subject'], receipt['routing'], receipt['decision']
    lines = [MARKER, f'<!-- receipt-head:{s["headSha"]} receipt-digest:{fingerprint(receipt)} -->',
             f'## Review Receipt · {md(local_requirement_id(receipt["requirement"]["id"]))}',
             'Our HackJunction 2026 project · local demo environment. Supplied code is demo material.',
             f'**Review depth: {md(routing["tier"].replace("_", " ").upper())}**',
             f'Head: `{s["headSha"]}` · Base: `{s["baseSha"]}`',
             f'Decision: **{md(DECISION_LABEL[d["status"]])}**']
    if d.get('owner'):
        lines.append(f'Owner: {md(d["owner"])} · Signed at: {md(d.get("signedAt", ""))}')
    if d.get('reason'):
        lines.append(f'Human reason: {md(d["reason"])}')

    if receipt.get('decisionBrief'):
        lines += ['', '### Decision brief']
        for statement in receipt['decisionBrief']:
            refs = ', '.join(statement['evidenceRefs'])
            lines.append(f'- **[{md(statement["provenance"])}]** {md(statement["text"])}'
                         + (f' ({md(refs)})' if refs else ''))

    lines += ['', '### Material risks and unknowns']
    if receipt.get('refusals'):
        lines.append('**Questions the AI refused to decide, with the recorded positions:**')
        for x in receipt['refusals']:
            lines.append(f'- **{x["id"]}: {md(x["question"])}** — {md(x["whyAiRefused"])}')
            if x.get('positions'):
                lines.append(f'  - Positions: {md(refusal_position_lines(x))}')
    if receipt.get('outOfRequirement'):
        lines.append('**Outside the requirement:**')
        for x in receipt['outOfRequirement']:
            lines.append(f'- **{x["id"]}**: {md(x["description"])}')
            lines.append('  - Positions: `accept_scope`, `change_required`, `needs_owner`')
    if receipt.get('unknowns'):
        lines.append('**Residual unknowns, acknowledged by ID to accept:**')
        lines += [f'- **{x["id"]}**: {md(x["text"])}' for x in receipt['unknowns']]
    if not (receipt.get('refusals') or receipt.get('outOfRequirement') or receipt.get('unknowns')):
        lines.append('None recorded.')

    lines += ['', '### Claims · evidence-linkage classifications',
              'These are mechanical evidence links, not a trust or hallucination score. '
              '**Test-backed** means the named tests ran with the outcomes those links expect; it does not prove the claim or test relevance. '
              '**Contradicted** means a linked outcome conflicted with its configured expectation. '
              '**Unsupported** means cited executed evidence is absent or insufficient, so the claim is unproven rather than proven false. '
              '**Source only** means the cited range resolves; runtime behaviour is not established.',
              '', '| ID | Claim | Classification and exact reason | Cited source |',
              '| --- | --- | --- | --- |']
    for c in receipt['claims']:
        ci = c['citation']
        url = f'https://github.com/{s["repository"]}/blob/{ci["sha"]}/{ci["file"]}#L{ci["startLine"]}-L{ci["endLine"]}'
        lines.append(f'| {c["id"]} | {md(c["text"])} | **{md(c["status"])}**: {md(c["statusReason"])} '
                     f'| [{md(ci["file"])}:{ci["startLine"]}]({url}) at `{md(ci["sha"][:8])}` |')
    if not receipt['claims']:
        lines.append('| — | No claims recorded. | — | — |')

    lines += ['', '### Checks that ran, and what they do not cover']
    for c in receipt['checks']:
        lines.append(f'- **{c["id"]}: {md(CHECK_LABEL.get(c["status"], c["status"]))}** — {md(c["description"])}')
        lines.append(f'  - Revision: {md(c["revision"])} · Scope: {md(c["scope"])}')
        lines.append(f'  - Limits: {md(c["limitations"])}')
        if c.get('failures'):
            lines.append('  - Failures: ' + md('; '.join(c['failures'])))

    lines += ['', '### Rules that fired']
    lines += [f'- **{md(x["rule"])}**: {md(x["observed"])}' for x in routing['reasons']]
    if routing.get('humanFocus'):
        lines += ['', '### Optional source focus']
        lines += [f'- `{md(x["file"])}:{md(x.get("lines", ""))}` — {md(x["why"])}' for x in routing['humanFocus']]
        lines.append('Source is optional corroboration. The decision brief, classifications, checks and unknowns above are the no-code path.')

    lines += ['', '### Your decision', '',
              'A named human must read the evidence and post their own comment. Copy this template and replace every bracketed field:',
              '```text',
              '/receipt accept [your reason, including residual risks]',
              f'Head: {s["headSha"]}']
    for x in receipt['refusals']:
        choices = ' | '.join(p['id'] for p in x.get('positions', [])) or 'no positions recorded'
        lines.append(f'{x["id"]}: [{choices}]')
    for x in receipt['outOfRequirement']:
        lines.append(f'{x["id"]}: [{ " | ".join(decision.FINDING_POSITIONS) }]')
    for x in receipt['unknowns']:
        lines.append(f'{x["id"]}: [acknowledged]')
    lines += ['```',
              'Append `-- your note` to a REF or OOR line to record an optional note. '
              'Use `/receipt changes [reason]` to request changes or `/receipt escalate [reason]` to route the gap to a code or domain owner. '
              'Requesting changes and escalating need only your reason; structured positions are optional.',
              'The operator then runs `engine/pr.py decide` with the human’s login and name. '
              'No event automation or branch protection is built. Bot and human share a login in a single-account demo; '
              'a teammate using their own account is preferred. Same-account decisions require an explicit operator flag.',
              f'[Open the walkthrough]({page}#receipt)',
              'The walkthrough is a pinned snapshot, not live PR state. Final freshness checks happen when the operator runs `decide`.']
    return '\n'.join(lines) + '\n'


def render_triage(row, head, base, page=PAGE):
    return '\n'.join([MARKER, f'<!-- receipt-head:{head} -->', f'## Review Receipt · {local_requirement_id(row["id"])} · triage only',
                      'Our HackJunction 2026 project · local demo environment. Supplied code is demo material.',
                      f'Head: `{head}` · Base: `{base}`', f'**Review depth: {row["tier"].replace("_", " ").upper()}**',
                      *[f'- {md(x)}' for x in row['reasons']],
                      'Triage only: no deep receipt, executed-check assessment, or human decision. Status stays pending.',
                      f'[Walkthrough]({page})']) + '\n'


def is_stale(receipt, head, base=None):
    return receipt['subject']['headSha'] != head or (base is not None and receipt['subject']['baseSha'] != base)


def parse_decision(body, contract, head):
    """Parse one human comment into the shared decision input.

    Structured lines use stable IDs. Unknown IDs, duplicates and acceptance
    contradictions are rejected by engine/decision.py, not by English prefixes.
    """
    lines = body.strip().splitlines()
    match = re.fullmatch(r'/receipt (accept|changes|escalate)\s+(.+)', lines[0] if lines else '')
    if not match:
        raise ValueError('Start with /receipt accept, /receipt changes or /receipt escalate followed by a reason.')
    action, reason = match.groups()
    reason = reason.strip()
    if not reason:
        raise ValueError('A non-empty reason is required.')
    if decision.is_placeholder(reason):
        raise ValueError('Replace the bracketed reason placeholder with your own words.')
    heads = re.findall(r'^Head:\s*([0-9a-f]{40})\s*$', body, re.M)
    if heads != [head]:
        raise ValueError('Include exactly one Head: line with the full receipt head SHA.')

    refusal_positions, finding_positions, acknowledged = [], [], []
    for line in lines[1:]:
        line = line.strip()
        m = re.fullmatch(r'(REF|OOR|UNK)([0-9]+):\s*(.*)', line)
        if not m:
            # Reject a malformed structured line instead of silently dropping it.
            if re.match(r'^(REF|OOR|UNK)(\w*:|\d)', line):
                raise ValueError(f'Malformed structured line: {line}. '
                                 'Use REF1: position-id, OOR1: accept_scope or UNK1: acknowledged.')
            continue
        kind, number, raw = m.groups()
        key = f'{kind}{number}'
        value, _, note = raw.partition(' -- ')
        value, note = value.strip(), note.strip()
        if not value:
            raise ValueError(f'{key}: a value is required.')
        if kind == 'REF':
            entry = {'refusalId': key, 'positionId': value}
            if note:
                entry['note'] = note
            refusal_positions.append(entry)
        elif kind == 'OOR':
            entry = {'findingId': key, 'positionId': value}
            if note:
                entry['note'] = note
            finding_positions.append(entry)
        elif note:
            raise ValueError(f'{key}: optional notes are supported only on REF and OOR lines.')
        elif value.casefold() != 'acknowledged':
            raise ValueError(f"{key}: write 'acknowledged' to acknowledge this unknown.")
        else:
            acknowledged.append(key)

    errors = decision.validate_decision(action, reason, refusal_positions,
                                        finding_positions, acknowledged, contract)
    if errors:
        raise ValueError(decision.format_errors(errors))
    return action, reason, refusal_positions, finding_positions, acknowledged


def apply_decision(receipt, comment, human, name, poster, head, allow_same=False, base=None):
    if is_stale(receipt, head, base):
        raise ValueError('Stale receipt: PR base/head changed. Rebuild evidence before deciding.')
    user = comment.get('user', {})
    if (user.get('type') != 'User' or user.get('login', '').casefold() != human.casefold()
            or not human.strip() or not name.strip() or MARKER in comment['body']):
        raise ValueError('Decision must be posted by the designated named human, not the receipt comment or a bot.')
    if human.casefold() == poster.casefold() and not allow_same:
        raise ValueError('Same-account decision: prefer a teammate; --allow-same-account requires an actual human comment.')
    contract = decision.contract_from_receipt(receipt)
    action, reason, refusal_positions, finding_positions, acknowledged = parse_decision(comment['body'], contract, head)
    status = {'accept': 'accepted', 'changes': 'changes_requested', 'escalate': 'escalated'}[action]
    result = copy.deepcopy(receipt)
    result['decision'] = dict(status=status,
                              owner=f'{name} (@{human})', reason=reason,
                              refusalPositions=refusal_positions,
                              findingPositions=finding_positions,
                              boundToHeadSha=head, signedAt=comment['created_at'])
    if action == 'accept':
        result['decision']['acceptedUnknownRefs'] = acknowledged
    if comment.get('html_url'):
        result['decision']['sourceCommentUrl'] = comment['html_url']
    return result


class GitHub:
    def __init__(self, repo, actor=None):
        if not re.fullmatch(r'[\w.-]+/[\w.-]+', repo):
            raise ValueError('Expected OWNER/REPO')
        self.repo = repo
        self.actor = actor

    def api(self, path, method='GET', payload=None):
        args = ['gh', 'api', path, '--method', method]
        if payload is not None:
            args += ['--input', '-']
        p = subprocess.run(args, input=json.dumps(payload) if payload is not None else None,
                           capture_output=True, text=True, check=True)
        return json.loads(p.stdout) if p.stdout.strip() else None

    def pr(self, number):
        return self.api(f'repos/{self.repo}/pulls/{number}')

    def comments(self, number):
        result, page = [], 1
        while True:
            batch = self.api(f'repos/{self.repo}/issues/{number}/comments?per_page=100&page={page}')
            result.extend(batch)
            if len(batch) < 100:
                return result
            page += 1

    def status(self, head, state, description):
        return self.api(f'repos/{self.repo}/statuses/{head}', 'POST',
                        dict(state=state, context='review-receipt', description=description, target_url=PAGE))

    def upsert(self, number, body, marker=MARKER):
        login = self.actor or self.api('user')['login']
        prior = next((c for c in self.comments(number) if c['body'].startswith(marker)
                      and c['user']['login'] == login), None)
        path = f'repos/{self.repo}/issues/comments/{prior["id"]}' if prior else f'repos/{self.repo}/issues/{number}/comments'
        return self.api(path, 'PATCH' if prior else 'POST', {'body': body})


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def validate(receipt):
    from jsonschema import Draft202012Validator
    from validate import invariant_errors
    schema = json.loads((ROOT / 'schema/receipt.schema.json').read_text())
    Draft202012Validator(schema).validate(receipt)
    errors = invariant_errors(receipt)
    if errors:
        raise ValueError('; '.join(errors))


def build_receipt(pr):
    """Reuse immutable recorded runs, never attach those runs to a new commit."""
    if not LIVE.exists():
        subprocess.run([sys.executable, str(HERE / 'propose.py'), str(ROOT / 'examples/receipt-2283.example.json'),
                        '--out', str(LIVE), '--raw-out', str(ROOT / 'evidence/propose-2283.live.raw.json')], check=True)
    r = json.loads(LIVE.read_text())
    if is_stale(r, pr['head']['sha'], pr['base']['sha']):
        raise ValueError('Recorded checks cover a different base/head. Run new checks and rebuild the live receipt.')
    import trx
    mapping = {f'CHK{i}': ROOT / f'evidence/trx/CHK{i}.trx' for i in range(1, 5)}
    # Checked-in per-test results allow reruns on a machine without the raw logs.
    if all(p.exists() for p in mapping.values()):
        r = trx.attach(r, mapping)
    elif any('tests' not in c for c in r['checks'] if c['id'] in mapping):
        raise ValueError('Missing recorded per-test evidence; attach the raw TRX runs first.')
    r['receiptId'] = 'receipt-2283-live'
    r['subject']['repository'] = pr['head']['repo']['full_name']
    if r['refusals'] or r['outOfRequirement']:
        focus = r['routing']['humanFocus']
        seen = {(f['file'], f.get('lines')) for f in focus}
        for claim in r['claims']:
            ci = claim['citation']
            lines = f"{ci['startLine']}-{ci['endLine']}"
            if claim['kind'] == 'code_fact' and (ci['file'], lines) not in seen:
                focus.append(dict(file=ci['file'], lines=lines, why=f"Review {claim['id']} alongside the scope findings and refusal questions; citation existence does not establish correctness."))
                seen.add((ci['file'], lines))
    r = review.finalize(r, str(ROOT / 'sample'))
    validate(r)
    save_json(LIVE, r)
    return r


def post(github, number, row):
    pr = github.pr(number)
    if (pr['head']['ref'] != row['branch'] or pr['base']['ref'] != row['baseBranch']
            or pr['head']['repo']['full_name'] != github.repo):
        raise ValueError('PR does not match the registered demo branches/repository.')
    github.status(pr['head']['sha'], 'pending', 'Needs a named human decision')
    if row['requirement'] == '#2283':
        receipt = build_receipt(pr)
        body = render_comment(receipt)
    else:
        if (pr['head']['sha'], pr['base']['sha']) != (row['headSha'], row['baseSha']):
            raise ValueError('Triage snapshot is stale; recompute it for this revision.')
        triage = next(t for t in json.loads((ROOT / 'examples/triage.json').read_text()) if t['id'] == row['requirement'])
        body = render_triage(triage, pr['head']['sha'], pr['base']['sha'])
    # Re-read after building to catch pushes during a model call / local finalization.
    now = github.pr(number)
    if (now['head']['sha'], now['base']['sha']) != (pr['head']['sha'], pr['base']['sha']):
        github.status(now['head']['sha'], 'pending', 'Receipt stale: PR changed during posting')
        raise ValueError('PR changed during posting; retry with fresh evidence.')
    return github.upsert(number, body)


def decide(github, number, human, name, allow_same=False):
    receipt = json.loads(LIVE.read_text())
    pr = github.pr(number)
    marker = '<!-- review-receipt-decision -->'
    if is_stale(receipt, pr['head']['sha'], pr['base']['sha']):
        github.status(pr['head']['sha'], 'pending', 'Receipt stale: PR base/head changed')
        github.upsert(number, marker + '\nStale receipt: PR base/head changed. Prior decisions do not apply; rebuild evidence.', marker)
        return None
    comments = github.comments(number)
    poster = github.api('user')['login']
    published = next((c for c in comments if c['body'].startswith(MARKER) and c['user']['login'] == poster), None)
    if not published or f'receipt-digest:{fingerprint(receipt)}' not in published['body']:
        raise ValueError('Post the current receipt before processing a decision.')
    candidates = [c for c in comments if c['body'].startswith('/receipt ') and c['user'].get('login', '').casefold() == human.casefold()
                  and c['created_at'] >= published['created_at']]
    if not candidates:
        raise ValueError('No human decision comment found after the receipt was posted.')
    comment = max(candidates, key=lambda c: c['id'])
    try:
        result = apply_decision(receipt, comment, human, name, poster, pr['head']['sha'], allow_same, pr['base']['sha'])
        validate(result)
    except ValueError as error:
        github.status(pr['head']['sha'], 'pending', 'Human decision needs correction')
        github.upsert(number, marker + '\nDecision rejected: ' + str(error), marker)
        return None
    now = github.pr(number)
    if is_stale(receipt, now['head']['sha'], now['base']['sha']):
        github.status(now['head']['sha'], 'pending', 'Receipt stale: PR changed during decision')
        github.upsert(number, marker + '\nStale: PR changed while reading the decision. Nothing signed.', marker)
        return None
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['post', 'decide'])
    parser.add_argument('pr', type=int)
    parser.add_argument('--repo', default=REPO)
    parser.add_argument('--human')
    parser.add_argument('--name')
    parser.add_argument('--allow-same-account', action='store_true')
    args = parser.parse_args()
    rows = json.loads(REGISTRY.read_text())
    row = next((r for r in rows if r['number'] == args.pr and r['repository'] == args.repo), None)
    if not row:
        parser.error('PR is not registered in docs/pull-requests.json')
    github = GitHub(args.repo)
    if args.command == 'post':
        posted = post(github, args.pr, row)
        row['receiptCommentUrl'] = posted['html_url']
        row['status'] = 'pending'
    else:
        if row['requirement'] != '#2283':
            parser.error('Triage-only PRs cannot be accepted through this CLI.')
        if not args.human or not args.name:
            parser.error('decide requires --human LOGIN and --name FULL_NAME of the actual commenter')
        result = decide(github, args.pr, args.human, args.name, args.allow_same_account)
        if result is None:
            row['status'] = 'pending'
        else:
            save_json(LIVE, result)
            row['status'] = status_for(result['decision'])
            save_json(REGISTRY, rows)
            subprocess.run([sys.executable, str(HERE / 'render.py')], check=True)
            subprocess.run(['git', '-C', str(ROOT), 'add', '--', str(LIVE), str(REGISTRY), str(ROOT / 'walkthrough/index.html')], check=True)
            subprocess.run(['git', '-C', str(ROOT), 'commit', '--only', str(LIVE), str(REGISTRY), str(ROOT / 'walkthrough/index.html'),
                            '-m', f'Record human receipt decision for {row["requirement"]}'], check=True)
            github.upsert(args.pr, render_comment(result))
            github.status(result['subject']['headSha'], row['status'],
                          'Named human decision recorded for this head' if row['status'] != 'pending'
                          else 'Escalated: pending owner judgement')
    save_json(REGISTRY, rows)
    subprocess.run([sys.executable, str(HERE / 'render.py')], check=True)
    print(f'{row["url"]}: {row["status"]}')


if __name__ == '__main__':
    main()
