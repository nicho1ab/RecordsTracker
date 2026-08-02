# Issue #655 — Review Next recommendation region planning record

## Planning boundary and dependency state

- **Governing issue:** #655 — Add in-place Review Next recommendation carousel
  to Complaint Patterns.
- **Authoritative base and merge base:**
  `df37d11bf57ad91964465d910be4fd20a0becf37`.
- **Dependency:** #643 is merged at that base. Its accepted card hierarchy,
  canonical inventory route, return-context behavior, copy control, and local
  evidence remain controlling inputs.
- **Planning worktree and branch:** `<issue-655-worktree>` on
  `codex/issue-655-review-next-carousel`.
- **Granted phase:** planning and read-only baseline validation only. No
  reviewer-facing behavior is implemented by this record.

Issue #655 is limited to one focused in-place Review Next recommendation
region on the Complaint Patterns view. It must not turn the complete facility
inventory into a carousel, move recommendation ranking into browser code, or
change Licensing and Visit Activity, Complaint Activity Over Time, taxonomy,
semantic colors, chip rules, or bottom pagination.

## Governing inputs read

- Issue #655 and its comments; Issue #643 and accepted planning record; Issues
  #656 and #657 for exclusions.
- `AGENTS.md`, `.github/copilot-instructions.md`, `README.md`,
  `CONTRIBUTING.md`, `SETUP_INSTRUCTIONS.md`, `ARCHITECTURE.md`,
  `DESIGN_AND_USABILITY.md`, `ACCESSIBILITY_REQUIREMENTS.md`, and
  `TESTING_STRATEGY.md`.
- `docs/developer/codex-workflow.md`,
  `docs/developer/reviewer-ui-regression-contracts.md`,
  `docs/product/records-tracker-approved-design-decisions.md`, and
  `docs/developer/ui-evidence-review.md`.
- Current Complaint Patterns renderer, read service, controls, fixtures,
  focused tests, and #643 accepted local-fixture interaction index.

Applicable durable requirements include `RT-RC-001`, `RT-RC-005`,
`RT-RC-006`, `RT-PAG-001`, `RT-RWD-001`, `RT-A11Y-001`, `RT-CF-642`, and the
Compare Facilities requirements in `ACCESSIBILITY_REQUIREMENTS.md`. There is
no Issue #655-specific approved Figma frame or motion token in the materials
reviewed. Implementation must not invent a controlled visual variance.

## A. Current recommendation-model trace

| Layer | File and symbol | Inputs and provenance | Output and deterministic rule |
| --- | --- | --- | --- |
| Authorized source-derived read | `src/ccld_complaints/hosted_app/auth.py`, `list_authorized_facility_intelligence_page` | Authorized corpus and import-batch scope; source-derived records only | Delegates to the read model after authorization. Reviewer-created state is not an input to ranking. |
| Read-model membership and page | `src/ccld_complaints/hosted_app/source_derived_reads.py`, `list_facility_intelligence_page` | `FacilityIntelligenceReadFilters`, source coverage, date/finding/topic/facility/geography filters, and seek continuation | Builds the filtered facilities relation, applies database-level keyset pagination (25 facilities), and returns current-page identities plus a matching total. |
| Priority order | `source_derived_reads.py`, `_facility_intelligence_order_spec` | Computed facility aggregates: substantiated count, complaint count, strongest delay, latest activity; normalized source-derived name and stable identity | Priority order is substantiated count descending, complaint count descending, strongest delay descending, latest activity descending, normalized facility name ascending, then normalized facility identity ascending. The final two terms are stable tie breakers. Other display sorts are distinct server orders. |
| Current Review next marker | `source_derived_reads.py`, `list_facility_intelligence_page` and `FacilityIntelligencePageRead.review_next_facility_identity` | Same filtered authorized relation, priority order only | Runs a separate bounded ordered `LIMIT 1` query and returns only one facility identity. It is independent of display sort and current result page. No predecessor, successor, rank, total sequence, or cursor is returned. |
| Summary hydration | `src/ccld_complaints/hosted_app/reviewer_ui.py`, `_facility_priority_summaries`, `FacilityPrioritySummary`, and `FacilityPriorityComplaint` | Source-derived complaint rows deduplicated by stable complaint identity; normalized facility identity; source availability | Produces facility-level computed counts and ordered complaint tuples. Facility fields are source-derived or computed; no reviewer-created status supplies ranking or a recommended complaint. |
| Recommended complaint | `reviewer_ui.py`, `_facility_priority_complaint_sort_key` and `_render_facility_intelligence_result` | Complaint activity date and source record key | Each visible facility selects only `summary.complaints[0]`: dates newest first, missing dates last, then source record key ascending. This is a computed deterministic selection from source-derived complaints. |
| Route and card | `reviewer_ui.py`, `_facility_intelligence_response`, `_render_facility_intelligence_results`, `_render_facility_intelligence_result` | Read-model page, filters, pagination, reviewer state kept separate | Renders every facility in the canonical inventory. Only the matching `review_next_facility_identity` gets the `Review next` marker. The card’s Facility Overview, canonical inventory count, and complaint links carry approved return context. |
| Current regression coverage | `tests/unit/test_hosted_facility_priorities.py`, `tests/unit/test_hosted_ccld_facility_lookup.py` | Fixture and route contracts | Proves deterministic priority/tie order, card rendering, authorized destinations, canonical Facility Overview inventory, filters, continuations, and return context. It does not prove a predecessor/successor sequence because none exists. |

