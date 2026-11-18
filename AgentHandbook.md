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

## Current work

November 18: PR #15 merged the documentation-only project direction. README.md
is the human entry point; SETUP-PLAYBOOK.md is the complete installation contract.
Earlier application code remains in Git history and existing branches/worktrees;
installed software and private runtime data are untouched.

Current task improves raw Markdown download instructions, first setup/resume,
guided manual steps, cloud-provider consistency and implementation freedom while
preserving privacy and acceptance requirements. Playbook version 2026-11-18.1
is recorded in installation receipts/manifests and handover. Keep the version
current whenever changing instructions. Source changes use a task branch and PR;
no application installation or activation is part of this documentation task.

This repository is the chosen home going forward. The separate private
ZackHanson/scrubbed-workspace-playbook repository is an earlier standalone copy;
no ongoing synchronization is required. Preserve it without further changes.
PR #14 and the older distribution PR #12 are superseded by this direction.
