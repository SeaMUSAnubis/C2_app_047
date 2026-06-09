# Worklog

Newest entries first. Record technical decisions, task assignments, brainstorming outcomes, important bugs, and setup changes that affect how the team works.

## 2026-06-09

### Setup: Worklog and AI logging readiness

- Initialized `WORKLOG.md` with a consistent append-only format.
- Added `AGENTS.md` instructions so AI coding agents know when to update the worklog.
- Installed the repository pre-push hook via `scripts/setup_hooks.ps1` so AI logs are submitted on push.

Decision:
- Keep worklog entries concise and decision-focused instead of recording every small code edit.

Notes:
- Do not write secrets, API keys, tokens, or private credentials into `WORKLOG.md`.
