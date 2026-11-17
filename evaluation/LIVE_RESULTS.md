# Guarded synthetic Qwen evaluation, November 16, 2026

The 35-case run **failed** at exact evaluation revision
`292cb40b5fa535d06719179215ae36e1841e6948`. Subsequent changes add reproduction
tests and documentation only. Runner, corpus, core scrubber and thresholds are
unchanged. This is not evidence about the six-module integrated system.

Python 3.13.15; fixed `qwen3.5:9b-q4_K_M` at `http://127.0.0.1:11434`.
Installed model digest recorded after the run:
`56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90`.
The tag and remote-host metadata were checked before inference; the digest was
not pinned or checked before each request. A tag is not an immutable model.

## Separate outcomes

| Dimension | Mock contract | Live useful cases | Input refusals | Injected faults |
| --- | --- | --- | --- | --- |
| Privacy containment / known canaries | 35/35 pass | 15/16 pass | 7/7 contained | 12/12 contained |
| Required meaning groups | 16/16 pass | 15/16 pass | N/A | N/A |
| Exact typed refusal | 19/19 pass | N/A | 7/7 pass | 12/12 pass |
| Candidate schema | 16/16 pass | 16/16 pass | No candidates | No candidates |
| Unexpected execution errors | 0 | 0 | 0 | 0 |

All 35 fixtures ran in order. Overall live privacy was 34/35 and utility 15/16;
the strict gate returned exit 1. All sixteen useful cases produced candidates.
Seven refusal cases exercise parsing, and twelve simulate model/transport
failures. These do not demonstrate actual model refusal behavior. Mock success
demonstrates contracts, not redaction quality or clinical correctness.

## Reproductions for the integration / scrubber owner

- `context-01`: a schema-valid candidate retained useful migraine/prevention
  meaning but also three known rare identifying-trait canaries. Both redactor
  and auditor accepted it. Guarded focused replay reproduced all three matches.
  Improve rare-combination generalization and auditor detection while preserving
  the useful request. The existing privacy gate must continue failing this output.
- `utility-05`: a schema-valid, canary-free candidate kept the insomnia topic but
  omitted the requested diagnosis/prescription exclusions. Guarded replay
  reproduced the loss. Preserve clinical scope and negative constraints. Keeping
  the topic alone does not satisfy this fixture.

Focused evaluator tests lock in these observed outcomes. No evaluator defect
was established. No core prompt, scrubber, auditor, threshold or fixture was
changed to make the run pass. Other paraphrases may require synthetic human review.

## Controls and receipts

Inspection and focused tests verified fixed numeric loopback, fixed model and
remote-metadata rejection, disabled proxies/redirects, rejected other socket
destinations, exclusive lock, serial inference, built-in fixtures only, temporary
STATE, unexpected-write detection and sanitized JSON receipts. The runner does
not read inboxes, runtime candidates or source records. Deterministic tests used
prohibited sockets and temporary LOCALAPPDATA. No real delivery, service, security
or infrastructure action occurred. Existing private runtime was not inspected.

Content-free JSON receipts are outside Git and private runtime in the local
temporary folder `scrubbed-synthetic-receipts-20261116`: `live-292cb40.json`,
`mock-292cb40.json` and `provenance-292cb40.json`. Temporary receipts are not durable
backup. Provenance records source fingerprints, model digest and content-free
replay outcomes. No messages or model text are persisted in these receipts.
Original live receipt SHA-256:
`d7148145e40821d16f39edb97c746278b01e6ed19c4520150fc02f2817c076d7`.

## Integrated-head rerun

The integration owner must use the intended combined checkout, record its exact
clean HEAD, and rerun after core fixes. This branch's result is not that rerun.
From the combined checkout in PowerShell:

```powershell
git rev-parse HEAD
git status --short
python -B -m unittest test_evaluation -v
$receipt = Join-Path $env:TEMP 'scrubbed-integrated-synthetic-receipt.json'
python -B -m evaluation.runner --live-qwen | Set-Content -Encoding utf8 $receipt
$evaluationExit = $LASTEXITCODE
Get-Content -LiteralPath $receipt
Write-Output "Evaluation exit: $evaluationExit"
```