### Current-model conclusion

The existing system provides:

- one full-filtered-corpus recommended **facility**;
- one deterministic recommended **complaint per rendered facility**;
- a complete ordered database relation usable as a future server implementation
  input; and
- **not** an exposed ordered recommendation sequence, position, next item, or
  previous item.

The marker therefore cannot safely be treated as evidence that a browser-side
carousel sequence already exists.

## B. Recommendation-unit decision

The smallest consistent unit is a **facility plus that facility's already
deterministic recommended complaint**. The facility is the ranked unit because
the current marker and source query are facility-level; the selected complaint
is carried with it so the region preserves the existing direct complaint action
and its identity context.

**Approved decision:** Previous and Next advance facility-and-recommended-
complaint pairs. The facility remains the ranked unit; the existing deterministic
recommended complaint travels with it. Browser code neither ranks nor selects
the unit.

## C. Proposed server-governed sequence contract

The server, after the existing authorization and all active filters, must own
membership, priority ordering, item position, and predecessor/successor. It
must not ship all ranked facilities to JavaScript for ranking or slicing.

| Contract concern | Proposed server behavior |
| --- | --- |
| Membership | The same authorized, deduplicated, filtered source-derived facility relation that currently feeds the `LIMIT 1` Review next query. Display pagination and user-selected display sort do not alter the recommendation order. |
| Item order | Existing priority order exactly: substantiated count desc, complaint count desc, strongest delay desc, latest activity desc, normalized facility name asc, normalized facility identity asc. Preserve the current database tie terms. |
| Complaint in item | Hydrate the existing first deterministic complaint only for the current recommendation item, using the existing complaint sort rule. Do not change Review next selection or hydrate a full complaint inventory. |
| Response | Add a bounded recommendation projection: current item, `position`, `total`, first/middle/last booleans, and canonical Previous/Next URLs or opaque server cursors. The projection must be derived in SQL/keyset form, not application-memory full-corpus aggregation. |
| First/middle/last | First has no previous destination; last has no next destination; one-item has neither. Controls are semantically unavailable, not merely visually dimmed. |
| Empty/unavailable | A filtered-empty relation renders a truthful unavailable state with recovery through existing filters; it does not fabricate a recommendation. Source-unavailable remains the item’s source state, not a missing sequence state. |
| Stability | Bind the opaque recommendation cursor to a version, active filter fingerprint, priority anchor, and expected corpus identity/count sufficient to reject mismatched state deterministically. Do not expose internal facility identity as a browser state mechanism. |
| Invalid/stale cursor | A malformed or incompatible cursor must be rejected by the server without substituting a different facility silently. The direct-GET error/recovery wording and the enhanced-response status need owner approval before coding. |

The current `FacilityIntelligencePageRead` lacks this projection, so adding it
is an Issue #655 server/read-model change for a later authorized implementation
phase. `RT-PAG-001` remains controlling: no facility-page OFFSET, full-corpus
application-memory slicing, or duplicate inventory.

## D. Current partial-page mechanisms and recommendation

