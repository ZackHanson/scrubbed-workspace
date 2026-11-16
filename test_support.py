import contextlib
import io
import json
import unittest
from unittest.mock import patch, Mock
import support


class SupportTests(unittest.TestCase):
    def test_default_never_reads_state_or_network(self):
        with patch('builtins.open', side_effect=AssertionError('private read')), \
             patch('socket.socket', side_effect=AssertionError('network')):
            report = support.diagnose()
            support.validate_report(report)
            self.assertIn('MODEL_NOT_CHECKED', report['codes'])
            self.assertIn('CLAUDE_NOT_CHECKED', report['codes'])

    def test_exception_content_never_leaves(self):
        secret = 'patient@example.invalid C:/private/record token=SECRET'
        with patch.object(support, 'request_json', side_effect=RuntimeError(secret)):
            report = support.diagnose(True)
        draft = support.issue_draft(report)
        self.assertNotIn(secret, draft)
        self.assertIn('MODEL_UNAVAILABLE', draft)

    def test_model_results(self):
        cases = [
            ([{'models': []}], 'MODEL_MISSING'),
            ([{'models': 'private'}], 'MODEL_RESPONSE_INVALID'),
            ([{'models': [None]}], 'MODEL_RESPONSE_INVALID'),
            ([{'models': [{'name': support.MODEL}]}, {}], 'MODEL_RESPONSE_INVALID'),
            ([{'models': [{'name': support.MODEL}]}, {'details': {}}], 'MODEL_OK'),
            ([{'models': [{'name': support.MODEL, 'remote_host': 'private'}]},
              {'details': {}}], 'MODEL_REMOTE_REJECTED'),
            ([{'models': [{'name': support.MODEL}]}, {'remote_model': 'private'}],
             'MODEL_REMOTE_REJECTED'),
        ]
        for responses, expected in cases:
            with self.subTest(expected=expected), patch.object(
                support, 'request_json', side_effect=responses
            ):
                self.assertEqual(support.model_code(), expected)

    def test_report_rejects_arbitrary_content(self):
        for key, value in [('extra', 'secret'), ('codes', ['secret']),
                           ('python_series', 'private'), ('os_family', 'hostname'),
                           ('software_version', 'token'), ('schema_version', True)]:
            report = support.diagnose()
            report[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                support.issue_draft(report)

    def test_platform_details_are_not_collected(self):
        with patch.object(support.platform, 'system', return_value='private host'):
            self.assertEqual(support.diagnose()['os_family'], 'Other')

    def test_transport_bounds_and_no_proxy(self):
        response = Mock()
        response.read.return_value = b'{}'
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        opener = Mock()
        opener.open.return_value = response
        with patch.object(support, 'build_opener', return_value=opener) as build:
            support.request_json('/api/tags')
        self.assertEqual(build.call_args.args[0].proxies, {})
        self.assertIsInstance(build.call_args.args[1], support.NoRedirect)
        self.assertEqual(opener.open.call_args.kwargs, {'timeout': 5})
        self.assertEqual(opener.open.call_args.args[0].full_url,
                         'http://127.0.0.1:11434/api/tags')
        response.read.assert_called_once_with(support.MAX_RESPONSE + 1)
        response.read.return_value = b'x' * (support.MAX_RESPONSE + 1)
        with patch.object(support, 'build_opener', return_value=opener):
            with self.assertRaises(ValueError):
                support.request_json('/api/tags')

    def test_arbitrary_routes_and_payloads_rejected(self):
        for route, payload in [('https://example.invalid', None),
                               ('/api/show', {'model': 'other'})]:
            with self.assertRaises(ValueError):
                support.request_json(route, payload)

    def test_cli_failures_are_nonzero_and_parseable(self):
        with patch.object(support, 'model_code', return_value='MODEL_UNAVAILABLE'), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(support.main(['doctor', '--probe-model']), 1)
        self.assertIn('MODEL_UNAVAILABLE', json.loads(output.getvalue())['codes'])


if __name__ == '__main__':
    unittest.main()
