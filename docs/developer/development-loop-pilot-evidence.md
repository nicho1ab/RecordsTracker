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
3. [#514](https://github.com/nicho1ab/RecordsTracker/issues/514) — completed Pilot Run 3.
4. [#466](https://github.com/nicho1ab/RecordsTracker/issues/466) — completed Pilot Run 4.

[#525](https://github.com/nicho1ab/RecordsTracker/issues/525) remains blocked
by the missing immutable approved-logo asset locator and SHA-256. Issues #465,
#499, and #580 were substantively ineligible. No genuine fifth qualified run
currently exists, so the candidate shortfall remains one.
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

## Run 3 — Issue #514

### Identity, lifecycle, and implementation

- Pilot run: 3 of 5; category: reviewer-facing copy-control consistency and accessibility correction; risk: medium; manual UI review: required and completed.
- Model: GPT-5.6 Terra; effort: High; suitability: eligible, bounded, reversible, and independently testable.
- Implementation issue: [#514](https://github.com/nicho1ab/RecordsTracker/issues/514); PR: [#598](https://github.com/nicho1ab/RecordsTracker/pull/598); implementation branch: `issue-514-consistent-copy-control`.
- Pre-squash head: `0057e76c94b4c100f8e756c0ad06078c1bdd2483`; squash SHA: `059c7a210c8137aa2eb3cc07699f917201e97e99`; merged UTC: 2026-07-24T16:47:41Z; Issue closed UTC: 2026-07-24T16:51:22Z.
- Scope: one commit, nine files, 224 additions, and 148 deletions.
- One shared idempotent copy-control behavior now provides compact native buttons, target-specific accessible names, adjacent readable values, independent copied/unavailable feedback and timers, focus retention, and exact displayed-value copying.
- Facility-name copy controls outside RT-CP-001 were removed. First investigation activity uses `Copy First investigation activity date`, removes visible `Copy date`, and copies only the displayed `MM/DD/YYYY` date. No copy target was added.
- Native evidence exposed visible raw JavaScript caused by an invalid shared-script composition boundary. The defect was corrected, regression-tested, and the final helper has one valid script boundary.

### Validation and evidence

- Pre-PR focused validation: 56 passed; merged focused regression: 236 passed; Ruff, targeted mypy, independent verification, secret scan, and diff hygiene passed.
- Required checks `validate`, `docs-check`, `fixtures`, and `security` passed twice. The broad application suite was not run because the documented trigger was not met.
- Accepted durable evidence: `data/processed/ui-evidence/20260724-162421Z-issue514-native-recapture` and `.zip`, SHA-256 `6e62d4b775c46166dee2a5893e785b5160e45d1cad23fb118d993c2dc234693d`; 13 files including 10 PNGs.
- Superseded, unaccepted evidence: `data/processed/ui-evidence/20260724-issue514-native-recovery` and `.zip`, SHA-256 `2678baf9cffa17a0a2064eb5828f5b11be918bfa88baa7b114b5e434012d7f63`; it showed visible raw JavaScript.
- Native reviewer-detail Tab focus and Enter activation passed, copying `06/12/2024`. Native facility-lookup Tab focus and Space activation passed, copying `900000001`. Focus retention, simultaneous feedback, timeout behavior, 720px narrow, 390px mobile, and raw-script absence were accepted.
- Clipboard-unavailable visual evidence was unavailable; deterministic rejection coverage was accepted. No suitable read-only case-brief fixture existed, so focused renderer/shared-helper coverage was accepted. Actual browser 200% zoom was unavailable and not claimed. Human review accepted these limitations.

### Measurements, findings, and suitability

- Blocked pre-implementation attempts: 1; elapsed: 1 minute 38 seconds; root cause: defective prompt requirement for blocked-state labels/comments on Issues #525 and #533.
- Implementation elapsed: 11 minutes 9 seconds; implementation iterations: 1; cumulative correction iterations: 7; human workflow interventions: 2; cumulative evidence attempts: 4; usage/cost: unavailable.
- Human review removed facility-name copy targets, corrected the understated original changed-file count, used supported Playwright/Edge after the in-app browser could not establish native Tab focus, and rejected the defective evidence package before recapture.
- Stopping conditions worked: the initial precheck failed closed, the first evidence attempt did not fabricate focus, and defective evidence was preserved as superseded and recaptured only after correction. No deployment or production mutation occurred.
- Run 3 supports retaining strict evidence and human-acceptance gates. Native browser evidence should use the supported Playwright/Edge route when the in-app browser cannot provide genuine keyboard input. Existing Issue #587 controls are sufficient; no new governance issue or ADR is warranted, and this run does not authorize greater automation.

## Run 4 — Issue #466

### Identity and lifecycle

- Pilot run: 4 of 5.
- Issue: [#466 — Define how zero-result reviewer CSV exports should work](https://github.com/nicho1ab/RecordsTracker/issues/466); PR: [#603](https://github.com/nicho1ab/RecordsTracker/pull/603).
- Pre-squash implementation commit: `a38e45a1cafabadda57ab24e3d7ffbc9709d6a58`; squash commit: `946af266f87aa7e6fac7aebf2b2faea380e0e061`; merged UTC: 2026-07-24T19:32:41Z.
- Issue qualification occurred before implementation, and Issue #466 was selected as Pilot Run 4 before its branch and worktree were created.
- Issue #466 closed as completed only after the verified merge.

### Scope and outcome

- One implementation commit changed three files with 38 additions and 63 deletions: a bounded reviewer CSV renderer, focused tests, and user documentation.
- No schema, source, ingestion, deployment, QNAP, production-data, authentication, authorization, security-policy, or privacy-policy change occurred.
- Successful zero-result exports return the ordinary shared 38-column header and zero data rows; no synthetic complaint, status, metadata, blank, unrelated, or sentinel row is emitted.
- One-result and multiple-result exports retain the ordinary complaint rows and schema. Filtering, authorization, deterministic ordering, HTTP success, CSV content type, source semantics, and accessible browser guidance remain unchanged.

### Validation

- Independent zero-result regression passed; focused CSV and filter tests passed (17 passed); directly affected reviewer tests passed (112 passed).
- Targeted Ruff, targeted mypy, documentation checks, independent-verification contract, secret scan, diff and hygiene checks all passed.
- Required GitHub checks passed: `validate` (30118839132), `docs-check` (30118839154), `fixtures` (30118839059), and `security` (30118839069). Within `validate`, Lint, Type check, Tests, Documentation check, required workflow-contract verification, and PR-evidence and governed-boundary verification passed.
- The broad application suite was not run because no documented trigger applied to this bounded renderer, focused-test, and documentation change. No required check or test obligation was weakened.

### Accepted evidence

- Accepted ZIP: `data/processed/issue-466-csv-evidence.zip`; SHA-256: `cbb3e00f65db31a5b27c244957a5e04e1f6cfbbb54ad02b686683fc01361d2d8`; package members: six.
- Zero-result, one-result, and multiple-result data-row counts were 0, 1, and 3. Shared ordered 38-column schema equality, field-count consistency, deterministic ordering, and the zero-result no-sentinel result passed.
- Spreadsheet-compatible consumer review was accepted. Excel-specific and Power BI-specific application behavior were not separately tested.

### Iterations and failure recovery

- Implementation iterations: 1; source correction iterations: 3; PR-body correction iterations: 3; evidence attempts: 3.
- No implementation failure or source defect was recorded. The corrections addressed PR-body evidence defects and stale pull-request event-payload validation, not defective required checks.
- Live PR-body edits did not change the already captured event payload, and reruns reused that payload. This repository's workflows did not trigger on `ready_for_review`.
- A controlled close and reopen produced a fresh supported `reopened` event, and final validation against that fresh event succeeded.

### Governed workflow lessons

- Changed test files require explicit test-boundary disclosure. `Authorized change` is the correct disclosure when test assertions intentionally change without weakening required checks or coverage obligations.
- The event-payload and lifecycle observations above are limited to the repository evidence from Run 4; they do not support broader generalization or autonomous approval, merge, or issue closure.

## Pilot-wide status

- Completed runs: 4 of 5.
- Completed issues: #431, #573, #514, #466.
- Qualified unstarted candidates: 0.
- Unresolved candidate shortfall: 1.
- #525 remains unavailable pending an approved immutable logo asset locator and verified integrity hash.
- #533 remains blocked by incomplete five-run pilot acceptance.
- Pilot Run 5 remains unselected.
- Pilot-wide acceptance: incomplete.

Issue #587 is governance provenance, not a pilot run. The automation decision gate in [#533](https://github.com/nicho1ab/RecordsTracker/issues/533) must not begin until #532 acceptance gates are complete. No conclusion about broad autonomous suitability may be drawn from the completed runs.

## Open follow-up observations

1. Future RL-PREPARE prompts should use the repository's exact governed PR-evidence format rather than a custom summary.
2. A PR-body-only correction may require a fresh `pull_request` event because rerunning an existing workflow preserves the original event payload.
3. Candidate qualification remains the pilot's primary blocking risk, not implementation capability.
4. Manual UI evidence remains required for any authorized future Pilot Run 5 when its selected issue requires it.
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
