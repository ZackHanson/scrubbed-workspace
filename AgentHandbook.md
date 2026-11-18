# Agent Handbook - Scrubbed Workspace

## Purpose and success

This repository provides SETUP-PLAYBOOK.md and human setup instructions for
building an independent scrubbed email workspace. Choose the application stack
and local models for the recipient computer and implement the complete playbook.

## Boundaries

Keep private email, credentials, runtime state and personal diagnostics out of
Git and cloud agent prompts. Use synthetic data for development and verification.
Repository edits do not authorize live email processing, provider submissions,
software installation, background jobs or changes to private local data.

## Run and verify

For documentation changes, check Markdown links, instructions and git diff
whitespace. The application and its tests are built in the recipient project
by following SETUP-PLAYBOOK.md.

## Source workflow

Preserve the established T3 workspace and other branches/worktrees. Use task
branches and pull requests against main in private ZackHanson/scrubbed-workspace.
Never commit or push directly to main. Preserve Git history and private data.

## Current work

November 18: Owner requested removal of the previous application and its
references, including the README statement about included code. Removed the
application modules, launchers, tests, icon and application usage guides. Retained
the setup playbook, human setup steps and safe issue-reporting instructions.
Removed references to the old implementation from the playbook and issue template.
This is a documentation-only source tree; it does not alter installed software
or private runtime data. Earlier work remains in Git history and existing branches.

A separate private ZackHanson/scrubbed-workspace-playbook repository also exists.
This cleanup applies to ZackHanson/scrubbed-workspace as requested; it does not
change that separate repository or other open implementation proposals.