| Existing mechanism | Reuse value | Risk and required boundary |
| --- | --- | --- |
| `src/ccld_complaints/hosted_app/compare_facilities_controls.py`, `FACILITY_INTELLIGENCE_CHIP_SCRIPT` | Canonical GET fetch, parsed response replacement, `pushState`, `popstate`, focus restoration, and no-JavaScript anchors are proven by #642. | It replaces the broad comparison dynamic region, reinitializes controls, and assumes filter-chip semantics. Reusing it directly for every Review Next change would replace too much and risks stale history/focus behavior. |
| `CHECKBOX_MULTISELECT_SCRIPT` | Shows idempotent data attributes and a singleton outside listener. | The Review Next controller must likewise avoid duplicate global listeners after region replacement. It must not change native multi-select semantics. |
| `reviewer_ui.py`, `_DETAIL_COPY_SCRIPT` | Existing #643 card controls provide tested copy behavior. | It binds document controls but exports no reusable initializer. A bounded replacement containing a facility-name copy control needs a small idempotent exported initializer or an explicitly different DOM composition; otherwise new controls would not be initialized. |
| `reviewer_ui.py`, `_COMPARE_FACILITIES_FOCUS_SCRIPT` | Shows hash-target focus on canonical full navigation. | It is not a replacement controller and cannot by itself define Review Next focus/history behavior. |
| Current `#facility-intelligence-dynamic-region[aria-live="polite"]` | Existing feedback announces changes. | Nesting a second live container around replacement card content would duplicate announcements. The new region needs a discrete status message, not a second live wrapper containing all card text. |

**Recommendation:** implement a narrowly separate, idempotent Review Next
controller later. It may reuse the canonical GET/DOMParser approach but owns
only the recommendation region and its message node. It needs one guarded
`popstate` owner, an `AbortController` plus monotonic request token, and a
small shared control-initialization seam. Filter changes must obtain the
server-rendered recommendation region for their new canonical state; this is a
targeted integration with #642, not a replacement of #642 controls.

## E. Proposed bounded recommendation-region DOM contract

**Proposed placement:** a single `section` immediately above the existing
complete facility inventory, not a replacement of that inventory and not a
second complaint inventory. It presents one compact facility-and-recommended-
complaint summary and links to the existing canonical destinations.

```html
<section id="review-next-region" aria-labelledby="review-next-heading"
         aria-busy="false" data-recommendation-cursor="…">
  <h2 id="review-next-heading" tabindex="-1">Review next</h2>
  <p id="review-next-position">Recommendation 2 of 4</p>
  <p id="review-next-status" role="status" aria-atomic="true"></p>
  <nav aria-label="Review next recommendations">
    <!-- canonical anchors without JavaScript; unavailable endpoint has no link -->
    <a rel="prev" href="…">Previous recommendation</a>
    <a rel="next" href="…">Next recommendation</a>
  </nav>
  <article class="review-next-card">…one facility and its one recommendation…</article>
  <p class="review-next-error" role="alert" hidden></p>
</section>
```

The compact summary may contain the same **facility** facts and one recommended
complaint needed for orientation and actions, but must not reproduce the full
contributor list, Source Record panel, reviewer-state form, or a second
canonical complaint inventory. The current full result list remains canonical.
The existing list marker must be reconciled with the selected regional item;
the server, not JavaScript, decides whether/how the matching list card is
marked when it is on the current page.

Loading keeps the last successful card visible, sets `aria-busy`, and disables
both activation paths. Error leaves the last successful card and URL intact,
restores the invoking control, and exposes concise visible recovery text plus
the ordinary-link fallback. Enhanced navigation focuses the new region heading
with `preventScroll`; the single status message announces displayed facility,
displayed complaint when applicable, and position exactly once.

### Approved placement and duplication boundary

The owner approved this compact section above the unchanged canonical list. It
may show only position, facility identity facts, one recommended complaint’s
identity/date/governed status or finding/source availability, and its two direct
actions. It must not repeat aggregate summaries, topic chips, contributor
records, Source Record panels, or reviewer-state controls.

## F. Canonical URL and history contract

- Retain `/ccld/facilities/intelligence` and all existing filter, display-sort,
  continuation, and `#facility-intelligence-results` state.
- Add one canonical opaque `recommendation` query value only after the server
  contract is approved. It represents the server-validated recommendation
  position/anchor; client code neither calculates rank nor substitutes an
  internal identity.
