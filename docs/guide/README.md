# Documentation Index

This is the entry point for project documentation. Start with the README
for a quickstart, then jump to the topic you need.

## Project docs (root)

| File | Purpose |
|---|---|
| [README.md](../../README.md) | Project overview, quickstart, demo accounts |
| [PLAN.md](../PLAN.md) | 4-phase implementation plan + 5 deployment plan |
| [PRD.md](../PRD.md) | Product requirements (what + why) |
| [BRIEF.md](../BRIEF.md) | Short brief for stakeholders |
| [UEBA_REQUIREMENTS.md](../UEBA_REQUIREMENTS.md) | Detailed functional + non-functional requirements |

## Architecture

| File | Purpose |
|---|---|
| [ARCHITECTURE.md](../ARCHITECTURE.md) | System architecture (text) |
| [ARCHITECTURE_OVERVIEW.md](../ARCHITECTURE_OVERVIEW.md) | 1-page overview |
| [architecture_diagram.md](../architecture_diagram.md) | Diagram source (mermaid) |
| [UI_FLOW.svg](../UI_FLOW.svg) | UI screen flow (visual) |

## Contracts

| File | Purpose |
|---|---|
| [API_CONTRACT.md](../API_CONTRACT.md) | REST API reference (all endpoints) |
| [DATA_CONTRACT.md](../DATA_CONTRACT.md) | Database schema + event payload formats |
| [REPO_STRUCTURE_STANDARD.md](../REPO_STRUCTURE_STANDARD.md) | Directory layout convention |

## Operations

| File | Purpose |
|---|---|
| [AGENT_DEPLOYMENT.md](../AGENT_DEPLOYMENT.md) | Install agent on employee machines (curl, pip, binary) |
| [OPERATIONS.md](../OPERATIONS.md) | Day-2 ops: health, monitoring, scaling, backup |
| [TROUBLESHOOTING.md](../TROUBLESHOOTING.md) | Common issues + fixes |

## Development

| File | Purpose |
|---|---|
| [CONTRIBUTING.md](../CONTRIBUTING.md) | Dev setup, code style, PR process |
| [ML_MODEL.md](../ML_MODEL.md) | OCSVM model: training, features, re-training, evaluation |
| [SECURITY.md](../SECURITY.md) | Security model + threat model + compliance |
| [CHANGELOG.md](../CHANGELOG.md) | Release notes |

## Project management

| File | Purpose |
|---|---|
| [MVP_PROGRESS.md](../management/MVP_PROGRESS.md) | MVP feature checklist (100% done as of v0.1.0) |
| [TEST_PLAN.md](../management/TEST_PLAN.md) | Original test plan |
| [TEST_REPORT.md](../management/TEST_REPORT.md) | Test execution report |
| [FRONTEND_TEST_REPORT.md](../management/FRONTEND_TEST_REPORT.md) | Frontend-specific test report |
| [WORKLOG.md](../management/WORKLOG.md) | Per-day work log |
| [JOURNAL.md](../management/JOURNAL.md) | Engineering journal (decisions, trade-offs) |

## Backend setup

| File | Purpose |
|---|---|
| [BACKEND.md](BACKEND.md) | How to run the backend locally + in Docker |

## Refactor history

| File | Purpose |
|---|---|
| [src_only_fe_be_db_keep_ml.md](../refactor/src_only_fe_be_db_keep_ml.md) | Refactor: move backend+frontend+db to `src/` |
| [inventory.md](../refactor/inventory.md) | Files moved during refactor |
| [result.md](../refactor/result.md) | Refactor result summary |
| [legacy_src_readme_before_refactor.md](../refactor/legacy_src_readme_before_refactor.md) | README from before refactor |
| [ueba_ui_redesign_prompt.md](../refactor/ueba_ui_redesign_prompt.md) | UI redesign prompt |

## Reports

| File | Purpose |
|---|---|
| [repo-review-2026-06-18.md](../reports/repo-review-2026-06-18.md) | Repository review report |
| [report_047_UEBA.md](../reports/report_047_UEBA.md) | Original project report (047_UEBA.xlsx summary) |

## References

| File | Purpose |
|---|---|
| [047_UEBA.xlsx](../047_UEBA.xlsx) | Original project spreadsheet (Bảng tính dự án) |
| [2506.23446v2.pdf](../references/2506.23446v2.pdf) | Paper reference (OCSVM for UEBA) |

---

## Reading order

**New to the project?** Read in this order:

1. [README.md](../../README.md) — 5 min, gets you running
2. [ARCHITECTURE_OVERVIEW.md](../ARCHITECTURE_OVERVIEW.md) — 5 min, big picture
3. [API_CONTRACT.md](../API_CONTRACT.md) + [DATA_CONTRACT.md](../DATA_CONTRACT.md) — 15 min, contracts
4. [AGENT_DEPLOYMENT.md](../AGENT_DEPLOYMENT.md) — 10 min, how to deploy
5. [OPERATIONS.md](../OPERATIONS.md) + [TROUBLESHOOTING.md](../TROUBLESHOOTING.md) — 20 min, day-2

**Want to contribute?**

1. [CONTRIBUTING.md](../CONTRIBUTING.md) — 10 min, dev setup
2. [SECURITY.md](../SECURITY.md) — 15 min, security model
3. [ML_MODEL.md](../ML_MODEL.md) — 10 min, OCSVM model

**Going to production?**

1. [SECURITY.md](../SECURITY.md) §6.3 — production checklist
2. [OPERATIONS.md](../OPERATIONS.md) §1+3+7 — deploy + scale
3. [AGENT_DEPLOYMENT.md](../AGENT_DEPLOYMENT.md) — fleet rollout
