"""Both trust boundaries accept identical wire data and retain domain errors."""
import json
import unittest

from actions import ActionError, _result, result_digest
from claude_adapter import ContractError, _action_result
from result_v1 import canonical_result


class ResultV1Tests(unittest.TestCase):
    def test_canonical_ascii_and_action_order_match_at_both_boundaries(self):
        value = {'actions': [{'text': '\u2603 General workflow.', 'kind': 'summarize'},
                             {'kind': 'draft_reply', 'text': 'General draft.'}], 'schema_version': 1}
        encoded = canonical_result(value)
        encoded.encode('ascii')
        self.assertEqual(_result(value), encoded)
        self.assertEqual(_action_result(value), json.loads(encoded))
        self.assertEqual(_result(_action_result(value)), encoded)
        self.assertNotEqual(result_digest(value), result_digest({**value, 'actions': value['actions'][::-1]}))

    def test_invalid_structures_fail_with_fixed_domain_errors(self):
        good = {'schema_version': 1, 'actions': [{'kind': 'summarize', 'text': 'General'}]}
        for value in (None, [], {**good, 'schema_version': True}, {**good, 'extra': 'untrusted'},
                      {**good, 'actions': []}, {**good, 'actions': good['actions'] * 21},
                      *({**good, 'actions': [action]} for action in (
                          {'kind': 'send_email', 'text': 'General'}, {'kind': [], 'text': 'General'},
                          {'kind': 'summarize', 'text': '  '}, {'kind': 'summarize', 'text': 1},
                          {'kind': 'summarize', 'text': 'General', 'to': 'untrusted'}))):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ActionError, '^invalid_result$'):
                    _result(value)
                with self.assertRaisesRegex(ContractError, '^invalid_response$'):
                    _action_result(value)

    def test_canonical_byte_limit_includes_escaped_unicode_and_envelope(self):
        envelope = {'schema_version': 1, 'actions': [{'kind': 'summarize', 'text': 'x'}]}
        overhead = len(canonical_result(envelope)) - 1
        envelope['actions'][0]['text'] = 'x' * (128_000 - overhead)
        self.assertEqual(len(_result(envelope)), 128_000)
        self.assertEqual(_action_result(envelope), envelope)
        for text in (envelope['actions'][0]['text'] + 'x', '\u2603' * 22_000):
            envelope['actions'][0]['text'] = text
            with self.assertRaisesRegex(ActionError, '^result_too_large$'):
                _result(envelope)
            with self.assertRaisesRegex(ContractError, '^invalid_response$'):
                _action_result(envelope)