- Without `recommendation`, the server selects position one and renders the
  canonical first-item URL. Previous/Next destinations are ordinary canonical
  GET anchors for no-JavaScript use.
- Enhanced Previous/Next use `history.pushState` only after a matching
  successful response. `popstate` aborts active work and restores the region
  from the canonical URL without creating another history entry.
- Browser Back/Forward must restore filters, display sort, result-page
  continuation, recommendation item, visible card/orientation, and focus to
  the region heading (or a documented, visible fallback when that item is no
  longer present).
- Facility Overview and complaint-detail links retain their existing
  `origin=facility_intelligence` return context plus the canonical comparison
  URL, including `recommendation`; their return must restore the same item when
  still valid.
- A direct URL is a normal server-rendered request. Invalid/stale cursor
  response semantics are deliberately unresolved below rather than silently
  normalizing an unverified link.

## G. Focus, announcement, and orientation contract

| State | Focus and announcement |
| --- | --- |
| Pointer or keyboard Previous/Next success | Focus the replacement region heading with `preventScroll`; one polite atomic message names the facility, recommended complaint when shown, and `Recommendation X of Y`. |
| First/last/one item | Do not expose a focusable unavailable anchor. If a disabled enhanced button is used while loading, it has semantic disabled state and receives no success announcement. |
| Empty/unavailable sequence | Focus the visible unavailable-state heading and announce its truthful recovery text once. |
| Enhanced request failure | Preserve current content and focus on the invoking control; use one `role="alert"` error, no success message. |
| Browser Back/Forward | Restore the canonical item, then focus the region heading or a visible documented fallback. No duplicate status message from the broad comparison live region. |
| Ordinary full navigation | Standard server navigation and the existing focus/hash helper apply; links remain operable without JavaScript. |

## H. Motion and reduced-motion contract

The owner approved a controlled variance because no repository motion token or
Issue #655 Figma frame exists: 180 ms, `ease-out`. Next moves bounded outgoing
content left and incoming content from the right; Previous reverses direction.
Only the bounded region moves. `overflow: hidden` prevents document overflow,
reduced motion is immediate, and print hides the whole duplicated region.

## I. Concurrency and error behavior

- One request at a time: disable both controls, set `aria-busy`, retain current
  content, and use a request sequence number.
- An `AbortController` cancels the prior fetch when a newer activation or
  `popstate` occurs. A response whose sequence no longer matches cannot replace
  the region or update history.
- A non-200, malformed document, missing region, mismatched cursor, or
  recommendation no longer available is an explicit failure: no silent skip,
  no fabricated replacement, no stale `pushState`.
- Browser Back during an active request aborts the request and restores the
  canonical history URL.
- JavaScript unavailable, a failed enhanced fetch, and any console/network
  error preserve ordinary canonical GET links as the usable path.

## J. Responsive, zoom, and print contract

| Condition | Required behavior |
| --- | --- |
| Desktop and 1024 px | Compact region above the unchanged list; action order Previous then Next; no viewport jump or horizontal page overflow. |
| 768 px and 500 px | Controls wrap in logical DOM order without clipping, preserving descriptive names and visible focus. Card facts remain readable; no fixed-width slide track. |
| 400 px and 390 px | One-column logical order: heading/position, controls, current recommendation, actions. Touch targets remain usable; no off-canvas content. |
| Native 200% zoom | Same order and no horizontal document overflow; focus remains visible and unobscured. |
| Print | Suppress animation and interactive Previous/Next controls. Proposed disposition is to suppress the duplicate recommendation region and retain the existing complete canonical list, avoiding duplicated print content; owner approval is required. |

## K. Accessibility matrix

