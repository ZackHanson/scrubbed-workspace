"""The recovery fence applies to public APIs and already-created instances."""
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from actions import ActionStore
from claude_adapter import AdapterConfig, ClaudeAdapter, FakeTransport
from holds import HoldStore
from intake import IntakeLedger
from operations import Runner, WorkItem
from recovery_guard import RecoveryError, _write_state, state_lock
from recovery import snapshot, restore, acknowledge_restore
from review import CandidateStore, ReviewError
from review_workflow import Reviewer, managed
from routing import DecisionStore
from shadow_workflow import ShadowWorkflow
from synthetic_workflow import fixture, synthetic_checks
import scrubber
import triage
from claude_pilot import Pilot


class StateAccessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'state'
        self.enterContext(synthetic_checks())
        self.workflow = ShadowWorkflow(self.root)
        self.source = fixture(Path(self.temp.name) / 'synthetic.eml')
        self.ticket = self.workflow.register(self.source)
        self.workflow.run([self.ticket])
        self.candidate = self.workflow.candidates.load(self.ticket)
        self.reviewer = Reviewer(self.root)
        self.holds = HoldStore(self.root)
        self.hold = self.holds.create(self.ticket, 'needs_recheck',
                                      self.workflow.intake.private_source(self.ticket)['source'])
        self.transport = Mock(wraps=FakeTransport())
        self.adapter = ClaudeAdapter(self.root / 'adapter.sqlite3', config=AdapterConfig(True),
                                     transport=self.transport)
        self.intake = Mock()
        self.runner = Runner(self.root / 'operations', self.intake, Mock())
        self.pilot = Pilot(self.root)

    def pending(self):
        with state_lock(self.root):
            _write_state(self.root, 'pending')

    def test_preexisting_instances_cannot_dispatch_or_mutate_pending_restore(self):
        operations = {
            'workflow register': lambda: self.workflow.register(self.source),
            'workflow run': lambda: self.workflow.run([self.ticket]),
            'workflow current': lambda: self.workflow.current(self.ticket),
            'workflow shadow': lambda: self.workflow.shadow(WorkItem(self.ticket, (self.ticket, None))),
            'workflow capture': lambda: self.workflow.capture(self.ticket, self.adapter, 'a' * 64,
                                                              expected_candidate_version=self.candidate.digest),
            'workflow bind': lambda: self.workflow.bind_result_request(self.ticket,
                                                                       expected_candidate_version=self.candidate.digest),
            'intake read': lambda: self.workflow.intake.status(self.ticket),
            'intake claim': lambda: self.workflow.intake.claim(self.ticket),
            'intake materialize': lambda: self.workflow.intake.materialize(self.ticket),
            'holds read': lambda: self.holds.load(self.ticket),
            'holds create': lambda: self.holds.create(self.ticket, 'needs_recheck', self.source),
            'holds update': lambda: self.holds.update(self.hold, status='dismissed'),
            'actions': lambda: self.workflow.actions.candidate_version(self.ticket),
            'decisions': lambda: self.workflow.decisions.record(self.ticket, self.candidate.record),
            'review retry': lambda: self.reviewer.retry(self.hold),
            'review draft': lambda: self.reviewer.draft(self.hold, b'Synthetic draft'),
            'review dismiss': lambda: self.reviewer.dismiss(self.hold),
            'managed read': lambda: managed(self.root, self.ticket),
            'runner': self.runner.run,
            'adapter read': lambda: self.adapter.captured('a' * 64),
            'adapter submit': lambda: self.adapter.submit({}, {}, expected_candidate_digest='',
                                                          expected_decision_digest=''),
            'pilot start': self.pilot.start,
            'pilot submit': lambda: self.pilot.submit('summary', mode='shadow'),
            'pilot pause': self.pilot.pause,
            'pilot stop': self.pilot.stop,
            'legacy triage': lambda: triage.recheck(self.root, self.hold, b'Synthetic draft'),
        }
        self.pending()
        for name, operation in operations.items():
            with self.subTest(api=name), self.assertRaises(RecoveryError):
                operation()
        for operation in (lambda: self.workflow.candidates.load(self.ticket),
                          lambda: self.workflow.candidates.save(self.candidate, 'General', 'General draft.',
                                                                'needs_local_review')):
            with self.assertRaises(ReviewError):
                operation()
        self.transport.assert_not_called()
        self.intake.poll.assert_not_called()

    def test_constructors_and_legacy_output_writers_refuse_pending_restore(self):
        self.pending()
        constructors = [lambda: ShadowWorkflow(self.root), lambda: IntakeLedger(self.root),
                        lambda: HoldStore(self.root), lambda: Reviewer(self.root),
                        lambda: ActionStore(self.root / 'actions.sqlite3'),
                        lambda: DecisionStore(self.root / 'routing'),
                        lambda: ClaudeAdapter(self.root / 'adapter.sqlite3'),
                        lambda: Runner(self.root / 'operations', Mock(), Mock())]
        for constructor in constructors:
            with self.subTest(constructor=constructor), self.assertRaises(RecoveryError):
                constructor()
        with self.assertRaises(ReviewError):
            CandidateStore(self.root)
        with patch.object(scrubber, 'STATE', self.root), patch('builtins.input') as prompt:
            for operation in (lambda: scrubber.process(b'Synthetic'),
                              lambda: scrubber.save_candidate(self.candidate.record, self.root),
                              lambda: scrubber.save_status({}), lambda: scrubber.gmail(1, {})):
                with self.assertRaises(RecoveryError):
                    operation()
            prompt.assert_not_called()

    def test_worker_source_reads_use_preloaded_bindings_without_lock_reentry(self):
        # Source/model workers are intentionally different threads. DB lookups
        # stay on their guarded caller thread, preventing a reentrant-lock deadlock.
        caller = threading.get_ident()
        original = self.workflow.intake.private_source
        def local_binding(ticket):
            self.assertEqual(threading.get_ident(), caller)
            return original(ticket)
        with patch.object(self.workflow.intake, 'private_source', side_effect=local_binding):
            self.assertEqual(self.workflow.current(self.ticket)[1].outcome, 'WOULD_SEND')

    def test_real_restore_is_inactive_at_direct_apis_until_acknowledged(self):
        backup = Path(self.temp.name) / 'snapshot'
        restored = Path(self.temp.name) / 'restored'
        snapshot(self.root, backup)
        restore(backup, restored)
        for constructor in (lambda: ShadowWorkflow(restored), lambda: Reviewer(restored),
                            lambda: Runner(restored / 'operations', Mock(), Mock()),
                            lambda: Pilot(restored / 'auxiliary')):
            with self.assertRaises(RecoveryError):
                constructor()
        from operations import acknowledge_restore as acknowledge_legacy
        with self.assertRaises(RecoveryError):
            acknowledge_legacy(restored / 'operations')
        acknowledge_restore(restored, operator_acknowledged=True, reconciliation_recorded=True)
        reopened = ShadowWorkflow(restored)
        self.assertEqual(reopened.candidates.load(self.ticket).digest, self.candidate.digest)
        self.assertEqual(reopened.current(self.ticket)[1].outcome, 'WOULD_SEND')
        self.assertEqual(reopened.run([self.ticket]).attempted, 0)


if __name__ == '__main__':
    unittest.main()
