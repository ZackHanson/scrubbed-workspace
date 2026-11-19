# Agent Handbook - Scrubbed Workspace

## Purpose and success

Owner: Zack. This is the primary repository for the Scrubbed Workspace setup
playbook. README.md is the human starting point; SETUP-PLAYBOOK.md instructs a
coding agent to build, install and test the complete workspace on the recipient's
computer. Choose software and local models for that computer.

## Boundaries

Keep private email, credentials, runtime state and personal diagnostics out of
Git and cloud agent prompts. Use synthetic data for development and verification.
Repository edits do not authorize live email processing, provider submissions,
software installation, background jobs or changes to private local data.

## Run and verify

For documentation changes, check local Markdown links, instructions, references
and git diff whitespace. This repository contains documentation only. Build and
test the application in the recipient project by following SETUP-PLAYBOOK.md.

## Source workflow

Preserve the established T3 workspace and other branches/worktrees. Use task
branches and pull requests against main in private ZackHanson/scrubbed-workspace.
Never commit or push directly to main. Preserve Git history and private data.
Resolve merge conflicts as they arise during project work, preserving intended
changes from both sides. Verify the thread's branch matches the Git checkout
and check PR mergeability before handing work back.

## Current work

November 18: PR #15 merged the documentation-only project direction. README.md
is the human entry point; SETUP-PLAYBOOK.md is the complete installation contract.
Earlier application code remains in Git history and existing branches/worktrees;
installed software and private runtime data are untouched.

November 18 safety review: playbook version 2026-11-18.2 adds host/installer and
model-artifact trust, least-privilege enrollment and TLS, protected local rendering,
explicit outbound envelope checks, resource limits and stale-backup reconciliation.
Acceptance rows require evidence for these safeguards; README explains remaining
risk and safe setup access. Documentation checks do not certify an implementation.
Keep the version current whenever changing instructions and record it in setup
receipts/manifests and handover. Source changes use a task branch and PR; no
application installation or activation is part of this documentation task.

This repository is the sole home for the setup playbook. PR #14 and the older
distribution PR #12 are superseded by this direction.

November 18 cleanup: removed the obsolete repository reference and preservation
instruction. The current documentation uses this repository as its source.

November 19: README uses "project folder" and gives returning users two steps
with a pasteable resume prompt that explains the setup receipt and preserves
existing work and the processing pause. Playbook instructions are unchanged.

November 19: shortened the README introduction to summarize local email scrubbing,
cloud AI, organized results and user-controlled actions. Setup safeguards remain
in SETUP-PLAYBOOK.md; its instructions are unchanged.

November 19: playbook version 2026-11-19.1 expands user guidance with a plain-language
system overview, context for each request, example questions and stage updates.
README's setup prompt requests the same guidance. Technical setup requirements
remain in place. This is a documentation change, not an installed application update.