| Requirement | Implementation/test obligation | Governing source |
| --- | --- | --- |
| Semantic structure and reading order | One labeled section, ordered heading/position/controls/card, no hidden duplicate interactive content. | `ACCESSIBILITY_REQUIREMENTS.md` Structure; `RT-RWD-001`. |
| Descriptive links and keyboard | Native anchors/buttons have facility- or recommendation-specific names, logical tab order, and keyboard activation. | `ACCESSIBILITY_REQUIREMENTS.md` Keyboard access; `RT-RC-001`, `RT-RC-005`, `RT-A11Y-001`. |
| Focus and history | Visible focus survives replacement, Back, Forward, detail return, errors, and no-JavaScript navigation. | `RT-RC-005`; `RT-CF-642`; #642 continuity contract. |
| Announcements | One atomic polite status for a successful transition, `role="alert"` only for errors, no nested live-region duplication. | Screen-reader requirements; #655 acceptance language. |
| Disabled/unavailable state | Endpoint controls are non-focusable unavailable controls or semantic disabled controls, with visible text and no color-only signal. | `RT-PAG-001`; accessibility color/state requirements. |
| Motion | Direction does not encode meaning alone; reduced motion is immediate; outgoing content is inert/hidden from assistive technology. | `ACCESSIBILITY_REQUIREMENTS.md`; #655 accessibility boundary. |
| Reflow and touch | No horizontal overflow at 1024, 390, and native 200%; usable touch targets and logical mobile order. | Compare Facilities accessibility requirements; `RT-RWD-001`. |
| Print | Navigation and interactive controls omitted while canonical comparison evidence retains text meaning. | Compare Facilities print requirement; `RT-PRINT-001` where applicable. |

## L. Fixture and test matrix

### Current fixture inventory and gaps

The accepted #643 fixture packet has production-shaped facility and complaint
identifiers, populated/source-unavailable card states, canonical destination
links, and multiple facilities. It proves one selected marker and card behavior,
not sequence behavior. Current fixtures do not explicitly model all of the
following Issue #655 cases:

- three known ranked facilities with first/middle/last predecessor-successor
  assertions;
- a one-item sequence and a filtered-empty sequence;
- an explicit stale/malformed recommendation cursor;
- source-available and source-unavailable items at deliberate sequence
  positions;
- return from Facility Overview and complaint detail with an active
  recommendation cursor; and
- rapid/stale enhanced requests with controllable response ordering.

Later fixture changes must remain production-shaped, source/reviewer-separated,
and confined to #655 coverage.

### Required test matrix

| Scenario | Unit/service or route test | Browser evidence and negative assertion | Fixture need |
| --- | --- | --- | --- |
| First, middle, last | Server projection returns exact position, predecessor, successor, priority ties. | Previous/Next endpoint semantics; no wrong facility. | Three ranked facilities. |
| One item and empty/unavailable | Truthful no-controls/unavailable render; no fabricated complaint. | Focus/live wording and recovery; no fake next. | One-item and filtered-empty. |
| Pointer and keyboard Previous/Next | Native input changes exactly one server-selected unit. | Focus, announcement, card identity, no full viewport jump. | Deterministic sequence. |
| Rapid activation and stale response | Abort/sequence guard rejects stale replacement/history update. | No duplicate listener, duplicate announcement, or console error. | Delayed controlled response. |
| Failed enhanced request | Preserves card/URL/focus and exposes error; ordinary link still works. | Network classification and no false success. | Forced non-200/malformed route. |
| No-JavaScript and direct URL | Canonical anchors/direct GET render the same item. | No client ranking or hidden-only control. | Cursor fixture. |
| Back and Forward | Exact comparison URL, item, filter, sort, continuation, and visible focus restore. | Browser-state records before/destination/after. | Filtered, non-first-page state. |
| Facility Overview and complaint-detail return | Existing route and identity contracts retain recommendation state. | Correct facility/complaint and returned position. | Known facility/complaint pair. |
| Filters, sort, non-first result page | Server recomputes/rejects cursor correctly; pagination stays keyset. | No full inventory carousel or offset use. | Filter and continuation fixtures. |
| Reduced motion | Immediate replacement remains semantic and operable. | No transform animation or overflow under reduced-motion. | Standard sequence. |
| Desktop, 1024, 768, 500, 400, 390, 200% | Layout and controls reflow without clipping/overflow. | Screenshot geometry plus actual native zoom. | Long production-shaped values. |
| Print | Approved print disposition and no interactive controls. | PDF/page count and no duplicate inventory. | Populated/one-item where applicable. |
| Console/network cleanliness | No console/page errors, failed requests, or unexpected responses. | Packet summaries and classified zero/nonzero result. | Every operated route. |

## Evidence plan for a later authorized phase

