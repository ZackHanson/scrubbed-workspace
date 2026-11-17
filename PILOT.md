# Bounded Claude pilot preparation

Owner decision, November 16: **prepare without submitting requests**. This change
does not authorize a live run. No account, model, credential, or spend has been
selected. Import, default CLI, dry run and shadow never create a provider client.
Existing routing, adapter defaults, desktop workflow and release policy are unchanged.

## Ready-to-run preparation (no network, key, account or spend)

From this source checkout:

```powershell
python claude_pilot.py
python claude_pilot.py shadow --request reply
python verify_synthetic.py
```

The first two commands print only fixed status/fixture/count receipts. They do not
create state. The test runner blocks sockets and redirects application state to
temporary storage; the new tests additionally mock every HTTPS connection.
Do not run `run` during preparation. Do not inspect actual private runtime through
a cloud agent. No Gmail connection, local-model inference, real email, arbitrary
input file, candidate, identifying reference, service or schedule is needed.

The only accepted request IDs are the five built-in, invented, nonclinical tasks:

| ID | Fixed request |
| --- | --- |
| summary | Summarize an imaginary office workshop plan |
| organize | Organize an imaginary stationery cupboard |
| reply | Draft a body-only thank-you for an imaginary reading club |
| checklist | Suggest a practice-presentation checklist |
| compare | Compare filing methods for imaginary office templates |

The exact text is declared in `claude_pilot.py:_FIXTURES`. There is no inbox,
file-content, arbitrary text, attachment, HTML, source-record or general release
input. `fixture()` returns copies. The transport independently checks that its
payload equals one of these five fixtures. Trusted fixture authorization uses the
unchanged `ClaudeAdapter` digest and release-decision contract; it does not convert
a shadow decision or local review marker into release authorization.

## Future operator procedure (requires a separate live-run decision)

Before any future run, the owner must choose and approve:

- A first-party Anthropic Console account/workspace with API access and an approved
  key scoped to that workspace (or the explicit workspace header).
- The exact Claude API model ID available to that account; prefer a pinned model
  where offered. No default model, account or alternative platform is selected.
- Current pricing, acceptable spend, and `max_tokens` (1–1024 per attempt, default
  512). There are at most five attempts. The local budget limits attempts and output
  tokens, **not dollars**; input tokens and unsuccessful/unknown requests may cost
  money. Set any desired monetary limit in the approved provider account separately.
- One owner-selected empty private state directory outside all Git source trees,
  retained for the entire pilot, under existing private filesystem permissions.
  This module does not install permissions, backups, services or security settings.

After that decision, create/select that private directory locally. The following
is a command template for **one** explicit start and **one** fixture; replace the
three placeholders only with nonsecret local state/account/model selections:

```powershell
python claude_pilot.py run --state "<private pilot directory>" --account "<approved-account-alias>" --model "<approved-exact-model-id>" --approve-spend --request summary --max-tokens 512
```

The account alias is a nonsecret local approval label, not authentication or proof
of billing identity. The key must belong to the owner-approved account. For an
unscoped key, also supply `--workspace-id <approved-workspace-id>`. This is only the
first-party Anthropic API; Claude subscriptions, Bedrock, Foundry, gateways,
proxies and other auth mechanisms are not supported or silently substituted.

The command prompts using an echo-free native terminal prompt. If secure prompting
is unavailable, it fails. Never put a key in CLI arguments, shell history,
environment variables, source, logs, result files or chat. For a trusted local
parent using secure secret delivery, the memory-only API is:

```python
# Local operator code only. approved_config is a PilotConfig with explicit
# enabled=True, spend_approved=True, account/model/workspace selections.
# memory_key comes directly from secure secret delivery; never a CLI token.
transport = AnthropicHTTPS(approved_config, api_key=memory_key)
pilot = Pilot(selected_private_root, approved_config, transport=transport)
try:
    receipt = pilot.start()
    if receipt['status'] == 'started':
        receipt = pilot.submit('summary', mode='pilot')
finally:
    pilot.pause()
# Only the content-free receipt may be reported back to a cloud coordinator.
```

`getpass` is the supplied CLI route. Secure delivery integration is the parent's
responsibility; no secret file, credential manager or account access is provisioned
here. Python cannot guarantee erasure of immutable strings from process memory.
Transport/config representations and caught exceptions omit credentials. Provider
error bodies are not read. Literal and JSON-escaped credential echoes are rejected
before results are persisted. No debugging or HTTP wire logging should be enabled.

For each remaining unused fixture, make another explicit operator invocation using
the **same directory and configuration**. Successful CLI exit pauses the session.
Duplicate fixture IDs never resubmit. A terminal stop is:

```powershell
python claude_pilot.py stop --state "<same private pilot directory>"
```

