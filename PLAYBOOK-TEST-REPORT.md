# Playbook execution test - November 17, 2026

## Verdict

The first independent execution trial did **not** qualify the playbook as a reliable
full-system setup procedure. A fresh model built a runnable synthetic application,
but independent checks exposed lost work and incomplete production paths. The
playbook was revised to address those findings. Independent work-preservation
retests now pass in the tested synthetic scenario; complete live setup remains
unverified.

## Method and scope

The baseline setup model received a frozen playbook, recipient choices and a new
agent-cache directory. It received no parent conversation or project application
source. It could inspect the actual host read-only and use existing local
inference, but had no permission for model downloads, shared-service changes,
startup installation, paid API calls, real mail or credential access.

The recipient scenario was English routine administrative mail, approximately
20 messages/day, at most 8,000 characters and 120 seconds local processing per
message, a desktop workspace, local synthetic exports and automatic local
tasks/drafts. External sending was disabled. Missing live access was explicit;
independent implementation and tests still had to proceed.

- Baseline source commit: `c120ecad60d63fd62ad9113fe0c3bb430c527e8e`.
- Frozen playbook SHA-256:
  `73d48e1b76d3e6342b26c30ebbdd8a8de3af0aeefac03605dd97855c13a8201e`.
- Actual host class: Windows, 32 GiB system memory and an 8 GiB discrete GPU.
- Existing local runtime/model: Ollama with `qwen3.5:9b-q4_K_M`.
- Frozen generated-source aggregate SHA-256 reported by the setup model:
  `24f990b421d572f434adaf6033455e771e01c000da882ccfe89ed61da455e51d`.
- No claim is made for another OS, hardware configuration or model.

Trial code, synthetic stores and detailed receipts remain outside Git under
`%LOCALAPPDATA%\Codex\playbook-tests`. The source-only repository contains this
summary, not runtime state or private machine diagnostics. The runner restrictions
also limit what can be concluded: this was a fresh-model test on an existing
machine, not a clean OS installation.

## Baseline results

The setup model reported 18 passing deterministic tests and a labeled local-model
corpus run using 24 actual inference requests. It also exercised its native Tk
window, source deduplication and encrypted synthetic backup/restore. Those are
self-test results; they do not substitute for the independent assessment below.

The parent evaluator supplied ten separate synthetic messages. Seven were prepared
before inspecting generated code; three additional cases targeted work-preservation
gaps discovered during inspection. The settled run used six real local inference
calls, generated three released tasks and captured three constructed Claude
requests with a substituted external service. No request reached Anthropic.

| Independent check | Observation |
| --- | --- |
| Simple routine agenda request | Released and result persisted. |
| Routine request containing synthetic identifiers | Released with none of the known identifying sentinels in the captured payload. |
| Attachment, HTML-only and oversized input | All held without a release. |
| Instruction attack | Held without a release. |
| Multipart alternative | Held as unsupported; this does not establish support for normal multipart mail. |
| Repeated import | No additional source records or inference. |
| Unapproved send proposal | Rejected. |
| Versioned source edit | Prior release could not be dispatched. |
| Screened exception draft | Created a usable new release path after the setup model's own fixes. |
| Unseen onboarding request | **Failed:** valid routine work was held by a narrow keyword policy. |
| Agenda with three required sections | **Failed:** it was released as a canned generic checklist, losing every requested section. |
| Substantive request in subject; polite body | **Failed:** source was marked ignored because only the body was considered. |
| Collection exceeding batch limit | **Failed:** of 45 exports with a batch limit of 40, the first poll found 40 and the next found zero; five were indefinitely undiscovered. No inference was needed for this test. |

There were no known sentinel leaks in the three captured requests. This finite
result does not establish general privacy performance. Another robustness probe
modified source storage without increasing its version: the old immutable release
remained dispatchable. Its approved payload did not change or leak the edited
text; this is a storage-integrity limitation, distinct from a demonstrated leak.

An earlier in-progress run encountered a release INSERT error. The setup model
independently detected and corrected it during self-tests before the settled run.
That intermediate run is retained as debugging evidence and excluded from the
qualification results. Empty release sets were not accepted as successful
privacy/persistence tests.

## Implementation gaps versus unavailable access

Unavailable account access prevented real Claude verification. Startup/reboot
testing was outside the authorized scope. These are genuine live-test blockers.

The generated application also had implementation gaps: its public CLI supported
only shadow execution, enrollment was incomplete, and activation unconditionally
refused rather than accepting an authorized production configuration. Those gaps
would not disappear merely by supplying a key. They must be implemented and
verified separately. Optional mailbox intake and external replies were not
qualified by the synthetic-export, local-draft scenario.