Use a new timestamped local-fixture packet only after implementation. Capture
native pointer and keyboard operations for first/middle/last, a direct URL,
Back/Forward, filtered/non-first-page context, detail returns, one-item,
unavailable/error, reduced motion, desktop through 390 px, native 200% zoom,
and print. Include screenshot-state accounting, browser-state JSON, URL and
focus records, route assertions, console/network summaries, manifest/file
index/ZIP verification, and explicit no-horizontal-overflow checks.

The packet is local fixture evidence, not deployed-host evidence. It cannot
substitute for an independent visual review or owner acceptance. Every captured
state must be classified under the applicable UI-evidence gates and compared to
the approved design source after the outstanding design decisions are resolved.

## Scope exclusions and dependency boundaries

- **#656:** taxonomy expansion, semantic labels/colors, and cross-site chip
  treatment. #655 consumes currently governed values only.
- **#657:** bottom-pagination behavior. #655 preserves current keyset
  pagination and does not add bottom controls.
- **Outside #655:** Licensing and Visit Activity, Complaint Activity Over Time,
  schemas, migrations, ingestion, connectors, production data, deployment,
  reviewer-state semantics, and any full inventory carousel.
- **Potential follow-up:** an approved motion token/duration or a new Figma
  frame may require a separate design-governance decision if not supplied by
  the owner.

## Implementation phases after owner decisions

1. Resolve the owner decisions below and classify the exact approved design
   artifact/variance before code.
2. Add focused fixtures and service/read-model tests for the bounded,
   server-owned sequence; retain authorization, deduplication, priority, and
   keyset invariants.
3. Add the minimal renderer, canonical URL contract, no-JavaScript anchors,
   and separate idempotent enhancement controller. Keep #642 controls intact.
4. Add focused route/browser-contract tests for activation, failures,
   concurrency, history, returns, accessibility, reflow, zoom, and print.
5. Run focused validation, then perform separately authorized local browser
   evidence capture and visual review.
6. Stop for owner acceptance before any lifecycle preparation.

## Owner decisions resolved for implementation

1. Navigation unit: facility plus its deterministic recommended complaint.
2. Placement: compact region above the unchanged canonical list, with the
   explicitly limited identity, complaint, finding/status, source, and action
   facts approved by the owner.
3. Direct-GET state: malformed/tampered cursor is a clear invalid-state
   response; stale cursor recovers to the first item with the cursor removed
   and a visible polite notice.
4. The approved controlled variance is 180 ms `ease-out`; implementation and
   evidence must verify it does not create overflow, focusable hidden content,
   or a layout jump.
5. Print is approved to suppress the duplicate interactive recommendation
   region and retain the existing canonical inventory.

## Baseline validation record

The documented shared primary-repository Python interpreter was used from this
secondary worktree with cache disabled and a checkout-external temporary base.

```powershell
& '<primary-repository>\\.venv\\Scripts\\python.exe' -m pytest -p no:cacheprovider --basetemp <temporary-basetemp> \
  'tests/unit/test_hosted_facility_priorities.py::test_facility_intelligence_filters_reconciles_and_preserves_drilldown_context' \
  'tests/unit/test_hosted_facility_priorities.py::test_facility_intelligence_accessible_structure_and_safe_language' \
  'tests/unit/test_hosted_facility_priorities.py::test_facility_intelligence_filter_chips_keep_canonical_no_script_removal_urls' \
  'tests/unit/test_hosted_facility_priorities.py::test_facility_intelligence_continuations_preserve_filters_and_reject_bad_state' \
  'tests/unit/test_hosted_facility_priorities.py::test_facility_hub_reuses_intelligence_aggregates_state_and_tie_order' \
  'tests/unit/test_hosted_facility_priorities.py::test_facility_hub_renders_complaint_context_without_directory_row' \
  'tests/unit/test_hosted_ccld_facility_lookup.py::test_ccld_facility_review_hub_has_one_deterministic_primary_next_action' \
  'tests/unit/test_compare_facilities_controls.py::test_filter_chip_enhancement_uses_canonical_fallback_and_history_updates' \
  'tests/unit/test_hosted_ui_evidence_capture.py::test_issue_642_operated_capture_uses_native_input_and_records_state_metadata' -q
```

Result: `9 passed in 1.87s`.

An earlier collection command named a removed test symbol and therefore failed
before test execution; it was corrected by inspecting the current test names.
That was a planning-command selection error, not a product-test failure.
