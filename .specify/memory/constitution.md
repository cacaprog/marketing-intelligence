<!--
SYNC IMPACT REPORT
==================
Version change: (template) → 1.0.0
New constitution — first ratification.

Added sections:
  - Core Principles (5 principles)
  - Technology Constraints
  - Development Workflow
  - Governance

Templates reviewed:
  - .specify/templates/plan-template.md     ✅ compatible (generic, no conflicts)
  - .specify/templates/spec-template.md     ✅ compatible (generic, no conflicts)
  - .specify/templates/tasks-template.md    ✅ compatible (generic, no conflicts)
  - .specify/templates/checklist-template.md ✅ not read (no constitution references expected)

Deferred TODOs:
  - None
-->

# conectivo-analytics Constitution

## Core Principles

### I. Service Independence

Each service under `services/` MUST be independently runnable, testable, and deployable.
A service MUST NOT import from another service directory. Cross-service logic MUST be
extracted to `shared/` first. Each service has its own `CLAUDE.md`, `tests/`, and
`dashboard/` — there are no shared entry points between services.

### II. Dataset Immutability

`data/raw/` is read-only for all services. No service MUST ever write to or modify files
under `data/raw/`. Services MUST write intermediate or processed outputs only to
`data/processed/<service-name>/`. Regenerating the dataset via `generate_dataset.py`
MUST be safe to run at any time without breaking any service.

### III. Shared Code First

Before implementing any utility in a service, contributors MUST check whether it belongs
in `shared/`. Database connections (`shared/db.py`), configuration constants
(`shared/config.py`), visualization theming (`shared/viz.py`), and general utilities
(`shared/utils.py`) MUST live in `shared/` and be imported from there. Duplicating these
across services is prohibited.

### IV. Ground Truth Accountability

Every attribution model implemented in `services/01-attribution/` MUST be evaluated
against `touchpoints.true_marginal_contribution`. No attribution analysis is considered
complete without a comparison table showing model output vs. ground truth (MAE or
correlation coefficient at minimum). This applies to all heuristics: last-touch,
first-touch, linear, time-decay, position-based, and engagement-weighted.

### V. Subpopulation Awareness

Any analysis that aggregates revenue, ROAS, or conversion rates MUST account for the
`channel × industry × size_class` interaction. Flat aggregations that ignore this
heterogeneity MUST be explicitly flagged in output or documentation as potentially
misleading. The dataset's generative model conditions all conversion probabilities on
this interaction — analyses that flatten it will produce incorrect channel rankings.

## Technology Constraints

- **Language**: Python 3.11 (managed via `.python-version`)
- **Package manager**: `uv` — all dependency operations MUST use `uv`, not `pip` directly
- **Primary data source**: `data/raw/b2b_attribution.db` (SQLite) — preferred over CSV for
  any multi-table analysis; indices are pre-built on all FK and high-cardinality columns
- **Dashboards**: Streamlit or Dash per service — one `dashboard/app.py` per service
- **Testing**: `pytest` — tests live in `services/<name>/tests/`
- **Visualization**: All charts MUST use the shared theme from `shared/viz.py`

## Development Workflow

New service work follows this sequence:

1. Run `/speckit-specify` to create `specs/<service-name>/spec.md`
2. Run `/speckit-plan` to generate the implementation plan
3. Run `/speckit-tasks` to produce the task list
4. Implement following the task order; commit after each logical group
5. Run `/speckit-checklist` before marking a service complete

Each service-level `CLAUDE.md` MUST document: what the service computes, its inputs from
`data/raw/`, its outputs to `data/processed/`, and how to run its dashboard.

## Governance

This constitution supersedes all other practices in this repository. Any amendment MUST:

1. Update this file with a version bump following semantic versioning:
   - MAJOR: removal or redefinition of an existing principle
   - MINOR: new principle or section added
   - PATCH: clarification or wording refinement
2. Update the Sync Impact Report comment at the top of this file
3. Review dependent templates for alignment after any MAJOR or MINOR change

All implementation plans MUST include a Constitution Check section verifying compliance
with Principles I–V before proceeding to Phase 0 research.

**Version**: 1.0.0 | **Ratified**: 2026-05-20 | **Last Amended**: 2026-05-20
