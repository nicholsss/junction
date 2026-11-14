#!/usr/bin/env python3
"""Trusted Actions entry point. Never executes code or shell text from a PR/comment."""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import pr

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / 'docs/reviewers.json'
STATE = ROOT / 'examples/automation-state.json'


def config():
    return json.loads(CONFIG.read_text())


def registered(repo, number):
    row = next((r for r in json.loads(pr.REGISTRY.read_text())
                if r['repository'] == repo and r['number'] == number), None)
    if not row or row['requirement'] != '#2283':
        raise ValueError('Only the registered R2283 deep-review PR supports decisions.')
    return row


def verify_pr(github, number, row):
    current = github.pr(number)
    if (current['head']['ref'] != row['branch'] or current['base']['ref'] != row['baseBranch']
            or current['head']['repo']['full_name'] != github.repo
            or current.get('state', 'open') != 'open'):
        raise ValueError('PR does not match the open registered demo PR.')
    return current


def process(github, number, comment_id, settings, receipt):
    """Return (receipt or None, explanation). Invalid commands never erase a decision."""
    row = registered(github.repo, number)
    current = verify_pr(github, number, row)
    comment = github.api(f'repos/{github.repo}/issues/comments/{comment_id}')
    expected_issue = f'https://api.github.com/repos/{github.repo}/issues/{number}'
    if comment.get('issue_url') != expected_issue:
        raise ValueError('Comment does not belong to this PR.')
    login = comment['user']['login']
    names = {k.casefold(): v for k, v in settings['reviewers'].items()}
    public_demo = settings.get('policy') == 'public_demo'
    if comment['user'].get('type') != 'User' or (not public_demo and login.casefold() not in names):
        raise ValueError('This commenter is not an approved reviewer. Ask the demo operator to register your login.')
    # Edited commands require a new comment; this gives the decision immutable input semantics.
    if comment.get('updated_at') != comment.get('created_at'):
        raise ValueError('Edited decisions are not processed. Post a new decision comment.')
    if not comment['body'].startswith('/receipt '):
        raise ValueError('Not a receipt decision command.')
    prior_url = receipt['decision'].get('sourceCommentUrl', '')
    if prior_url:
        prior_id = int(prior_url.rsplit('-', 1)[-1])
        if comment_id <= prior_id:
            return None, 'Already processed or superseded by a newer recorded decision.'
    if pr.is_stale(receipt, current['head']['sha'], current['base']['sha']):
        github.status(current['head']['sha'], 'pending', 'Receipt stale: fresh evidence required')
        return None, 'Receipt stale. The operator must rebuild evidence for the current base and head.'
    publishers = {x.casefold() for x in settings['receiptPublishers']}
    published = next((c for c in reversed(github.comments(number))
                      if c['body'].startswith(pr.MARKER)
                      and c['user']['login'].casefold() in publishers
                      and f'receipt-digest:{pr.fingerprint(receipt)}' in c['body']), None)
    if not published:
        raise ValueError('No trusted published receipt matches this evidence. Repost the current receipt first.')
    if comment['created_at'] < published['created_at']:
        raise ValueError('Post a new decision after the current receipt was published.')
    poster = settings['automationLogin']
    result = pr.apply_decision(receipt, comment, login, names.get(login.casefold(), login), poster,
                               current['head']['sha'], base=current['base']['sha'])
    pr.validate(result)
    latest = verify_pr(github, number, row)
    if pr.is_stale(result, latest['head']['sha'], latest['base']['sha']):
        github.status(latest['head']['sha'], 'pending', 'Receipt stale: PR changed during processing')
        return None, 'PR changed during processing. Fresh evidence is required; nothing recorded.'
    return result, f'Decision recorded: {result["decision"]["status"].replace("_", " ")}. [Source comment]({comment["html_url"]}).'


def save_state(row, current, message, receipt, watermark=0):
    rows = json.loads(pr.REGISTRY.read_text())
    row['status'] = 'pending' if pr.is_stale(receipt, current['head']['sha'], current['base']['sha']) else pr.status_for(receipt['decision'])
    for i, old in enumerate(rows):
        if (old['repository'], old['number']) == (row['repository'], row['number']):
            rows[i] = row
    pr.save_json(pr.REGISTRY, rows)
    pr.save_json(STATE, dict(updatedAt=datetime.now(timezone.utc).isoformat(),
                            repository=row['repository'], pr=row['number'], lastProcessedCommentId=watermark,
                            currentHead=current['head']['sha'], currentBase=current['base']['sha'],
                            receiptHead=receipt['subject']['headSha'],
                            stale=pr.is_stale(receipt, current['head']['sha'], current['base']['sha']),
                            message=message, runUrl=os.environ.get('REVIEW_RUN_URL', '')))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True)
    parser.add_argument('--pr', type=int, required=True)
    parser.add_argument('--comment-id', type=int)
    args = parser.parse_args()
    row = registered(args.repo, args.pr)
    settings = config()
    github = pr.GitHub(args.repo, actor=settings['automationLogin'])
    receipt = json.loads(pr.LIVE.read_text())
    current = verify_pr(github, args.pr, row)
    result = None
    message = 'Current receipt checked against the PR.'
    # Actions concurrency retains one pending run, not a durable FIFO. Sweep the
    # authoritative PR comment history so coalesced deliveries cannot lose decisions.
    previous = json.loads(STATE.read_text()) if STATE.exists() else {}
    watermark = previous.get('lastProcessedCommentId', 0) if previous.get('repository') == args.repo else 0
    comments = github.comments(args.pr)
    candidates = sorted((c for c in comments if c['id'] > watermark
                         and c['body'].startswith('/receipt ')), key=lambda c: c['id'])
    for candidate in candidates:
        cid = candidate['id']
        try:
            applied, message = process(github, args.pr, cid, settings, receipt)
            if applied:
                result = receipt = applied
        except ValueError as error:
            message = 'Decision not recorded: ' + str(error)
        marker = f'<!-- review-receipt-result:{cid} -->'
        github.upsert(args.pr, marker + '\n' + message + '\n\n[Review workspace](' + pr.PAGE + ')', marker)
        watermark = cid
    if result:
        receipt = result
        pr.save_json(pr.LIVE, receipt)
    current = verify_pr(github, args.pr, row)
    if pr.is_stale(receipt, current['head']['sha'], current['base']['sha']):
        message = 'Receipt stale: this PR needs fresh evidence. Earlier decisions cover the recorded commit only.'
        github.status(current['head']['sha'], 'pending', 'Receipt stale: fresh evidence required')
    elif receipt['decision']['status'] != 'pending':
        github.status(current['head']['sha'], pr.status_for(receipt['decision']),
                      'Recorded human decision: ' + receipt['decision']['status'])
    save_state(row, current, message, receipt, watermark)
    print(message)


if __name__ == '__main__':
    main()
