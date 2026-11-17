"""Pure ResultV1 validation and canonical ASCII JSON; no authorization or state."""
import json


KINDS = frozenset({'summarize', 'suggest_organization', 'draft_reply'})
MAX_RESULT_BYTES = 128_000


def canonical_result(value):
    """Return canonical bytes as text, or a fixed ValueError category."""
    if (type(value) is not dict or set(value) != {'schema_version', 'actions'}
            or type(value['schema_version']) is not int or value['schema_version'] != 1
            or type(value['actions']) is not list or not 1 <= len(value['actions']) <= 20):
        raise ValueError('invalid_result')
    for action in value['actions']:
        if (type(action) is not dict or set(action) != {'kind', 'text'}
                or type(action['kind']) is not str or action['kind'] not in KINDS
                or type(action['text']) is not str or not action['text'].strip()):
            raise ValueError('invalid_result')
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    if len(encoded) > MAX_RESULT_BYTES:
        raise ValueError('result_too_large')
    return encoded