Stop forbids subsequent reservations. A request already reserved/dispatched cannot
be recalled or guaranteed cancelled remotely. Timeout may leave an adapter worker
finishing the bounded HTTPS call; the pilot is terminal and dispatches no more.
There is no automatic retry, backoff, redirect, proxy fallback, reset, reconcile-
and-resend, or background startup. Do not delete/copy/change the state directory to
get another budget. The bound is local durable state, not an account-wide or
tamper-resistant provider quota.

## Durable behavior and local results

`pilot.sqlite` holds the pilot session/config fingerprint, content-free attempt
receipts, the adapter's reservation/captured results and ActionStore's inert
proposals. There are no result exports or result text in CLI output. Review result
text only locally in the selected private state, as untrusted content; do not
print it into a cloud-agent session. No file with the invented `.eml` source name
is created or read; it is solely an invented local ActionStore binding. Results
can contain unwanted content and must not be executed or automatically acted on.

SQLite's immediate transactions and FULL synchronous mode reserve each fixture
before adapter/thread/network creation, incrementing the total at that point.
Stable fixture scopes do not contain model/account/policy/retry values. A clean
pause permits unused fixtures after another explicit start, while duplicates stay
reserved. An unclean active session, unknown attempt, refusal, truncation, invalid
schema, provider/transport error, failed capture/proposal persistence, budget
exhaustion, or changed configuration/policy/fixtures/system prompt halts the state.
Even an error before a request reaches the provider conservatively consumes its
reservation. Changes cannot reset the budget or resubmit a prior request. A crash
after reservation cannot be distinguished from successful remote execution;
manual reconciliation is read-only and must never resend it.

One request can be reserved at a time. A concurrent second request while another
is unknown halts the pilot; it does not dispatch a second call. Another process
trying to start an active session also halts. No process locks are removed by
timeout. Preserve the entire selected state for local recovery; source publication
does not back it up. Include its `pilot.sqlite` explicitly as an extra ledger in
the coordinated snapshot API; it contains pilot, adapter and action/result tables.

## Protocol and primary-source verification

Verified November 16, 2026 against Anthropic primary documentation:

- [API overview](https://platform.claude.com/docs/en/api/overview): first-party
  HTTPS origin, supported `x-api-key`, version/content headers and workspace header.
- [Messages API](https://platform.claude.com/docs/en/api/messages/create):
  `POST /v1/messages`, explicit model, `max_tokens`, user text, assistant text blocks
  and `end_turn` completion. This pilot pins `anthropic-version: 2026-10-21`.
- [Model overview](https://platform.claude.com/docs/en/models/overview) and
  [pricing](https://platform.claude.com/docs/en/about-claude/pricing): the operator
  must verify the desired model's availability, exact ID and price before spending.

The standard-library `http.client.HTTPSConnection` uses verified TLS directly to
`api.anthropic.com:443` and the fixed `/v1/messages` path. No URL/endpoint option,
proxy environment lookup, redirect handler, tool declaration, stream, remote
resource, fallback or retry exists. Requests are capped at 16,384 bytes; responses
at 65,536 bytes, uncompressed JSON only; socket/deadline and adapter timeouts are
bounded at 1–60 seconds. Adapter wall timeout can precede the worker's eventual
socket termination (DNS/slow header handling are OS/library limited); durable halt
prevents overlapping follow-on calls. No unbounded provider error body is read.
Successful output must match the approved model ID exactly, contain one text block,
finish with `end_turn`, and decode to strict ResultV1. Models requiring thinking
blocks or resolving aliases differently will fail closed; there is no parser retry.
Provider protocol/model compatibility is **not live-tested** by this source work.

## Recovery integration and evidence

The combined build requires `recovery_guard.require_active` and `active_state`;
there is no missing-module fallback. Restored pending state blocks construction,
reads and calls on preexisting pilot objects. Enabled initialization and dispatch
hold the canonical state lock. Disabled/dry-run calls retain no-files behavior.

Exact integration callsites already prepared:

- `Pilot._db`: active-state guard around every mutation of `root/pilot.sqlite`.
- `Pilot.submit(mode='pilot')`: outer active-state guard around reservation,
  adapter dispatch, capture, proposal and final receipt. `_db` nests in the same
  thread, using the shared reentrant lock. Concurrent dispatch is refused busy.
- `Pilot.start`: read-check before any initialization, then guard the full start.
  `pause` and `stop` check the fence and guard their complete persistent DB updates;
  dry run/shadow do not create state.

Any future provider activation still requires its separate account/model/spend
decision. The combined suite tests the actual recovery guard and
direct restored workflow/store/pilot entrypoints. The `transport=` API is trusted local test injection, not an untrusted
plugin or external payload interface.

Validation: new deterministic pilot tests cover five-request exhaustion, restart
and duplicate fencing, simulated interruption after reservation, unknown/timeouts,
concurrent attempts, explicit stop, config/policy/digest changes, private paths,
shadow isolation, approval defaults, strict payload/result parsing, provider errors,
TLS origin, sizes, and credential/error sanitization. All data is invented and
temporary. Final test counts and source SHA are recorded in Current work and the
PR. No real request or credential was used; no privacy certification or general
release approval is implied.
