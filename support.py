"""Content-free local diagnostics. Never reads mail, runtime state or credentials."""
import argparse
import json
import platform
import sys
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

VERSION = '0.1.0-dev'
MODEL = 'qwen3.5:9b-q4_K_M'
ENDPOINT = 'http://127.0.0.1:11434'
MAX_RESPONSE = 65536
CODES = frozenset({
    'PYTHON_OK', 'PYTHON_UNSUPPORTED', 'MODEL_OK', 'MODEL_NOT_CHECKED',
    'MODEL_UNAVAILABLE', 'MODEL_MISSING', 'MODEL_REMOTE_REJECTED',
    'MODEL_RESPONSE_INVALID', 'EMAIL_NOT_CHECKED', 'ROUTING_NOT_CHECKED',
    'CLAUDE_NOT_CHECKED', 'SYNTHETIC_NOT_CHECKED',
})


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_json(route, payload=None):
    """Only fixed model metadata routes, bounded response, no proxies/redirects."""
    if (route, payload is None) not in {('/api/tags', True), ('/api/show', False)}:
        raise ValueError('unsupported route')
    if payload is not None and payload != {'model': MODEL}:
        raise ValueError('unsupported payload')
    data = None if payload is None else json.dumps(payload).encode('ascii')
    opener = build_opener(ProxyHandler({}), NoRedirect())
    req = Request(ENDPOINT + route, data=data,
                  headers={'Content-Type': 'application/json'})
    with opener.open(req, timeout=5) as response:
        raw = response.read(MAX_RESPONSE + 1)
    if len(raw) > MAX_RESPONSE:
        raise ValueError('response too large')
    return json.loads(raw)


def model_code():
    try:
        tags = request_json('/api/tags')
        if not isinstance(tags, dict) or not isinstance(tags.get('models'), list):
            return 'MODEL_RESPONSE_INVALID'
        if any(not isinstance(item, dict) for item in tags['models']):
            return 'MODEL_RESPONSE_INVALID'
        selected = next((item for item in tags['models']
                         if item.get('name') == MODEL), None)
        if selected is None:
            return 'MODEL_MISSING'
        details = request_json('/api/show', {'model': MODEL})
        if not isinstance(details, dict):
            return 'MODEL_RESPONSE_INVALID'
        if any(item.get(key) for item in (selected, details)
               for key in ('remote_host', 'remote_model')):
            return 'MODEL_REMOTE_REJECTED'
        if not isinstance(details.get('details'), dict):
            return 'MODEL_RESPONSE_INVALID'
        return 'MODEL_OK'
    except (ValueError, TypeError, KeyError):
        return 'MODEL_RESPONSE_INVALID'
    except Exception:
        # Exception text can include paths, addresses, server bodies or secrets.
        return 'MODEL_UNAVAILABLE'


def diagnose(probe_model=False):
    system = platform.system()
    os_family = system if system in {'Windows', 'Linux', 'Darwin'} else 'Other'
    return {
        'schema_version': 1,
        'software_version': VERSION,
        'os_family': os_family,
        'python_series': f'{sys.version_info.major}.{sys.version_info.minor}',
        'codes': [
            'PYTHON_OK' if sys.version_info[:2] == (3, 13) else 'PYTHON_UNSUPPORTED',
            model_code() if probe_model else 'MODEL_NOT_CHECKED',
            'EMAIL_NOT_CHECKED', 'ROUTING_NOT_CHECKED', 'CLAUDE_NOT_CHECKED',
            'SYNTHETIC_NOT_CHECKED',
        ],
    }


def validate_report(report):
    """Reject unknown fields/values rather than attempting to redact them."""
    if type(report) is not dict or set(report) != {
        'schema_version', 'software_version', 'os_family', 'python_series', 'codes'
    }:
        raise ValueError('invalid report')
    if type(report['schema_version']) is not int or report['schema_version'] != 1:
        raise ValueError('invalid schema')
    if report['software_version'] != VERSION:
        raise ValueError('invalid version')
    if report['os_family'] not in ('Windows', 'Linux', 'Darwin', 'Other'):
        raise ValueError('invalid system')
    # Only numeric major/minor; never arbitrary build/platform strings.
    series = report['python_series']
    if type(series) is not str or len(series) > 7 or len(series.split('.')) != 2:
        raise ValueError('invalid Python series')
    if any(not part.isascii() or not part.isdecimal() for part in series.split('.')):
        raise ValueError('invalid Python series')
    codes = report['codes']
    if type(codes) is not list or len(codes) > len(CODES) or any(
        type(code) is not str or code not in CODES for code in codes
    ):
        raise ValueError('invalid codes')


def issue_draft(report):
    validate_report(report)
    return ('## Setup diagnostics\n\n```json\n' + json.dumps(report, indent=2)
            + '\n```\n\nThis is a diagnostic draft, not a compliance assessment. '
            'No message content, logs, paths or credentials were collected.\n'
            'Review before submitting. No issue has been sent.\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('doctor', 'report'))
    parser.add_argument('--probe-model', action='store_true',
                        help='query fixed numeric loopback model metadata only')
    args = parser.parse_args(argv)
    report = diagnose(args.probe_model)
    print(issue_draft(report) if args.command == 'report'
          else json.dumps(report, indent=2))
    return int(any(code in report['codes'] for code in (
        'PYTHON_UNSUPPORTED', 'MODEL_UNAVAILABLE', 'MODEL_MISSING',
        'MODEL_REMOTE_REJECTED', 'MODEL_RESPONSE_INVALID')))


if __name__ == '__main__':
    sys.exit(main())
