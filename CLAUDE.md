# observatory: rules for agents

Instructions for coding agents working in this repo; a human reader wants `README.md`. Read
`README.md` for how it works, `RUNBOOK.md` for procedures, `TASK.md` for what is open. The
owner's global agent rules apply on top of these.

- Public repo: no personal data, account figures, third-party names or the owner's email in any file; a pre-commit scan blocks them.
- Real-time commits only; never backdate, never set `GIT_AUTHOR_DATE`.
- Release steps: `RUNBOOK.md` §Release.
- README, RUNBOOK, CLAUDE and TASK each hold one kind of fact; the README commands table is
  generated, never hand-edited.
- Traps: sourcewatch pins this package by tag, so a public API change is a new tag plus a pin bump there, never a force-pushed tag; the dashboard is an optional extra, so run tests after `uv sync --all-extras`; the results database's directory must exist before a run.
