# observatory: rules for agents

Read `README.md` for how it works, `RUNBOOK.md` for procedures, `TASK.md` for what is open.
Global rules in `~/.claude/CLAUDE.md` still apply.

- Public repo: no personal data, account figures, third-party names or the owner's email in any file; the git gate blocks them.
- Real-time commits only; never backdate, never set `GIT_AUTHOR_DATE`.
- Releases follow hq CONVENTIONS (`~/developer/hq/CONVENTIONS.md`); the RUNBOOK names the steps.
- Docs follow the four-file skeleton: a fact lives in one file, and the commands table is generated.
- Traps: sourcewatch pins this package by tag, so a public API change is a new tag plus a pin bump there, never a force-pushed tag; the dashboard is an optional extra, so run tests after `uv sync --all-extras`; the results database's directory must exist before a run.
