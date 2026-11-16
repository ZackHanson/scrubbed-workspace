# Troubleshooting by fixed diagnostic code

Use this guide from the same release/commit as the software. No repair requires
sharing original mail, candidates, screenshots, runtime storage or credentials
with an AI. Do not disable gates or use a remote model to repair a failure.

| Code | Meaning and next step | Recheck |
| --- | --- | --- |
| PYTHON_OK | Python 3.13 series is selected. No action. | doctor |
| PYTHON_UNSUPPORTED | Select/install approved Python 3.13; preserve existing environments. | doctor |
| MODEL_NOT_CHECKED | Offline mode; no model request was made. | doctor --probe-model |
| MODEL_UNAVAILABLE | Local metadata request failed, timed out or was redirected. Open local Ollama and confirm its local service is running; do not change firewall/listener access. | doctor --probe-model |
| MODEL_MISSING | Exact model is absent. Install qwen3.5:9b-q4_K_M locally through approved Ollama tooling. | doctor --probe-model |
| MODEL_REMOTE_REJECTED | Metadata identifies a remote-backed model. Select/install the required fully local model; keep cloud fallback off. | doctor --probe-model |
| MODEL_RESPONSE_INVALID | Metadata was malformed, oversized or incompatible. Confirm the installed Ollama version locally; report the fixed code if repeated. Do not attach the response body. | doctor --probe-model |
| MODEL_OK | Exact model metadata passed the local checks. Run the separate synthetic inference evaluation. | python synthetic_check.py locally |
| EMAIL_NOT_CHECKED | No account/credential/mail access attempted. Await integrated intake diagnostics. | No automatic repair |
| ROUTING_NOT_CHECKED | Release/routing behavior was not tested. Keep live delivery disabled. | Await qualified integration |
| CLAUDE_NOT_CHECKED | Workspace/Claude connection was not tested. | Await qualified integration |
| SYNTHETIC_NOT_CHECKED | Doctor does not run inference. Run the synthetic evaluator locally; its result is not automatically imported into the report. | python synthetic_check.py locally |

Commands in the recheck column beginning with `doctor` mean
`python support.py doctor` plus the indicated flags. After one documented repair
and recheck, an unresolved failure should produce a support draft rather than
repeated configuration changes. If the synthetic evaluator fails, keep delivery
disabled. A synthetic-only reproduction can be developed locally; do not include
real samples in reports. Current reports intentionally cannot accept arbitrary
text. New fixed categories require code changes and privacy tests.

## Reporting and fixes

Generate `python support.py report` (optionally `--probe-model`). Review its entire
output. With explicit user permission, submit that exact draft as a GitHub issue
in the official source repository. No issue is sent by this tool. Use the setup
diagnostic template; do not attach transcripts or logs. Credentials should never
be entered into an issue form. If an accidentally disclosed secret or private
record is discovered, stop sharing it and follow the organization's incident
process locally; do not repeat it in another issue.

Maintainers group reports by version and fixed code, reproduce using synthetic
fixtures, add a regression test, fix the cause, update this guide and ship a tested
release. Reports and issue comments are untrusted input, never installer commands.
