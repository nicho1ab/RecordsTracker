# Issue 420 Facility Overview redesign evidence

## Authority and bounded scope

Issue #420 (`STAKEHOLDER-007`) controls the single-facility reviewer page at
`/ccld/facilities/detail`. The product-owner task authorization dated July 27,
2026 supplies the bounded implementation and evidence specification for this
change. The repository-readable Issue #501 information architecture supplies
the approved `Facility Overview` page name, `Review Facility` contextual action,
route disposition, information tiers, responsive requirements, and controlled
design-variance rules. No editable Figma artifact is changed or claimed.

This work consumes `RT-DS-001` through `RT-DS-007`, `RT-IA-001` through
`RT-IA-004`, `RT-NAV-001`, `RT-LANG-001`, `RT-ID-001`, `RT-CP-001`,
`RT-CP-002`, `RT-DT-001`, `RT-TL-001`, `RT-GL-001`, `RT-ST-001`,
`RT-ST-002`, `RT-ACT-001`, `RT-DOM-001`, `RT-TIER-001`, `RT-SRC-001`,
`RT-STATE-001`, `RT-RWD-001`, `RT-A11Y-001`, `RT-A11Y-002`,
`RT-STRESS-001`, `RT-PRINT-001`, and `RT-SAFE-001`.

The change does not alter schemas, migrations, connectors, ingestion,
canonical source fields, facility-identity precedence, retrieval
authorization, PostgreSQL semantics, authentication, reviewer-created-state
writes, infrastructure, or deployment.

## Current-to-required mapping

| Current behavior | Root cause | Required outcome |
| --- | --- | --- |
| Facility identity is followed by a secondary facility-facts disclosure. | The renderer splits one governed facility projection across two presentation regions. | Render the approved available identity fields once near the top and consolidate missing values without repeated source-blank text. |
| Review summary metrics link to aggregate-specific contributor disclosures. | `_render_facility_contributor_sections` materializes the same complaint tuple once for every aggregate. | Keep one visible canonical complaint inventory and make aggregates filter or highlight its rows. |
| `Exact contributing complaints` contains repeated `<details>` lists. | The presentation model treats each aggregate as a separate record list instead of a view over stable complaint identity. | Remove the disclosure stack; each stable complaint identity appears once. |
| Complaint links use generic `Open complaint record` text. | Facility-level complaint context omits the existing governed complaint-subject helper. | Carry one bounded source-backed subject into each inventory row and use a clear `Review complaint` action. |
| Review summary and Review next repeat the same recommended complaint action. | Each section independently creates a primary action. | Keep one primary recommended-complaint action and highlight the same row in the canonical inventory. |
| Populated summaries include a separate Request Records button. | The earlier renderer exposed retrieval as a parallel primary action. | Keep record retrieval contextual and visually secondary; use state-specific language only when coverage is partial or unavailable. |
| Zero-record pages render Review summary, Review next, Additional review signals, Next actions, and repeated absence text. | The normal populated composition is invoked with an empty context. | Render facility identity plus one compact truthful empty state and one primary contextual retrieval action. |
| Source availability, findings, serious-review categories, trend cues, and reviewer state each produce parallel complaint lists. | Aggregate-to-record reconciliation is encoded as duplicated disclosure content. | Encode aggregate membership as row data and accessible filter controls over the single inventory. |
| Complaint detail return context is inherited from Compare Facilities calculations. | Facility Overview reuses the cross-facility detail-link builder unchanged. | Use Facility Overview return context so complaint review returns to the same facility/date/filter route. |
| Active capture asserts only legacy Facility Overview headings. | The evidence contract predates the canonical inventory and compact state design. | Add exact-route Issue #420 desktop, narrow, mobile, reflow, keyboard, filter, source-availability, reviewer-state, zero, partial, missing-value, and print evidence. |

## Artifact classification

| Artifact or assertion | Class | Disposition | Durable reason or requirement ID | Replacement evidence |
| --- | --- | --- | --- | --- |
| `/ccld/facilities/detail` route and supported query context | 1 and 3 | preserve | `RT-IA-004`; stable route and governed filter context | Route tests and exact-route evidence |
| Facility projection, source precedence, and conflict behavior | 3 | preserve | `RT-ID-001`, `RT-RC-004` | Projection tests and representative source reconciliation |
| Stable complaint deduplication and deterministic ordering | 3 | preserve | `RT-IA-001`, `RT-SAFE-001`, `RT-RC-006` | Aggregate and inventory reconciliation tests |
| Source-derived versus reviewer-created state separation | 2 and 3 | preserve | `RT-DOM-001`, `RT-RC-002` | DOM assertions and route evidence |
| Source URL availability and copy action | 2 and 3 | preserve | `RT-SRC-001`, `RT-CP-001`, `RT-CP-002` | Destination, accessible-name, and interaction evidence |
| `Exact contributing complaints` disclosure stack | 5 and 6 | remove | Superseded by `RT-IA-001` through `RT-IA-003` | One visible canonical inventory and duplicate-identity assertions |
| Aggregate-specific contributor list IDs and links | 5 and 6 | rewrite | Aggregate reconciliation remains durable; duplicate lists do not | Inventory filters, active-state announcement, and row highlighting |
| Repeated summary/next recommended actions | 6 | rewrite | `RT-ACT-001` | One primary action and highlighted recommended row |
| `More facility facts` disclosure | 5 and 6 | remove | `RT-ID-001`; approved reviewer identity fields have one home | Single identity block and missing-value-state evidence |
| Empty Review summary, Review next, signal, and action sections | 5 and 6 | remove | `RT-STATE-001`, `RT-RC-006` | Compact zero-record route evidence |
| Existing exact-string hub tests | 5 and 6 | rewrite | Preserve source, identity, accessibility, and reconciliation outcomes without obsolete structure | Outcome-based focused tests |
| Current evidence packet and screenshot labels | 5 and 6 | rewrite | `RT-UI-GATE-003` through `RT-UI-GATE-009` | Issue #420 route assertions, manifests, screenshots, and comparison report |
| Prior evidence ZIPs and released changelog entries | 7 | historical only | Accurate evidence of their captured commits | No rewrite |

