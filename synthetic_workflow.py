"""Built-in temporary integration fixture. No real source or transport accepted."""
from contextlib import contextmanager
from dataclasses import asdict
from email.message import EmailMessage
import json
from pathlib import Path
import socket
import tempfile
from unittest.mock import patch

from claude_adapter import (AdapterConfig, ClaudeAdapter, FakeTransport,
                            decision_digest, payload_digest)
from holds import file_source
import scrubber
from shadow_workflow import ShadowWorkflow, WorkflowError


PAYLOAD = {'subject': 'Workflow', 'body': 'Explain general follow-up workflow.'}
MODEL_DIGEST = 'a' * 64


@contextmanager
def synthetic_checks():
    """Mock only Ollama wire responses; run real parse/redact/audit validators."""
    def api(route, payload=None):
        if route == '/api/tags':
            return {'models': [{'name': scrubber.MODEL, 'digest': MODEL_DIGEST}]}
        if route == '/api/show':
            return {}
        if route != '/api/chat':
            raise AssertionError('unexpected_model_route')
        result = ({'suspected_phi': False, 'uncertain': False}
                  if payload['format'] == scrubber.CHECK_SCHEMA else {**PAYLOAD, 'uncertain': False})
        return {'done': True, 'done_reason': 'stop', 'message': {'content': json.dumps(result)}}

    with patch.object(scrubber, 'api', side_effect=api), \
            patch.object(socket.socket, 'connect', side_effect=AssertionError('network_forbidden')), \
            patch.object(socket.socket, 'connect_ex', side_effect=AssertionError('network_forbidden')):
        yield


def fixture(path):
    mail = EmailMessage()
    mail['Subject'] = 'Synthetic workflow'
    mail['From'] = 'synthetic@example.test'
    mail.set_content(PAYLOAD['body'])
    raw = mail.as_bytes()
    Path(path).write_bytes(raw)
    return file_source(Path(path), raw)


def submit_fixture(workflow, ticket, adapter):
    """Separate fake-only test authorization, never translate a shadow decision.

    No arbitrary payload, provider client or injected transport is accepted.
    The explicit release contract below applies only to this constant fixture.
    """
    if type(adapter) is not ClaudeAdapter or type(adapter.transport) is not FakeTransport:
        raise WorkflowError('fake_transport_required')
    snapshot = workflow.candidates.load(ticket)
    if snapshot.record != {'status': 'needs_local_review', **PAYLOAD}:
        raise WorkflowError('synthetic_fixture_required')
    key = workflow.bind_result_request(ticket, expected_candidate_version=snapshot.digest)
    authorization = {'eligible': True, 'mode': 'release', 'policy_version': 'synthetic-fixture-v1',
                     'candidate_digest': payload_digest(PAYLOAD)}
    result = adapter.submit(PAYLOAD, authorization,
                            expected_candidate_digest=payload_digest(PAYLOAD),
                            expected_decision_digest=decision_digest(authorization),
                            request_scope=ticket)
    return key, snapshot.digest, result


def demo():
    with tempfile.TemporaryDirectory(prefix='synthetic-shadow-') as temp, synthetic_checks():
        root = Path(temp)
        workflow = ShadowWorkflow(root / 'state')
        source = fixture(root / 'synthetic.eml')
        ticket = workflow.register(source)
        report = workflow.run([ticket])
        duplicate = workflow.run([workflow.register(source)])
        # Shadow has finished. This independent test uses its own explicit
        # synthetic-only authorization and the built-in FakeTransport.
        adapter = ClaudeAdapter(root / 'adapter.sqlite3', config=AdapterConfig(True),
                                transport=FakeTransport())
        key, version, response = submit_fixture(workflow, ticket, adapter)
        proposal = workflow.capture(ticket, adapter, key, expected_candidate_version=version)
        return {'mode': 'synthetic_mocked_contract', 'shadow': asdict(report),
                'duplicate_attempts': duplicate.attempted, 'adapter': response.status,
                'local_proposals': len(proposal['proposals']), 'network_enabled': False,
                'release_enabled': False, 'live_model_tested': False}
