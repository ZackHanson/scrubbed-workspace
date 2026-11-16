# Claude adapter contract (synthetic only)

`claude_adapter.py` has no API client, network code, credential handling, CLI,
environment activation or integration with intake/review. It does not send mail.
No Anthropic API/model/account was selected. `FakeTransport` is deterministic.

Configuration is explicit Python `AdapterConfig(enabled=False,
timeout_seconds=30.0)`. Timeout must be finite, greater than zero and at most 120
seconds. Enabling requires an injected callable; no default remote transport
exists. The ledger path must be explicitly provided in approved local state;
tests use temporary directories. Disabled calls do not create/open that store.

`submit(payload, decision, *, expected_candidate_digest,
expected_decision_digest)` requires exactly `subject` and `body` strings in the
payload. No candidate status, ID, routing map, source reference, addresses,
credential, filename or raw MIME field belongs here. Local identifier patterns
and routing-header checks provide additional rejection, not de-identification
certification. They cannot identify every name, street address or private detail.
Only upstream trusted local policy can decide content is eligible.

Decision fields are exactly:

- `eligible`: a boolean, which must be true for submission.
- `mode`: `shadow` or `release`; only `release` permits submission.
- `candidate_digest`: `payload_digest(payload)`.
- `policy_version`: lowercase alphanumeric slug with dots, underscores or hyphens,
  maximum 64 characters.

`decision_digest(decision)` computes the decision binding. Digests use SHA-256
of sorted ASCII JSON with compact separators. The content digest covers only
subject/body; it is **not** `CandidateStore.Snapshot.digest` (file-byte hash).
The caller must reload/verify the current candidate and trusted policy decision
under its own lock before supplying expected digests. These hashes are not a
signature or authorization token. Never let email text or a model self-authorize
by constructing its own decision. Review markers alone confer no eligibility.
Routing integration must project its richer decision into this contract, verify
current eligibility/freshness/revocation, and keep the private routing map local.
An old eligible decision is not invalidated automatically by this standalone module.

Transport signature: `transport(payload, *, timeout_seconds, idempotency_key)`.
It receives only copied subject/body and an opaque content-derived key, never
decision metadata or local identifiers. It must honor the timeout itself. A
daemon worker bounds caller waiting; Python cannot cancel an arbitrary callable,
so timed-out work may still finish. No thread can trigger a second submission.
Transport code must not log payloads, credentials or exception text.

Transport response is exactly `{'result': ResultV1, 'stop_reason': str}`. Stop reasons
are `end_turn`, `max_tokens`, `refusal`. ResultV1 is exactly
`{'schema_version': 1, 'actions': [{'kind': KIND, 'text': NONEMPTY_STRING}]}`,
with 1–20 actions, kinds `summarize`, `suggest_organization`, `draft_reply`, and
a 128 KiB limit on compact canonical ASCII JSON. Unknown/routing fields are
rejected at every level. Reply text is body-only; actions validation must also
check content before proposing it. `AdapterResult` returns status/code/key plus
the copied untrusted `result` object and stop reason; result is excluded from
repr, never persisted by the adapter. Completed
means a valid response was received, not that an action/reply is authorized.
Truncation/refusal remain explicit for downstream handling. Result consumers must
keep response content local and validate it before any action.

The local integration caller passes `AdapterResult.result` to
`ActionStore.capture_result(candidate_id, candidate_version, result_id,
result_version, result, expected_result_id=None)`. Candidate/result IDs and
versions must come from the caller's LOCAL request ledger, never model echo.
The adapter deliberately accepts none of those identifiers in the wire payload.
`result_digest()` in actions uses the same canonical JSON encoding, but covers
the ResultV1 object rather than content or eligibility. Response persistence,
CAS replacement and inert proposals belong to actions; no automatic capture or
reply is wired here. Only `completed` with `end_turn` should advance to normal
capture; truncation/refusal/unknown need explicit local exception handling.

SQLite stores only submission hashes and fixed statuses. Atomic unique insertion
reserves a content key before calling transport, across threads/process restarts.
The key is stable across decision changes to prevent policy changes bypassing
unknown delivery. Duplicate calls return no cached response. Timeouts, exceptions,
invalid responses and interrupted processes retain reservations and never retry.
Storage failure blocks a new submission; final update failure reports unknown.
There is intentionally no reset/retry API. Future production integration needs a
local operator/provider reconciliation workflow and response persistence contract
before retries or real delivery can be enabled. This ledger is adapter-specific;
other schedulers must not automatically retry `unknown` results.

No current application path imports this adapter. Remote calls, real releases,
reply sending and background schedules remain inactive.