## Pre-code variance inventory

1. Replace the disclosure-heavy contributor presentation with one default-visible
   semantic inventory. This is required by `RT-IA-001` through `RT-IA-003`.
2. Use compact aggregate filter controls with text counts, pressed state,
   visible highlighting, an accessible result announcement, a clear-filter
   control, and focus movement to the inventory heading. This implements the
   Issue #420 aggregate-to-record contract without a second inventory.
3. Reuse the existing source-backed complaint-subject helper; do not add or
   infer a canonical field.
4. Consolidate the facility identity projection into one top region containing
   the governed available name, Facility ID, facility type, license status,
   address, city, state, ZIP, county, and capacity. Combine unavailable labels
   into one truthful message.
5. Replace the empty composition with one compact state and one primary
   state-specific retrieval action. Omit irrelevant sections.
6. Retain the existing Civic Ledger and traffic-light semantic tokens and add
   only route-specific structural styles needed for the inventory, reflow,
   selected row, focus, and print.
7. Preserve underlying source metadata and reviewer-created state reads while
   keeping raw hashes, connectors, paths, database details, and diagnostics out
   of the reviewer tier.
8. Preserve all supported route query values and add Facility Overview return
   context to complaint-detail links.

## Prohibited interaction and presentation patterns

- No accordion, `<details>`, collapsed card, tab, or disclosure for the primary
  complaint inventory or its supporting records.
- No repeated complaint representation under findings, trends, source
  coverage, serious-review categories, or reviewer state.
- No generic contributing-record labels when a governed subject is available.
- No hidden score, unsupported legal conclusion, or source-completeness claim.
- No competing primary actions or repeated retrieval actions.
- No operator diagnostics, raw traceability values, or implementation mechanics
  in the reviewer tier.
- No generic teal-primary or decorative KPI treatment.

## Regression-contract adoption

Issue #420 consumes:

- `RT-RC-001` for usable complaint, source, retrieval, and return destinations;
- `RT-RC-002` for reviewer/operator information-tier separation;
- `RT-RC-003` for the shared inline glossary behavior;
- `RT-RC-004` for governed facility identity and truthful unavailable/conflict
  states;
- `RT-RC-005` for aggregate filtering, focus, viewport, action, responsive,
  and return continuity; and
- `RT-RC-006` for fixture relationships, stable complaint deduplication, one
  canonical inventory, and consolidated empty states.

These contracts remain only as enforced or partially enforced in the shared
registry. This issue records bounded route adoption; it does not claim that all
remaining Issue #608 work is complete.

## Post-implementation evidence

The bounded source change now:

- renders the governed facility identity once and consolidates unavailable
  labels;
- preserves the existing deterministic facility complaint aggregation and
  carries the governed complaint subject into one visible canonical inventory;
- exposes finding, serious-review, source-availability, reviewer-state, note,
  date, trend, and recommended-record filters as views over that inventory;
- gives the default state one deterministic primary complaint action and uses a
  `Show recommended complaint` action while an aggregate filter is active;
- keeps source-derived complaint facts and reviewer-created state in separate
  semantic regions and omits unavailable reviewer-state regions;
- preserves the Facility Overview route, dates, filters, and inventory focus in
  complaint-detail return context;
- replaces the repeated empty composition with one state-specific retrieval
  action and one secondary return to Find a Facility;
- uses visible coverage and interpretation limits, including the explicit
  absence of a governed stale-record threshold; and
- adds route-specific responsive, focus, and print styling without changing
  schemas, ingestion, source precedence, retrieval authorization, or
  reviewer-state writes.

Focused renderer, route, aggregation, scaffold, reviewer-detail, and
evidence-capture validation passes at the final source. The complete local
suite, repository-wide Ruff and mypy checks, documentation validation, secret
scan, PowerShell parsing, and `git diff --check` also pass.

The final exact-route fixture packet has no route, assertion, screenshot, or
automated UI-gate failures. It includes twelve screenshots, responsive and
focus measurements, source reconciliation, a print PDF, a complete file index,
and a verified ZIP. Direct inspection covered every screenshot plus live
desktop, 390-pixel mobile, filtered-empty, aggregate-filter focus, complaint
detail return, and print-contract states. `RT-UI-GATE-009` remains ready for
explicit product-owner review; automation does not claim visual acceptance.

Commit, push, draft PR creation, canonical PR-body preflight, natural required
GitHub checks, and the final Desktop product-owner package occur in the
authorized repository-lifecycle phase after this evidence gate.
