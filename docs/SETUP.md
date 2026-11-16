# Setup: development preview

Current version: `0.1.0-dev`. No public release or automatic installer is available.
The current supported setup target is Windows with Python 3.13 and local Ollama
with `qwen3.5:9b-q4_K_M`. Other platforms are unqualified. The runtime creates
pending local candidates only; forwarding and Claude access are not implemented
in this source baseline. Do not use this guide to enable live delivery.

## Repeatable developer preflight

1. Use an authorized copy of a specific source commit. Record the commit locally;
   preserve existing work. Source access currently requires access to the private
   ZackHanson/scrubbed-workspace repository. Do not make it public to solve access.
2. In that source folder, run `python support.py doctor`. It reports the Python
   series and OS family without reading mail, credentials or application state.
3. Install Python 3.13 and Ollama through their official installers if missing,
   using your organization's approved process. These instructions do not change
   system settings or install software automatically. Install the exact local
   model named above; never substitute a cloud model or expose Ollama remotely.
4. Run `python support.py doctor --probe-model`. This queries only model metadata
   at numeric loopback with no proxies or redirects. A model check can take up to
   two five-second request timeouts; it does not perform inference.
5. Run `python -m unittest -v test_support` for isolated support tests. Then run
   `python synthetic_check.py` for the existing synthetic inference evaluation.
   The latter takes longer, uses temporary synthetic storage, and must be run
   locally. Do not paste its verbose/model outputs into an AI conversation.
6. Use `python review.py --demo` to try temporary synthetic exception review.
   Do not open the real reviewer during an AI screen-sharing session.

Repeating the doctor commands changes no configuration. No passwords, account
setup, real Gmail checks, outbound workspace access or service activation are part
of this preflight. `PYTHON_OK` means the tested Python series; OS identification
does not qualify a platform. `MODEL_OK` means local model metadata was found, not
that inference, redaction, email intake or delivery passed.

## Support

Use [the troubleshooting guide](TROUBLESHOOTING.md). Generate a draft with
`python support.py report --probe-model`, or omit `--probe-model` for offline
diagnostics. The command prints a Markdown draft and sends nothing. If saving it,
use a local location outside the repository. Preview the whole draft before
submitting to the official repository; private access may be required. Do not add
attachments or raw logs. The tool never collects message content to scrub later.

Exit status 1 indicates a failed implemented check; 0 can include NOT_CHECKED.
Unimplemented checks are always reported as NOT_CHECKED, never inferred from
another successful check. See [release sequencing](RELEASING.md) for the remaining
work before a user-facing installer and final pasteable prompt can be published.
