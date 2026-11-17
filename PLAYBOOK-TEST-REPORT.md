# Playbook execution test - November 17, 2026

## Verdict

Current judgment after continued testing: **around 9/10 for the playbook as
adaptive setup instructions** (9.1 under the rubric below). This is a conservative
instruction-quality assessment, not a probability of success, deployment score
or certification. Live account/service qualification remains outstanding.

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

## Continued evaluation: target quality around 9/10

This rating concerns the playbook as instructions for a setup model, not the
readiness or compliance of an installation generated from it. Use ten equally
weighted dimensions, each worth one point. A dimension scores zero when absent
or broken, 0.5 for material ambiguity, 0.8 when usable with a small clarification,
and one when clear and supported by execution or directly checkable evidence.
Intermediate scores require a stated reason. Record deductions as well as passes.

| Dimension | Evidence sought |
| --- | --- |
| Action clarity | Ordered steps, explicit completion evidence and an unambiguous resume path. |
| Host adaptation | Actual hardware/workload assessment, measured local selection and an honest infeasible-host branch. |
| Privacy boundaries | Original data/routing isolation across requests, follow-ups, logs, tools and diagnostics. |
| Workflow coverage | Intake through returned work, exceptions and the selected action mode. |
| Implementable contracts | Clear release, configuration, result, state and authority requirements across components. |
| Acceptance evidence | Useful positive traffic, unseen cases, failure injection and correctly labeled mock/local/live evidence. |
| Operations/recovery | Credential repair, pause/resume, startup, restore/source identity and safe updates. |
| Dependency/autonomy handling | Missing access separated from missing code; independent work continues without invented approval. |
| Portability | Platform/provider examples remain conditional and recipient choices are retained. |
| Owner handoff | Runnable artifacts, tested commands, active rules, operating/recovery instructions and truthful remaining gaps. |

Qualification for an approximately nine-point documentation rating requires no
unresolved high-severity instruction defect, independent review near that level,
and corroborating behavioral checks. Simulated platforms are labeled tabletop
tests; real local-model reads are not installation tests. No score substitutes
for the live checks listed above.

The continued fresh-source execution run was exposed to historical trial summaries
through mandatory project startup guidance. It remains useful execution evidence
but is not an uncontaminated blind test. A separate local-model reader receives
only the frozen document and simulated scenarios, with no project history.

### What the additional rounds found and changed

The first portability review scored the then-current document 8.93/10. Its three
simulated hosts covered macOS/unified memory/non-Gmail, Linux CPU-only with no
model or download permission, and Windows with dirty source/OAuth/mirror/reply
choices. Twelve continuation challenges covered recovery and authorization. The
reference scenario runner checks the reviewer's interpretation; it is not an
application or proof that prose enforces policy.

Findings led to capability-level receipts/evidence classes, identity-preserving
source rebinding, wrong-account renewal rejection, effective-configuration
precedence/provenance, independent persistent stop reasons and a scope-bound
activation manifest. Separate build/integration/shadow/live profiles clarify when
real-provider synthetic tests may occur without prematurely activating real mail.

An interim reviewer scored that revision 8.8/10 and identified budget-period and
reservation-settlement ambiguity. The next revision defines period/clock policy,
conservative pre-attempt cost bounds, idempotent settlement, outstanding unknown
liabilities across rollover/restart/renewal, and explicit budget guard limits.
It also identifies actual dirty installed bytes, distinguishes unmeasured hosts
from failed tests, and requires reason-specific resume demonstrations.

A final independent document reviewer found no substantive gap and scored its
reviewed snapshot 10/10. That was a tabletop instruction review, not executed
integration evidence, and it disclosed the mandatory startup-history exposure.
The primary does **not** adopt a perfect score: real recipient variation and the
limits of the execution evidence justify the deductions below. A subsequent
context-scoping clarification requires useful same-task follow-ups using only
released/validated history; it was checked by the primary and final local-reader
probe, not by another full deployment trial.

### New source-free execution and independent assessment

The execution model built new application source from the frozen earlier
playbook, without reusing prior application code or parent fixtures. Mandatory
startup guidance exposed earlier high-level findings, as noted above. Its own
report scored that snapshot 8.75/10 and recorded all partial capabilities and
interpretation choices. Several deductions were addressed in the later document
revisions; others concerned deliberately delegated implementation choices.

Self-test evidence: 43 deterministic checks, twelve actual-local corpus outcomes,
a screened follow-up, a 7,999-character request, CLI controls, native Tk rendering
and encrypted backup/in-memory restore checks. The generated application still
lacked full startup registration/uninstall, relocated restore/update rollback and
retention enforcement. These were recorded as code gaps, not concealed as missing
credentials or counted as complete.

The parent then exercised that frozen application with twelve independent exports:

- All six required routine cases released; all four required meaning checks passed.
- Known identifiers were absent from all eight captured requests. One attack-bearing
  input was generalized to its benign office request with the attack removed;
  it was not counted as an attack rejection.
- Attachment, HTML-only, oversized and unsupported multipart inputs stayed held.
- Imports progressed ten, two, zero; no source duplication occurred.
- Eight results and sixteen local task/draft actions persisted through substituted
  provider HTTP. Twenty-four actual local-model calls included output audits.
- Separate deterministic fault tests verified unknown-outcome reservation retention
  without blind retry, privacy pause surviving activation, changed-source rejection
  before transport and budget-cap rejection before transport.

Source hashes stayed unchanged. The run took about 39 seconds on this host, not an
isolated performance benchmark. It made no actual provider call and established
neither real Claude work quality nor live startup/recovery. Later document-only
contracts, including stateful approved conversation context and detailed rollover
semantics, were not retroactively claimed as implemented in that frozen build.

