# Distribution and support implementation sequence

Owner authorized all distribution/support components on November 16, 2026.
The support foundation is implemented now so evolving components can adopt its
privacy boundary. Final installation instructions depend on the integrated system.

## Present foundation

- Standalone content-free doctor and allowlisted Markdown report generator.
- Synthetic support tests covering failures, transport limits and privacy.
- Version-matched troubleshooting guide, GitHub issue template and draft AI prompt.
- Source-only development preflight; no public installer/release claim.

The hardcoded `0.1.0-dev` version identifies development software only. Before a
release, stamp one version into code/docs/artifacts and retain the exact source
commit, model tag/digest, dependency/runtime versions and test results. Different
development commits are not reproducible releases merely because this string matches.

## After the six runtime tracks integrate

1. Stabilize intake, shadow routing, synthetic evaluation, Claude capture, reply
   workflow and recovery interfaces. Keep identity/routing local. Add fixed,
   content-free diagnostics for each implemented component with privacy tests.
   Inference tests stay opt-in and synthetic. Account checks must not return
   addresses, credentials, source references or message content to the AI.
2. Build the repeatable installer/configurator against these interfaces. Preserve
   prior installs/configuration, detect partial installs, support resume and safe
   rollback, keep secrets in local credential entry, and separate synthetic setup
   from live activation. Do not repeatedly overwrite settings on rerun. Record
   supported platforms/hardware from actual fresh-machine tests, not assumptions.
3. Qualify an immutable release on a clean supported Windows machine: initial
   installation, second run, interrupted install/recovery, missing/wrong/remote
   model, offline/authentication failure, synthetic end-to-end flow and rollback.
   Test report privacy and setup with an AI that receives only permitted outputs.
   Establish the applicable de-identification/release requirements separately;
   passing setup tests alone never enables real delivery.
4. Finalize SETUP.md and the pasteable prompt against that release, replacing
   DEVELOPMENT_REF with its immutable commit URL. Test all commands literally.
   Publish artifacts with checksums and release notes; keep an upgrade/rollback
   guide and an explicit supported-version policy. Never use a changing branch
   as an executable installer source.
5. Prepare public distribution: review the full proposed source/history/artifact
   scope for privacy and choose licensing. The current private repository stays
   private. Obtain the owner's concrete approval for the prepared public target
   and contents before creating a public repository or changing visibility. Select
   the support destination, review permissions and test access as an outside user.
   Private reports must still contain only allowlisted data. Do not publish an
   unavailable public URL in a finished prompt.
6. Operate the feedback loop: reports -> synthetic reproduction -> regression test
   -> fix -> updated troubleshooting -> versioned release. Deduplicate by version
   and failure code. Extend the schema deliberately; no automatic log collection,
   AI-written arbitrary report fields, automatic issue submission or unreviewed
   fixes sourced from issue comments.

The release maintainer owns this checklist when runtime integration is ready.
No scheduler, public repository, GitHub release or external reporting service is
created by this source change. At verification, main exists at the shared source
baseline; it was created outside this track. This track does not bootstrap main
or change branch protection. Integration remains a separate reviewed action.