Do not delete an existing experiment lock to force a run; coordinate with its
owner. Record the integrated revision beside the receipt; the current format
does not embed Git SHA. Runs may vary despite temperature 0. Separate actual
inference, input refusals and injected failures when assessing each dimension.

Lexical checks cannot establish clinical correctness, entailment, unknown
identifier detection or absence of invented advice. Same-model redactor/auditor
passes are correlated. Neither a pass nor this report certifies privacy, medical
safety or compliance, or authorizes automatic Claude delivery.

## Integrated Qwen fix rerun, November 16, 2026

The full 35-case strict live gate **passed** (exit 0) on clean combined code head
`123c26ef3923078e6016745f8038d94f011e87b5`, based on exact integration head
`92633ac067ee074b44ee5435f22e0b4ef5923f18`. Later commits record results only.
Python 3.13.15; fixed numeric loopback and model tag as above. Before inference,
`/api/tags` selected the fixed local model and `/api/show` rejected remote metadata.
The verified installed digest was
`56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90`.
The guarded runner now checks this digest before and after every actual inference,
failing closed on changes. This verifies the installed model identity reported by
Ollama, not independent supply-chain attestation of the model's training or bytes.

Privacy containment passed 35/35; all 16 actual-inference useful cases produced
schema-valid candidates and passed every required meaning group with zero known
canary matches. Seven input refusals and 12 injected model faults matched their
exact expected typed reasons. Zero unexpected execution errors occurred. Input
refusals do not call the model; injected faults do not establish live model
refusal behavior. All original corpus bytes, lexical groups and thresholds remain
unchanged. The same-head deterministic mock contract also passes all 35 cases.

The redactor now separates the requested work from distinctive biography and
preserves all scope, exclusions and negation. The auditor explicitly considers
combinations of personal traits even without names or locations. Examples in the
prompts use unrelated invented details, not fixture words or replacements.

An intermediate full run on clean `92f61085294ad5dcf698002672624bc4cf003472`
still failed: privacy containment 35/35, usefulness 15/16, schema 15/15, exact
refusals 19/19. Both original reproductions passed, but `quoted-01` was correctly
blocked by the auditor after the redactor retained an unnecessary visit month
and relative-employment narrative. The follow-up fixes task extraction from
quoted history; the auditor was not weakened. That failed receipt is retained.

Final guarded focused replay passed eight candidate cases: both original
failures, quoted-history regression, and five extra synthetic cases covering
other rare trait combinations, negative scope and quoted personal history.
All passed privacy, utility and schema. Three direct auditor probes passed:
two retained rare-context candidates blocked, one clean scoped request accepted.
`python -B -m evaluation.focused` runs these built-in probes serially with the
same exclusive lock, digest checks and temporary STATE; no output text is saved.

Deterministic validation: 36 focused tests and all 184 combined tests passed with
sockets blocked and temporary LOCALAPPDATA. The final combined suite ran on the
same clean code head as the final live run. No real messages, candidates, source
references or private runtime storage were read. No real transport, cloud model,
action, service, scheduler, infrastructure or access setting was activated.

Content-free receipts remain outside Git/runtime in the operator temporary
folder: `scrubbed-qwen-focused.json`, `scrubbed-qwen-full-92f6108.json`,
`scrubbed-qwen-focused-v2.json`, `scrubbed-qwen-full-123c26e.json`, and
`scrubbed-qwen-provenance.json`. The manifest associates each receipt's SHA-256
with its exact clean code SHA and verified model digest. Final full receipt hash:
`91f01ae8ba07320da816a7231753c85263a2237ddb438369e2f0affa17acc2c3`.
Temporary receipts are not durable backup. Source-only stacked draft PR:
https://github.com/ZackHanson/scrubbed-workspace/pull/4, targeting
`feature/integrated-shadow-workflow`. No merge is authorized by this work.

A passing lexical synthetic gate cannot establish unknown-identifier detection,
clinical correctness, entailment or absence of invented advice. Same-model
redactor/auditor decisions remain correlated, and live behavior can vary. This
pass is not privacy certification, release permission or authorization for
automatic Claude delivery. Broader qualification, desktop retry wiring, pilot UX,
release/provider qualification and private-state recovery remain separate work.