### Clean-context local-model reading tests

The existing local Qwen model received only a playbook snapshot and declared
simulated scenarios, with fresh message history and no project handbooks. It
passed 32 basic decision checks on the earlier snapshot, then eighteen mixed
positive/negative operational decisions on the intermediate revision. A later
probe passed thirty checks including budget settlement and actual installed-byte
identity. The delivery snapshot passed **34/34**, adding task-context boundaries.

These are real local inference/reading tests over hypothetical situations, not
installations on macOS/Linux or application enforcement tests. The counts overlap
between revisions and are not a statistical confidence estimate. They corroborate
readability and decision consistency alongside the code execution evidence.

### Final conservative rating

| Dimension | Points out of 1 | Remaining deduction |
| --- | ---: | --- |
| Action clarity | 0.90 | Long multi-stage document still requires disciplined receipt use. |
| Host adaptation | 0.90 | Actual execution used one host/model; other resource profiles were simulated. |
| Privacy boundaries | 0.95 | Strong explicit controls; finite known-identifier tests cannot cover every private combination. |
| Workflow coverage | 0.90 | Full route specified; real provider work and the newest context contract remain unqualified. |
| Implementable contracts | 0.90 | Invariants are explicit; provider-specific concurrency/reconciliation still needs implementation judgment. |
| Acceptance evidence | 0.95 | Multiple evidence classes and independent tests; coding trials have startup-history contamination. |
| Operations/recovery | 0.85 | Concrete repair requirements now exist, but full installed-account/reboot/relocated-restore execution is absent. |
| Dependency/autonomy handling | 0.95 | Independent progress is clear; every recipient still needs accurate scope/account decisions. |
| Portability | 0.90 | General choices and native integration required; no actual non-Windows installation was performed. |
| Owner handoff | 0.90 | Deliverables and active authority are explicit; usability across real recipients remains unobserved. |
| **Total** | **9.10 / 10** | **Primary judgment of instruction quality, rounded to about nine.** |

No unresolved high-severity instruction finding remains from these reviews. The
score is not an average of reviews of different revisions and does not turn any
blocked installation or simulated result into a completed capability.

### Continued-trial provenance

Artifacts remain under the local agent-cache run `rating-20261117-154425`:
`fresh/REPORT.md`, `fresh/FREEZE-MANIFEST.json`, `assessment/verify_fresh.py`,
`assessment/fresh-independent-results.json`, the portability/recheck/final-review
reports, and `reader/reader-baseline.json`, `reader/contracts-revised.json`,
`reader/contracts-final.json`, `reader/contracts-delivery.json`.

Reviewed final snapshot before the last context clarification:
`dbbed1dd452b7d6a5e8eef6683bd8e7976bf539583887a329aafb297cb6c9d46`.
Prior delivery playbook SHA-256, checked by the 34-decision reader probe:
`8bf23f82c53a93fba5d855336fa706351a101dbf76d70b56080cf3746af15a91`.

The repository changes are documentation only. Real mail, secret credentials,
paid provider requests, installed startup jobs and live external replies were
not used to obtain this rating.

## Rewrite for the setup model

Replaced the human handoff preface and copyable prompt with direct instructions
to the model performing setup. The file now assigns the model responsibility for
inspection, implementation, installation, testing and delivery. It distinguishes
that model from the user, the local inference model and Claude. The fourteen
phases, completion checks, privacy rules and adaptive setup requirements remain.

The local reader passed 38/38 decisions on this revision, including four explicit
role checks. It identified building/installing/verifying as its task, rejected
rewriting the document as the deliverable, and kept real-original inspection with
the user rather than the setup model. Structure, links and workflow identifiers
also passed checks. These reading tests do not replace live integration tests;
no new application build or live activation was performed for this audience edit.

Tested playbook SHA-256:
`bf8e9276d3d900fac341f67aa023f06c72632acaa0a7513f972a91639812aaf1`.
Receipt: `reader/contracts-agent-directed-final.json` in the retained rating run.

## Fresh-machine default

The playbook now assumes only the OS and setup-model access exist. It requires
installation of the selected language/build tools, dependencies, authentication
and UI support, inference runtime and model weights. Existing installations are
optional reuse candidates and must be verified. Missing software alone is setup
work; explicit download restrictions or genuine installation failures remain
separate blockers.

Added OS-native prerequisite discovery and bootstrap, dependency ordering,
official-source/signature checks, per-item install receipts, interrupted-install
recovery, new-process path verification and a bootstrap entry point that works
before the application runtime exists. Local model installation now precedes
evaluation. A successful synthetic inference request is required; a model tag or
completed download alone does not establish readiness.

The first reading probe passed 47/48 decisions. Its ambiguous question about
"requiring missing Python to bootstrap Python" returned an inconsistent answer
despite a reason describing OS-native installation. Added a concrete instruction
to install Python with an OS-native installer before running any Python installer
script, and clarified the probe to ask about that exact dependency cycle. The
final probe passed 48/48, including the prior role/privacy/recovery checks and ten
fresh-machine decisions. Both receipts are retained as
`reader/contracts-fresh-machine-default.json` and
`reader/contracts-fresh-machine-final.json`.

Structure checks verified all fourteen phases/completion checks and installation
before model evaluation. These are document and local-model reading checks on an
existing host. No software was installed and no real clean-OS bootstrap was run.
The new acceptance requirement explicitly distinguishes a fresh-target install
from a virtual environment or simulated missing tools.

Tested playbook SHA-256:
`2327c593a074d75d4a29fb5ccfa93b65b1ec554881810894d254eda23faa9b7b`.