## Changes prompted by the trial

The revised playbook now requires subject/body processing together, preservation
of non-identifying task requirements, recipient-defined routine categories, unseen
acceptance examples, positive traffic through the pipeline and a working vertical
slice. It explicitly separates unimplemented code from missing account access and
requires a configurable activation path rather than unconditional placeholders.
The batch failure also prompted an explicit eventual-discovery check beyond the
configured batch limit.

The revised playbook snapshot used for the affected work-preservation retest has SHA-256:
`95991844322c5896434bebcb7f12b5fdcceaf8032f3909f1ce34620f22e29834`.
The additional batch requirement was tested separately using the later snapshot
`1c86f81a0dcd8200a6f1329433dc7a606b70e0050ff3e29554baf58b2995aa2d`.

## Retest and remaining qualification

A second fresh model received the revised playbook and the first trial's frozen
application source, with no runtime state or parent assessment fixtures. This
tests the source-reuse branch; a new from-scratch build of the revised playbook
was not performed. It also received a brief naming the failed requirement
categories. This is a targeted regression test, not an unassisted fresh-start
comparison or proof that wording alone caused the improvement.
The model completed its own repairs and self-tests before
freezing source for the qualifying independent run. Intermediate failed runs
were retained, not counted as qualification.

The independent final run used twelve messages, including the original regressions
and two additional positives withheld from the setup model. It made fifteen real
local inference calls and took approximately 32 seconds on this host. Every
required routine case released: six of six. All four meaning-preservation checks
and both ordering checks passed; the evaluator also inspected the actual generated
task text. Identifier-bearing routine input produced a seventh release with none
of the known identifying sentinels.

The five other inputs were held, including the attack, unsupported content and
oversized input. Repeat import, versioned-edit invalidation, exception draft
resolution and rejection of unapproved send proposals passed. Source hashes were
unchanged during the qualifying run.

Unlike the first assessment's direct fake-service callback, this run exercised
configuration activation, durable release, the configured dispatcher, real Claude
request construction, response parsing/validation and persistence. Only the
external HTTP call was substituted. Seven requests were captured and seven
placeholder service results persisted. These were **not Claude-generated work**
and establish neither provider compatibility nor output quality from Claude.

The setup model separately reported fourteen of fourteen actual-inference routing
checks and twenty-two deterministic/regression checks. Those self-test counts are
distinct from the independent twelve-message run.

The batch-progress follow-up used a separate source copy and no model inference.
The model's own 125-source test passed. The parent independently generated 95
distinct exports: successive polls added 40, 40, 15 and zero, with a database
close/reopen after the second poll. All 95 source IDs were unique. Changed-source
holding, repeated-change version stability and missing-source rejection passed;
the source file stayed unchanged throughout the run. This verifies the batch
repair in isolation, not the combined full application after installing it.

## Reproduction and retained evidence

The baseline's exact command ledger is `evidence/cli-commands.json` in its trial
directory. Its primary commands were:

```powershell
python -m workspace setup
python -m workspace doctor
python -m workspace test --synthetic
python -m workspace test --synthetic --local-model
python -m workspace run --mode shadow --once
python -m workspace ui --smoke
python -m workspace backup
python -m workspace restore-check
```

The independent evaluator ran `python verify_trial.py settled-v1` for the baseline
and `python verify_trial.py revised-final --retest` for the revised source. These
are trial-artifact commands, not commands installed by this repository. They
require the retained generated application and fixtures, located in the sibling
assessment directory under the local agent cache. Each run uses a new isolated
database and records results, actual request payloads containing synthetic data,
model-call metrics and, for the final run, source hashes.

Key receipts are `independent-results-settled-v1.json`,
`independent-results-revised-final.json`, `batch-baseline.json` and
`batch-revised-final.json`. The revised
application has its own `RETEST-REPORT.md` and `evidence/source-sha256.json`.
The separate intake repair has `BATCH-RETEST-REPORT.md`; its independently tested
`intake.py` SHA-256 is
`e93f1dc4aa669134a540b4b5037404241dd68ce5692d1b0d0c9305b195e8819f`.

## Still unverified

Full qualification still requires an authorized real-provider synthetic round
trip, secure enrollment under the installed worker identity, actual startup and
restart checks, recipient-local live intake/review, and the selected action mode.
Passing the targeted retest alone will not establish that the whole system is
ready for real use.
