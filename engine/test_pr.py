"""Pure receipt contracts and mocked GitHub edges. Never posts a human decision."""
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent))
import decision
import pr
import render

R = json.loads(pr.LIVE.read_text())
HEAD = R['subject']['headSha']
BASE = R['subject']['baseSha']
ROW = json.loads(pr.REGISTRY.read_text())[0]
CONTRACT = decision.contract_from_receipt(R)


def structured_lines(include=True, refusal_position=None, finding_position='accept_scope',
                     unknown_value='acknowledged'):
    lines = []
    if not include:
        return lines
    for refusal in R['refusals']:
        position = refusal_position or next(p['id'] for p in refusal['positions']
                                            if p['effect'] == 'accept_compatible')
        lines.append(f'{refusal["id"]}: {position}')
    for finding in R['outOfRequirement']:
        lines.append(f'{finding["id"]}: {finding_position}')
    for unknown in R['unknowns']:
        lines.append(f'{unknown["id"]}: {unknown_value}')
    return lines


def comment(action='accept', structured=True, login='teammate',
            reason='I reviewed the evidence and accept the listed risks.',
            refusal_position=None, finding_position='accept_scope', unknown_value='acknowledged'):
    body = f'/receipt {action} {reason}\nHead: {HEAD}\n'
    body += '\n'.join(structured_lines(structured, refusal_position,
                                       finding_position, unknown_value))
    return dict(id=12, body=body, user=dict(login=login, type='User'),
                created_at='2026-11-14T10:00:00Z')


def api_mock():
    g = Mock()
    g.repo = pr.REPO
    g.pr.return_value = dict(head=dict(sha=HEAD, ref=ROW['branch'], repo=dict(full_name=pr.REPO)),
                            base=dict(sha=BASE, ref=ROW['baseBranch']))
    g.api.return_value = {'login': 'poster'}
    g.comments.return_value = [dict(id=1, body=pr.render_comment(R), user=dict(login='poster'), created_at='2026-11-14T09:00:00Z'), comment()]
    return g


class CommentTests(unittest.TestCase):
    def test_full_comment_contains_decision_critical_evidence(self):
        body = pr.render_comment(R)
        self.assertIn(HEAD, body)
        self.assertIn(BASE, body)
        self.assertIn(pr.MARKER, body)
        for statement in R['decisionBrief']:
            self.assertIn(pr.md(statement['text']), body)
        for c in R['claims'] + R['refusals']:
            self.assertIn(c['id'], body)
        for x in R['outOfRequirement'] + R['unknowns']:
            self.assertIn(x['id'], body)
        for r in R['routing']['reasons']:
            self.assertIn(pr.md(r['rule']), body)
        self.assertNotIn('/Users/', body)
        self.assertNotIn('INJECTED', body)

    def test_comment_explains_statuses_without_hallucination_score(self):
        body = pr.render_comment(R)
        self.assertIn('not a trust or hallucination score', body)
        self.assertIn('unproven rather than proven false', body)
        for claim in R['claims']:
            self.assertIn(pr.md(claim['statusReason']), body)

    def test_comment_shows_positions_and_every_check_limit(self):
        body = pr.render_comment(R)
        for refusal in R['refusals']:
            for position in refusal['positions']:
                self.assertIn(position['id'], body)
        self.assertIn('accept_scope', body)
        self.assertIn('change_required', body)
        self.assertIn('needs_owner', body)
        for check in R['checks']:
            self.assertIn(pr.md(check['limitations']), body)
            self.assertIn(pr.CHECK_LABEL[check['status']], body)

    def test_comment_source_links_use_the_actual_citation_revision(self):
        body = pr.render_comment(R)
        for claim in R['claims']:
            sha = claim['citation']['sha']
            self.assertIn(f'/blob/{sha}/', body)

    def test_public_comments_use_local_requirement_labels(self):
        body = pr.render_comment(R)
        self.assertIn("R2283", body)
        self.assertIn("HackJunction 2026", body)
        self.assertNotIn("#2283", body)
        self.assertNotIn("github.com/MessagePack-CSharp/", body)
        self.assertNotIn("github.com/te-industry-tech-office/", body)
        row = json.loads((pr.ROOT / 'examples/triage.json').read_text())[1]
        triage = pr.render_triage(row, HEAD, BASE)
        self.assertIn("R2234", triage)
        self.assertNotIn("#2234", triage)

    def test_model_text_cannot_inject_html_or_table_columns(self):
        r = copy.deepcopy(R)
        r['claims'][0]['text'] = '<script>alert(1)</script>|extra\nline'
        r['decisionBrief'][0]['text'] = '<script>alert(2)</script>|extra'
        body = pr.render_comment(r)
        self.assertNotIn('<script>', body)
        self.assertIn('&#124;', body)

    def test_comment_states_snapshot_and_no_code_path(self):
        body = pr.render_comment(R)
        self.assertIn('pinned snapshot, not live PR state', body)
        self.assertIn('Source is optional corroboration', body)

    def test_triage_is_explicit(self):
        row = json.loads((pr.ROOT / 'examples/triage.json').read_text())[1]
        body = pr.render_triage(row, HEAD, BASE)
        self.assertIn('triage only', body)
        self.assertIn(HEAD, body)
        self.assertNotIn('/receipt accept', body)

    def test_fingerprint_ignores_decision_but_not_decision_bearing_brief(self):
        r = copy.deepcopy(R)
        r['decision'] = {'status': 'accepted'}
        self.assertEqual(pr.fingerprint(R), pr.fingerprint(r))
        r['decisionBrief'][0]['text'] += ' changed'
        self.assertNotEqual(pr.fingerprint(R), pr.fingerprint(r))
        r = copy.deepcopy(R)
        r['refusals'][0]['positions'][0]['label'] += ' changed'
        self.assertNotEqual(pr.fingerprint(R), pr.fingerprint(r))


