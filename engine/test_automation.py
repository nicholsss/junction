"""Event identity, replay and freshness tests; never posts a real decision."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import automation
import pr
from test_pr import R, HEAD, BASE, ROW, api_mock, comment

SETTINGS = dict(reviewers={'teammate': 'Actual Human'}, automationLogin='receipt[bot]',
                receiptPublishers=['poster'])


def event(action='accept'):
    g = api_mock()
    c = comment(action=action, structured=action == 'accept')
    c.update(issue_url=f'https://api.github.com/repos/{pr.REPO}/issues/1',
             html_url=f'https://github.com/{pr.REPO}/pull/1#issuecomment-12',
             updated_at=c['created_at'])
    g.api.return_value = c
    return g, c


class EventTests(unittest.TestCase):
    def test_three_outcomes_use_the_shared_contract(self):
        for action, status in [('accept', 'accepted'), ('changes', 'changes_requested'), ('escalate', 'escalated')]:
            with self.subTest(action=action):
                g, _ = event(action)
                result, _ = automation.process(g, 1, 12, SETTINGS, copy.deepcopy(R))
                self.assertEqual(result['decision']['status'], status)
                self.assertIn('#issuecomment-12', result['decision']['sourceCommentUrl'])
                g.api.assert_called_once_with(f'repos/{pr.REPO}/issues/comments/12')

    def test_unapproved_and_bot_authors_rejected(self):
        for login, kind in [('stranger', 'User'), ('teammate', 'Bot')]:
            g, c = event()
            c['user'] = dict(login=login, type=kind)
            with self.assertRaisesRegex(ValueError, 'approved reviewer'):
                automation.process(g, 1, 12, SETTINGS, R)
            g.status.assert_not_called()

    def test_public_demo_accepts_unregistered_humans_but_not_bots(self):
        settings = dict(SETTINGS, policy='public_demo')
        g, c = event('changes')
        c['user']['login'] = 'visiting-judge'
        result, _ = automation.process(g, 1, 12, settings, R)
        self.assertEqual(result['decision']['owner'], 'visiting-judge (@visiting-judge)')
        c['user']['type'] = 'Bot'
        with self.assertRaisesRegex(ValueError, 'approved reviewer'):
            automation.process(g, 1, 12, settings, R)

    def test_comment_from_other_pr_is_rejected(self):
        g, c = event()
        c['issue_url'] += '0'
        with self.assertRaisesRegex(ValueError, 'does not belong'):
            automation.process(g, 1, 12, SETTINGS, R)

    def test_edited_comments_require_new_comment(self):
        g, c = event()
        c['updated_at'] = '2026-11-14T11:00:00Z'
        with self.assertRaisesRegex(ValueError, 'Edited'):
            automation.process(g, 1, 12, SETTINGS, R)

    def test_replay_and_older_events_do_not_apply(self):
        g, _ = event()
        for prior in [12, 13]:
            receipt = copy.deepcopy(R)
            receipt['decision']['sourceCommentUrl'] = f'https://github.com/{pr.REPO}/pull/1#issuecomment-{prior}'
            result, message = automation.process(g, 1, 12, SETTINGS, receipt)
            self.assertIsNone(result)
            self.assertIn('superseded', message)
            g.status.assert_not_called()

    def test_bad_accept_does_not_clear_previous_status(self):
        g, c = event()
        c['body'] = f'/receipt accept missing all positions\nHead: {HEAD}'
        with self.assertRaises(ValueError):
            automation.process(g, 1, 12, SETTINGS, R)
        g.status.assert_not_called()

    def test_stale_head_and_push_during_validation_stay_pending(self):
        for during in [False, True]:
            g, _ = event()
            fresh = copy.deepcopy(g.pr.return_value)
            stale = copy.deepcopy(fresh)
            stale['head']['sha'] = 'b' * 40
            g.pr.side_effect = [fresh, stale] if during else [stale]
            result, _ = automation.process(g, 1, 12, SETTINGS, R)
            self.assertIsNone(result)
            self.assertEqual(g.status.call_args.args[1], 'pending')

    def test_untrusted_or_mismatched_published_receipt_is_rejected(self):
        for tamper in ['author', 'digest']:
            g, _ = event()
            comments = copy.deepcopy(g.comments.return_value)
            if tamper == 'author':
                comments[0]['user']['login'] = 'stranger'
            else:
                comments[0]['body'] = pr.MARKER + '\nnot matching evidence'
            g.comments.return_value = comments
            with self.assertRaisesRegex(ValueError, 'trusted published receipt'):
                automation.process(g, 1, 12, SETTINGS, R)

    def test_wrong_registered_branch_and_triage_only_pr_rejected(self):
        g, _ = event()
        g.pr.return_value['head']['ref'] = 'another-branch'
        with self.assertRaisesRegex(ValueError, 'registered demo PR'):
            automation.process(g, 1, 12, SETTINGS, R)
        with self.assertRaisesRegex(ValueError, 'deep-review'):
            automation.registered(pr.REPO, 2)

    def test_app_actor_avoids_unsupported_user_endpoint(self):
        from unittest.mock import Mock
        g = pr.GitHub(pr.REPO, actor='receipt[bot]')
        g.api = Mock(return_value={})
        g.comments = Mock(return_value=[])
        g.upsert(1, 'test')
        self.assertEqual(g.api.call_count, 1)
        self.assertIn('/issues/1/comments', g.api.call_args.args[0])


class WorkerRecoveryTests(unittest.TestCase):
    def test_coalesced_events_and_retries_preserve_latest_valid_decision(self):
        import contextlib
        import io
        import json
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt_path, registry_path = root / 'receipt.json', root / 'registry.json'
            state_path, settings_path = root / 'state.json', root / 'reviewers.json'
            receipt_path.write_text(json.dumps(R))
            registry_path.write_text(json.dumps([ROW]))
            settings_path.write_text(json.dumps(SETTINGS))
            g, valid = event('accept')
            invalid = copy.deepcopy(valid)
            invalid.update(id=13, body=f'/receipt accept incomplete\nHead: {HEAD}')
            g.comments.return_value = [g.comments.return_value[0], valid, invalid]
            g.api.side_effect = lambda path: invalid if path.endswith('/13') else valid
            with patch.object(pr, 'LIVE', receipt_path), patch.object(pr, 'REGISTRY', registry_path), \
                 patch.object(automation, 'STATE', state_path), patch.object(automation, 'CONFIG', settings_path), \
                 patch.object(pr, 'GitHub', return_value=g), \
                 patch.object(sys, 'argv', ['automation.py', '--repo', pr.REPO, '--pr', '1', '--comment-id', '13']), \
                 contextlib.redirect_stdout(io.StringIO()):
                # One delivered event sweeps both comments in posting order.
                automation.main()
                self.assertEqual(json.loads(receipt_path.read_text())['decision']['status'], 'accepted')
                self.assertEqual(json.loads(state_path.read_text())['lastProcessedCommentId'], 13)
                self.assertEqual(g.upsert.call_count, 2)
                self.assertEqual(g.status.call_args.args[1], 'success')
                g.api.reset_mock()
                automation.main()
                # Retry neither reapplies the comments nor creates duplicate replies.
                g.api.assert_not_called()
                self.assertEqual(g.upsert.call_count, 2)
                self.assertEqual(json.loads(receipt_path.read_text())['decision']['status'], 'accepted')


if __name__ == '__main__':
    unittest.main()
