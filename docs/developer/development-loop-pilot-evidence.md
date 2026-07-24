# Governed Development Loop Pilot Evidence

## Purpose and governing issues

This durable evidence record supports the five planned pilot runs governed by
[Issue #532](https://github.com/nicho1ab/RecordsTracker/issues/532), under
[parent roadmap #527](https://github.com/nicho1ab/RecordsTracker/issues/527)
and its [independent-verification prerequisite #531](https://github.com/nicho1ab/RecordsTracker/issues/531).

Completed, stopped, and blocked runs use the same evidence fields. Pilot
completion requires every acceptance gate in Issue #532; one successful run
does not establish pilot-wide acceptance.

## Pilot controls

Human authority remains required for issue qualification, capability grants,
implementation review, PR readiness, merge, and closure. The pilot permits no
autonomous issue selection, approval, merge, deployment, or production-data
mutation.

The required checks remain `validate`, `docs-check`, `fixtures`, and `security`.
Independent verification is advisory to human approval and fails closed when
objective PR evidence is missing.

## Issue #587 provenance

Pilot Run 1's stale pull-request-event correction and Pilot Run 2's fixture,
native-interaction, zoom-exception, package-preservation, and squash-cleanup
lessons produced Issue #587. That issue hardens the controlling workflow and
evidence policy; it does not reopen, revise, or replace either completed run.

Each run records its model, effort, timestamps, iterations, interventions,
failures, checks, scope findings, usage/cost availability, and suitability.
Dependent work does not begin before prerequisite gates are complete.

## Pilot candidate status

1. [#431](https://github.com/nicho1ab/RecordsTracker/issues/431) — completed Pilot Run 1.
2. [#573](https://github.com/nicho1ab/RecordsTracker/issues/573) — completed Pilot Run 2.
3. [#514](https://github.com/nicho1ab/RecordsTracker/issues/514) — qualified, risk-medium, requires manual UI review, unstarted.

[#525](https://github.com/nicho1ab/RecordsTracker/issues/525) remains blocked
by the missing immutable approved-logo asset locator and SHA-256. Issues #465,
#499, and #580 were substantively ineligible. No genuine fourth or fifth
qualified run currently exists, so the candidate shortfall remains two.
Qualification criteria must not be weakened merely to fill the five-run target.

## Run 1 — Issue #431

### Identity and outcome

- Pilot run: 1 of 5
- Issue: [#431 — Report complaint coverage separately from facility-data gaps](https://github.com/nicho1ab/RecordsTracker/issues/431)
- Category: representative-coverage reporting correction
- Risk: medium
- Result: completed and merged
- PR: [#583](https://github.com/nicho1ab/RecordsTracker/pull/583)
- Squash SHA: `a17279903da1498f16ca97aa532e7123b12613d3`
- Merged UTC: 2026-07-24T03:38:56Z
- Completion comment: [Issue #431 completion evidence](https://github.com/nicho1ab/RecordsTracker/issues/431#issuecomment-5065923920)
- Final suitability: suitable for the governed workflow

### Model and effort

- Model: GPT-5.6 Terra
- Effort: High
- Usage/cost: unavailable

### Timing

- Implementation start: 2026-07-23 21:52:16 CDT (UTC-05:00)
- Implementation stop: 2026-07-23 21:57:48 CDT (UTC-05:00)
- Implementation elapsed: 5 minutes 32 seconds
- Human-review stop: 2026-07-23 22:01:40 CDT (UTC-05:00)
- Elapsed through human review: 9 minutes 24 seconds
- Merge completion: 2026-07-23 22:41:14 CDT (UTC-05:00)

No continuous total elapsed time is asserted.

### Iterations

- Implementation iterations: 1
- Correction iterations: 1
- Repository-code corrections: 0
- PR-evidence corrections: 1

### Human interventions

- candidate investigation;
- issue-contract clarification;
- readiness and risk labeling;
- explicit Pilot Run 1 authorization;
- human implementation review;
- narrow PR-evidence correction authorization;
- pull-request event-refresh authorization;
- explicit RL-MERGE authorization; and
- separate Issue #431 completion closure.

### Implementation result

Run 1 preserved the legacy `representative_coverage_status` as the conservative
overall result and added `complaint_coverage_status` and
`facility_reference_coverage_status`. Each dimensional result includes a
deterministic status, blockers, warnings, and non-validation language.

Complaint candidacy can be reported when complaint gates pass despite partial
facility-reference provenance, while facility-reference gaps remain visible and
the overall result remains conservative. Complaint provenance, traceability,
source-linkage, and stable-identity defects still block complaint candidacy.
Fixture, demo, and test exclusions remain unchanged. No validated-coverage or
stakeholder-acceptance claim was introduced.

### Changed files

- `README.md`
- `docs/developer/hosted-scaffold.md`
- `src/ccld_complaints/hosted_app/representative_coverage.py`
- `tests/unit/test_representative_coverage.py`

The pre-squash branch had one commit across four files: 217 additions and 8
deletions.

### Validation evidence

Objective implementation and CI evidence:

- focused representative-coverage tests: 16 passed;
- targeted Ruff: passed;
- targeted mypy: passed;
- documentation validation: passed;
- local independent-verification contract: passed;
- secret scan: passed;
- `git diff --check`: passed;
- full suite not run because the documented trigger was not met;
- required checks: `validate`, `docs-check`, `fixtures`, and `security`;
- required checks passed in both pre-merge watch cycles after the corrected PR evidence was evaluated; and
- fresh PR independent verification passed.

Human-review findings:

- human implementation review found no defect; and
- all acceptance criteria passed first human review.

### Failure and correction evidence

The initial draft PR body did not use the repository's machine-verifiable
governed-summary format. CI correctly failed `validate` at the independent
PR-evidence step. Implementation tests, linting, type checking, documentation,
workflow contract, fixtures, and security were not the cause.

The PR body was corrected under narrow authorization. Rerunning the old
workflow reused its original pull-request event payload and still evaluated the
stale body. PR #583 was then closed and reopened under narrow authorization to
generate a fresh `pull_request` event; the fresh CI run evaluated the corrected
body and passed. No repository-code or workflow change was required.

Future PR-body-only correction procedures should account for GitHub Actions
retaining the original event payload during reruns. This was an objective
PR-evidence defect, not noise or a false positive.

### Scope and boundary evidence

No change occurred to schemas or migrations; ingestion or source-connector
contracts; source authority or provenance classifications; canonical-data
semantics; production data or correction behavior; deployment or
infrastructure; security or privacy; authorization behavior; branch protection
or rulesets; required check names; or autonomous approval or merge behavior.

There was no deployment, QNAP access, production-data mutation, stash mutation,
broad cleanup, or unrelated branch, issue, PR, or worktree mutation.

### Cleanup and preserved state

The Issue #431 remote branch and local branch were deleted, and its worktree
registration was removed. The empty OneDrive-locked Issue #431 directory
remains and was not retried. Authoritative `main` synchronized to the squash
SHA. The parked Issue #532 worktree and protected stash were preserved. Issue
#431 was documented and closed as completed after merge verification.

### Suitability assessment

Run 1 is suitable for the governed workflow. One implementation iteration and
no code correction were sufficient, and human review passed all acceptance
criteria on first review. Independent verification detected an objective
PR-evidence defect before merge; narrow authorization corrected that metadata
defect without expanding repository scope. The fresh-event requirement exposed
a procedural improvement opportunity. No evidence supports reducing human
authority for qualification, review, readiness, merge, or closure.

## Run 2 — Issue #573

### Identity and outcome

- Pilot run: 2 of 5
- Issue: [#573 — Prevent inline definition popups from obscuring content](https://github.com/nicho1ab/RecordsTracker/issues/573)
- Category: shared glossary accessibility and collision-safe presentation correction
- Risk: medium
- Manual UI review: required and completed
- Result: completed and merged
- PR: [#585](https://github.com/nicho1ab/RecordsTracker/pull/585)
- Squash SHA: `6b949cb73cb90b5f3c7f72187400fb874d00b445`
- Pre-squash head: `b26e0d7590f0b37d7ce867502774fff096d466c3`
- Merged UTC: 2026-07-24T05:44:55Z
- Completion comment: [Issue #573 completion evidence](https://github.com/nicho1ab/RecordsTracker/issues/573#issuecomment-5066962358)

### Model, timing, and iterations

- Model: GPT-5.6 Terra
- Effort: High
- Implementation start: 2026-07-23T23:27:03-05:00 CDT
- Initial implementation stop: 2026-07-23T23:35:23-05:00 CDT
- Implementation elapsed: 8 minutes 20 seconds
- Implementation iterations: 1
- Correction iterations: 3
- Usage/cost: unavailable

### Human interventions

- human code review identified the duplicate-tooltip-ID accessibility defect;
- human UI review accepted the governed 720×600 reflow approximation after reviewing native interaction evidence; and
- readiness, merge, and Issue #573 completion remained separately human-authorized decisions.

### Objective implementation and validation evidence

The merged change has two commits across six files, with 190 additions and 40
deletions:

- `src/ccld_complaints/hosted_app/ui_shell.py`
- `src/ccld_complaints/hosted_app/reviewer_ui.py`
- `src/ccld_complaints/hosted_app/ccld_facility_lookup.py`
- `tests/unit/test_hosted_app_scaffold.py`
- `tests/unit/test_hosted_reviewer_ui.py`
- `tests/unit/test_hosted_facility_priorities.py`

Objective validation and merge evidence:

- duplicate-ID regression passed;
- focused glossary regressions passed;
- final affected hosted UI suite: 201 passed;
- targeted Ruff and mypy passed;
- independent workflow contract and independent PR-evidence verification passed;
- required checks `validate`, `docs-check`, `fixtures`, and `security` passed in both required watch cycles;
- the pre-merge secret scan passed;
- squash-diff integrity passed; and
- the post-merge combined local secret-scan invocation timed out and was stopped. This is not recorded as a security failure because both required Security checks and the pre-merge secret scan passed.

The full suite was not run because the documented trigger was not met.

### Corrections, evidence, and human judgment

The initial implementation included a lint-only assertion-wrapping correction.
Human code review then found repeated glossary terms producing duplicate tooltip
IDs. The shared renderer was corrected to assign unique definition IDs and valid
per-trigger accessible relationships. CI required one bounded compatibility
correction, producing the final correction count of three.

The first evidence package established reviewer focus and Escape behavior but
also identified that facility fixture `900000001` had no in-scope facility
glossary term, the initial browser mechanism did not establish native hover or
native Tab focus-loss, and actual browser-chrome 200% zoom was unavailable.

The second package used facility `157806098` and Python Playwright controlling
installed Microsoft Edge. Its 20 PNGs, manifest, and evidence index record
native reviewer and facility hover, Tab focus, Escape, focus loss, mobile edge
placement, unique IDs, and valid `aria-describedby` relationships. The durable
ZIP SHA-256 is
`60E6D0A8A6136CE407E1A1B500D312E5AC0A442F1DD8EADE3B4473B177235E88`.

After merge, the evidence directory and unchanged ZIP were preserved under
authoritative main's ignored `data/processed/ui-evidence` location before the
Issue #573 worktree registration and local and remote branches were removed.
The former Issue #573 path remains unregistered and was not cleaned manually.

One additional attempt confirmed that no installed supported mechanism could
establish and report browser-chrome-controlled 200% zoom. Human review accepted
the governed 720×600 reflow approximation together with the native desktop,
standard, mobile, hover, focus, Escape, focus-loss, and edge-placement evidence.
Actual browser-chrome 200% zoom and screen-reader product testing were not
performed or claimed.

### Scope and suitability assessment

No glossary terminology or definition text, route design, Figma artifact,
schema, migration, source, connector, ingestion, import, backfill, retrieval,
production data, deployment, QNAP, security, privacy, or authorization behavior
changed. The correction was suitable for the governed human-supervised workflow:
human review added material value by finding the duplicate-tooltip-ID defect,
and evidence capture required human judgment about fixture suitability and
acceptable reflow proof. Independent verification remained advisory. This run
does not support autonomous approval, merge, closure, or broader autonomy.

## Pilot-wide status

- Completed runs: 2 of 5
- Qualified unstarted runs: 1 (#514)
- Unresolved candidate shortfall: 2
- #525 remains blocked.
- #533 remains blocked by incomplete pilot acceptance.
- Pilot-wide acceptance: incomplete

The automation decision gate in [#533](https://github.com/nicho1ab/RecordsTracker/issues/533)
must not begin until #532 acceptance gates are complete. Pilot Run 3 is not
authorized. No conclusion about broad autonomous suitability may be drawn from
the completed runs.

## Open follow-up observations

1. Future RL-PREPARE prompts should use the repository's exact governed PR-evidence format rather than a custom summary.
2. A PR-body-only correction may require a fresh `pull_request` event because rerunning an existing workflow preserves the original event payload.
3. Candidate qualification remains the pilot's primary blocking risk, not implementation capability.
4. Manual UI evidence remains required for any authorized future Run 3.
5. The immutable logo-asset prerequisite must be resolved before #525 can be reconsidered.

These observations do not create implementation commitments or new issue scope.

## Coordination update measurements

- Coordination update implementation iterations: 1
- Correction iterations: 0
- Human intervention: authorization to record merged Pilot Run 1 evidence
- Usage/cost: unavailable
- Documentation-contract finding: no authoritative pilot-evidence document previously existed; this document is indexed as a required developer workflow record.
- Elapsed time: 2 minutes 19 seconds from the recorded documentation-edit start through final focused documentation validation (2026-07-23 22:48:03 to 22:50:22 CDT, UTC-05:00).

## Run 2 documentation update measurements

- Documentation implementation iterations: 1
- Documentation correction iterations: 1
- Human intervention: authorization to record completed Pilot Run 2 evidence after Issue #573 closure.
- Usage/cost: unavailable
