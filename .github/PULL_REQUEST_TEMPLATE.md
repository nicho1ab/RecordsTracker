# Pull Request Evidence

Complete every required section. Use `Not applicable - <reason>` only where the
template permits it. Self-reported evidence supplements, and never replaces,
the required GitHub checks.

## Governing issue and intended outcome

- Governing issue: <!-- Example: Closes #123 -->
- Intended outcome:

## Implementation scope

- Major files or components changed:
- Important behavior intentionally left unchanged or out of scope:

## Acceptance-criteria evidence

| Acceptance criterion | Evidence and result |
| --- | --- |
| <!-- One criterion per row --> | <!-- Test, diff, review artifact, or other concrete result --> |

## Validation and failure classification

List each exact command that was run. Use `Not run - <reason>` instead of
implying that unrun validation passed.

| Exact command | Result | Failure classification, if applicable |
| --- | --- | --- |
| `<!-- command -->` | <!-- Pass, fail, or not run --> | <!-- Implementation-caused, pre-existing, environmental, or none --> |

- Implementation-caused failures: <!-- None, or command and disposition -->
- Pre-existing failures: <!-- None, or command and evidence that it predates this change -->
- Environmental failures: <!-- None, or command and environment limitation -->
- Tests intentionally not run and why:

## UI and accessibility evidence (when applicable)

Complete this section only for UI or accessibility changes. Otherwise state
`Not applicable - no UI or accessibility change`.

- Evidence: <!-- Routes/states, viewport or zoom, keyboard/focus behavior, accessibility checks, print, and visual artifacts as applicable -->

## Documentation, assumptions, and remaining risks

- Documentation impact: <!-- Updated docs, or why no user-facing or documentation-impacting behavior changed -->
- Assumptions and limitations:
- Remaining risks or follow-up:

## Governed-boundary review

For every row, select `No change`, `Authorized change`, or
`Concern - review required`, and give a specific explanation. A generic statement
such as "all tests passed" does not satisfy this review.

| Governed boundary | Status | Specific explanation or evidence |
| --- | --- | --- |
| Schemas and migrations |  |  |
| Ingestion and source-connector contracts |  |  |
| Security and privacy |  |  |
| Production data and correction behavior |  |  |
| Deployment and infrastructure |  |  |
| Repository governance |  |  |
| Tests or checks weakened to obtain passage |  |  |

## Required GitHub checks

Record the current result without marking a pending or unrun check as passed.
These checks remain the authoritative merge gates.

- [ ] `validate`
- [ ] `docs-check`
- [ ] `fixtures`
- [ ] `security`