class DecisionTests(unittest.TestCase):
    def apply(self, c=None, **kw):
        return pr.apply_decision(R, c or comment(), 'teammate', 'Actual Human', 'poster', HEAD, **kw)

    def test_accept_bound_to_sha_and_human(self):
        r = self.apply()
        self.assertEqual(r['decision']['status'], 'accepted')
        self.assertEqual(r['decision']['boundToHeadSha'], HEAD)
        self.assertEqual(r['decision']['owner'], 'Actual Human (@teammate)')
        self.assertEqual(r['decision']['signedAt'], comment()['created_at'])
        self.assertEqual(R['decision']['status'], 'pending')
        self.assertEqual(len(r['decision']['refusalPositions']), len(R['refusals']))
        self.assertEqual(len(r['decision']['findingPositions']), len(R['outOfRequirement']))
        self.assertEqual(r['decision']['acceptedUnknownRefs'], [u['id'] for u in R['unknowns']])
        self.assertNotIn('acceptedResidualRisk', r['decision'])
        self.assertNotIn('refusalAnswers', r['decision'])
        pr.validate(r)

    def test_changes_can_omit_structured_positions(self):
        r = self.apply(comment('changes', structured=False,
                               reason='The filter hides diagnostics the consumer cannot investigate.'))
        self.assertEqual(r['decision']['status'], 'changes_requested')
        pr.validate(r)

    def test_escalate_is_pending_not_failure(self):
        r = self.apply(comment('escalate', structured=False,
                               reason='A source-generator owner must judge the suppression policy.'))
        self.assertEqual(r['decision']['status'], 'escalated')
        self.assertEqual(pr.status_for(r['decision']), 'pending')
        self.assertNotIn('acceptedUnknownRefs', r['decision'])
        pr.validate(r)

    def test_status_mapping_is_distinct(self):
        self.assertEqual(pr.status_for({'status': 'accepted'}), 'success')
        self.assertEqual(pr.status_for({'status': 'changes_requested'}), 'failure')
        self.assertEqual(pr.status_for({'status': 'escalated'}), 'pending')
        self.assertEqual(pr.status_for({'status': 'pending'}), 'pending')

    def test_accept_requires_each_refusal_position(self):
        with self.assertRaisesRegex(ValueError, 'REF1'):
            self.apply(comment(structured=False))

    def test_accept_rejects_change_required_position(self):
        with self.assertRaisesRegex(ValueError, 'does not permit acceptance'):
            self.apply(comment(refusal_position='ref1_require_visible'))

    def test_accept_rejects_change_required_finding(self):
        with self.assertRaisesRegex(ValueError, 'does not permit acceptance'):
            self.apply(comment(finding_position='change_required'))

    def test_accept_requires_unknown_acknowledgements(self):
        c = comment()
        c['body'] = c['body'].replace(f"{R['unknowns'][0]['id']}: acknowledged\n", '')
        with self.assertRaisesRegex(ValueError, R['unknowns'][0]['id']):
            self.apply(c)

    def test_unknown_ids_are_rejected(self):
        c = comment()
        c['body'] = c['body'].replace(f"{R['unknowns'][0]['id']}: acknowledged", 'UNK9: acknowledged')
        with self.assertRaisesRegex(ValueError, 'not an unknown'):
            self.apply(c)

    def test_duplicate_structured_line_is_rejected(self):
        c = comment()
        c['body'] += f"\n{R['refusals'][0]['id']}: ref1_require_visible"
        with self.assertRaisesRegex(ValueError, 'more than once'):
            self.apply(c)

    def test_unknown_acknowledgement_value_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'acknowledged'):
            self.apply(comment(unknown_value='yes'))

    def test_malformed_structured_lines_are_rejected(self):
        for line in ('REF1 ref1_accept_suppression', 'OOR1 accept_scope',
                     'UNKK1: acknowledged', 'REF: ref1_accept_suppression'):
            with self.subTest(line=line):
                c = comment('changes', structured=False,
                            reason='The filter hides diagnostics the consumer cannot investigate.')
                c['body'] += '\n' + line
                with self.assertRaisesRegex(ValueError, 'Malformed'):
                    self.apply(c)

    def test_optional_position_note_is_persisted(self):
        position = next(p['id'] for p in R['refusals'][0]['positions']
                        if p['effect'] == 'accept_compatible')
        c = comment()
        c['body'] = c['body'].replace(f"{R['refusals'][0]['id']}: {position}",
                                      f"{R['refusals'][0]['id']}: {position} -- noted for the demo")
        r = self.apply(c)
        entry = next(p for p in r['decision']['refusalPositions']
                     if p['refusalId'] == R['refusals'][0]['id'])
        self.assertEqual(entry['note'], 'noted for the demo')
        pr.validate(r)

    def test_validate_rejects_duplicate_acceptance_criteria(self):
        r = copy.deepcopy(R)
        r['requirement']['acceptanceCriteria'].append(copy.deepcopy(r['requirement']['acceptanceCriteria'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicated'):
            pr.validate(r)

    def test_validate_requires_a_reason_for_changes(self):
        r = copy.deepcopy(R)
        r['decision'] = dict(status='changes_requested', owner='Actual Human (@teammate)',
                             reason='', signedAt='2026-11-14T10:00:00Z', boundToHeadSha=HEAD)
        with self.assertRaisesRegex(ValueError, 'reason'):
            pr.validate(r)

    def test_validate_allows_escalation_with_reason_only(self):
        r = copy.deepcopy(R)
        r['decision'] = dict(status='escalated', owner='Actual Human (@teammate)',
                             reason='A source-generator owner must judge the policy.',
                             signedAt='2026-11-14T10:00:00Z', boundToHeadSha=HEAD)
        pr.validate(r)

    def test_placeholder_reason_rejected(self):
        with self.assertRaisesRegex(ValueError, 'placeholder'):
            self.apply(comment(reason='[your reason]'))

    def test_legitimate_bracketed_reason_accepted(self):
        r = self.apply(comment(reason='The [FromMetadata] case is separate; I accept the listed risks.'))
        self.assertEqual(r['decision']['status'], 'accepted')

    def test_blank_reason_rejected(self):
        with self.assertRaisesRegex(ValueError, 'reason'):
            pr.parse_decision('/receipt accept    \nHead: ' + HEAD, CONTRACT, HEAD)

    def test_command_required(self):
        for body in ['/receipt accept\nHead: ' + HEAD,
                     '/receipt approve yes\nHead: ' + HEAD]:
            with self.assertRaises(ValueError):
                pr.parse_decision(body, CONTRACT, HEAD)

    def test_wrong_author(self):
        with self.assertRaisesRegex(ValueError, 'designated'):
            self.apply(comment(login='stranger'))

    def test_bot_rejected(self):
        c = comment()
        c['user']['type'] = 'Bot'
        with self.assertRaises(ValueError):
            self.apply(c)

    def test_receipt_marker_cannot_sign(self):
        c = comment()
        c['body'] += '\n' + pr.MARKER
        with self.assertRaises(ValueError):
            self.apply(c)

    def test_same_account_requires_explicit_flag(self):
        args = (R, comment(login='poster'), 'poster', 'Actual Human', 'poster', HEAD)
        with self.assertRaisesRegex(ValueError, 'Same-account'):
            pr.apply_decision(*args)
        self.assertEqual(pr.apply_decision(*args, allow_same=True)['decision']['status'], 'accepted')

    def test_head_line_required_and_exact(self):
        for head in ['', '0' * 40, HEAD + '\nHead: ' + HEAD]:
            c = comment()
            c['body'] = c['body'].replace(HEAD, head)
            with self.assertRaisesRegex(ValueError, 'Head:'):
                self.apply(c)

    def test_stale_head_and_base(self):
        self.assertFalse(pr.is_stale(R, HEAD, BASE))
        self.assertTrue(pr.is_stale(R, '0' * 40))
        self.assertTrue(pr.is_stale(R, HEAD, '0' * 40))
        with self.assertRaisesRegex(ValueError, 'Stale'):
            pr.apply_decision(R, comment(), 'teammate', 'Name', 'poster', '0' * 40)


class EdgeTests(unittest.TestCase):
    @patch.object(pr, 'build_receipt', return_value=R)
    def test_post_pending_upserts(self, build):
        g = api_mock()
        pr.post(g, 1, ROW)
        g.status.assert_called_once_with(HEAD, 'pending', 'Needs a named human decision')
        self.assertTrue(g.upsert.call_args.args[1].startswith(pr.MARKER))

    @patch.object(pr, 'build_receipt', side_effect=ValueError('stale'))
    def test_post_fails_closed(self, build):
        g = api_mock()
        with self.assertRaises(ValueError):
            pr.post(g, 1, ROW)
        g.upsert.assert_not_called()
        self.assertEqual(g.status.call_args.args[1], 'pending')

    def test_rejected_decision_keeps_pending_and_explains(self):
        g = api_mock()
        g.comments.return_value[-1] = comment(structured=False)
        self.assertIsNone(pr.decide(g, 1, 'teammate', 'Actual Human'))
        self.assertIn('REF1', g.upsert.call_args.args[1])
        self.assertEqual(g.status.call_args.args[1], 'pending')

    def test_valid_decision_has_no_network_signoff_before_persistence(self):
        g = api_mock()
        result = pr.decide(g, 1, 'teammate', 'Actual Human')
        self.assertEqual(result['decision']['status'], 'accepted')
        g.status.assert_not_called()

    def test_escalation_is_not_marked_success_or_failure(self):
        g = api_mock()
        g.comments.return_value[-1] = comment('escalate', structured=False,
                                              reason='Needs a source-generator owner.')
        result = pr.decide(g, 1, 'teammate', 'Actual Human')
        self.assertEqual(result['decision']['status'], 'escalated')
        g.status.assert_not_called()

    def test_stale_decision_posts_pending(self):
        g = api_mock()
        g.pr.return_value['head']['sha'] = '0' * 40
        self.assertIsNone(pr.decide(g, 1, 'teammate', 'Actual Human'))
        self.assertEqual(g.status.call_args.args[:2], ('0' * 40, 'pending'))
        self.assertIn('Stale', g.upsert.call_args.args[1])

    def test_push_during_decision_does_not_sign(self):
        g = api_mock()
        now = copy.deepcopy(g.pr.return_value)
        now['head']['sha'] = '0' * 40
        g.pr.side_effect = [g.pr.return_value, now]
        self.assertIsNone(pr.decide(g, 1, 'teammate', 'Actual Human'))
        self.assertEqual(g.status.call_args.args[:2], ('0' * 40, 'pending'))

    def test_unpublished_receipt_not_processed(self):
        g = api_mock()
        g.comments.return_value = [comment()]
        with self.assertRaisesRegex(ValueError, 'Post the current'):
            pr.decide(g, 1, 'teammate', 'Name')

    @patch('pr.subprocess.run')
    def test_gh_edge_uses_structured_stdin(self, run):
        run.return_value.stdout = '{"id": 1}'
        g = pr.GitHub(pr.REPO)
        self.assertEqual(g.api('path', 'POST', {'body': 'literal $()\ntext'}), {'id': 1})
        self.assertEqual(json.loads(run.call_args.kwargs['input'])['body'], 'literal $()\ntext')

    def test_upsert_ignores_other_authors_and_edits_own_marker(self):
        g = pr.GitHub(pr.REPO)
        g.api = Mock(side_effect=[dict(login='poster'), dict(id=99)])
        g.comments = Mock(return_value=[dict(id=3, body=pr.MARKER, user=dict(login='other')), dict(id=4, body=pr.MARKER, user=dict(login='poster'))])
        g.upsert(1, 'body')
        self.assertEqual(g.api.call_args.args[0], f'repos/{pr.REPO}/issues/comments/4')
        self.assertEqual(g.api.call_args.args[1], 'PATCH')


class PageFlowTests(unittest.TestCase):
    def test_real_pr_flow_no_browser_signature(self):
        page = render.build(R, json.loads(render.MODEL_RUN.read_text()), json.loads(render.TRIAGE.read_text()))
        self.assertIn('/receipt accept', page)
        self.assertIn(ROW['url'], page)
        self.assertIn('Copy decision draft', page)
        self.assertNotIn('localStorage', page)
        self.assertNotIn('Download decision JSON', page)
        self.assertNotIn('Record decision', page)

    def test_signed_snapshot_is_rendered(self):
        signed = pr.apply_decision(R, comment(), 'teammate', 'Actual Human', 'poster', HEAD)
        with patch.object(render, 'receipt_pr', return_value=dict(status='success')):
            self.assertIn('accepted by Actual Human', render.render_header(signed))
            self.assertIn('I reviewed the evidence', render.render_decision(signed))


if __name__ == '__main__':
    unittest.main()
