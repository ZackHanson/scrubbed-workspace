"""Focused built-in synthetic replays and independent generalization probes."""
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import scrubber as s
from .corpus import Fixture, corpus, message
from .runner import assess, live_guard


def examples():
    return (
        Fixture('extra-context-01', 'rare_context', message(
            'A six-fingered prize-winning ice sculptor requests a general allergy education checklist.').as_bytes(),
            (('allergy',), ('checklist',)), ('six-fingered', 'prize-winning', 'ice sculptor')),
        Fixture('extra-context-02', 'rare_context', message(
            'The sole unicycle repairer and regional sand painting finalist asks for general back pain prevention education.').as_bytes(),
            (('back pain',), ('prevention',)), ('unicycle', 'sand painting', 'finalist')),
        Fixture('extra-scope-01', 'scope', message(
            'Compare general nutrition approaches for fatigue. No supplements or laboratory testing is requested.').as_bytes(),
            (('nutrition',), ('fatigue',), ('no supplements or laboratory testing',))),
        Fixture('extra-scope-02', 'scope', message(
            'Prepare a general knee rehabilitation education checklist; do not recommend injections.').as_bytes(),
            (('knee',), ('rehabilitation',), ('do not recommend injections',))),
    )


def run():
    rows, audits = [], []
    with tempfile.TemporaryDirectory(prefix='scrubbed-focused-') as folder, ExitStack() as stack:
        stack.enter_context(patch.object(s, 'STATE', Path(folder)))
        digest = stack.enter_context(live_guard())
        fixtures = tuple(f for f in corpus() if f.id in ('context-01', 'utility-05')) + examples()
        for fixture in fixtures:
            record, reason = None, None
            try:
                record = s.scrub(fixture.raw)
            except s.Blocked as blocked:
                reason = blocked.code
            rows.append(assess(fixture, record, reason))
        # Test the auditor independently: a better redactor must not hide a blind spot.
        probes = (
            ('audit-reproduction', 'A left-handed glass harp champion needs a general migraine prevention summary.', True),
            ('audit-extra', 'A six-fingered prize-winning ice sculptor requests general allergy education.', True),
            ('audit-clean', 'Prepare general allergy education. No diagnosis is requested.', False),
        )
        for id, body, expected in probes:
            check = s.llm(s.AUDIT_SYSTEM, {'subject': 'General request', 'body': body}, s.CHECK_SCHEMA)
            audits.append({'probe_id': id, 'passed': (check['suspected_phi'] or check['uncertain']) == expected})
        if list(Path(folder).iterdir()):
            raise RuntimeError('unexpected_evaluation_state')
    return {'scope': 'synthetic_regression_only', 'certification': False,
            'model_digest': digest, 'fixtures': rows, 'audits': audits,
            'passed': all(r['privacy'] == r['utility'] == r['schema'] == 'pass' for r in rows)
                      and all(r['passed'] for r in audits)}


if __name__ == '__main__':
    try:
        receipt = run()
    except Exception:
        receipt = {'passed': False, 'error': 'evaluation_unavailable'}
    print(json.dumps(receipt, sort_keys=True))
    raise SystemExit(0 if receipt['passed'] else 1)
