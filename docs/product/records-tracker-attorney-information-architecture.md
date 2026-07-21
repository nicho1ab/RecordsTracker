# RecordsTracker Attorney Information Architecture

## Authority and status

This is the repository-readable product decision record for GitHub issue #501.
It governs later attorney-facing route, navigation, page-name, terminology, and
information-tier implementation. It does not itself change application
behavior.

The product owner approved the direction recorded here after inventorying the
current application and subsequently approved this repository-readable package
as a controlled design variance for #419, #502, and #503. The approved design
system remains Direction A — Civic Ledger in
`records-tracker-approved-design-decisions.md`. No editable Figma artifact was
changed. The variance preserves requirement mapping, pre-code variance
inventory, automated exact-route evidence, every applicable visual gate, and
explicit visual acceptance.

This record does not authorize a new route, redirect, route retirement,
retrieval, data mutation, source change, export change, authentication change,
deployment, or hosted operation.

## Attorney task model

The normal attorney experience is organized around six distinct destinations:

1. **Home** — choose the next RecordsTracker task.
2. **Find a Facility** — search for and select one CCLD facility.
3. **Compare Facilities** — compare authorized loaded complaint records and
   available public licensing or visit information across facilities.
4. **Complaint Worklist** — filter loaded complaint records and open the next
   complaint for review.
5. **Feedback** — report a problem, request, or confusing experience without
   private material.
6. **Help** — learn how to complete attorney tasks and understand official CCLD
   terms and RecordsTracker states.

Three governing questions keep pages aligned to attorney work:

1. Which facilities may need closer review?
2. What does the available public record show about this facility?
3. Which complaint or source record should I examine next?

Record retrieval is necessary workflow behavior, not a seventh global
destination. It appears after facility selection and retains its existing
bounded authorization and data behavior.

## Reviewer-facing route and page inventory

The inventory below reflects the application at the Issue #501 starting SHA.
Support endpoints and action endpoints are included because later route changes
must preserve their contracts even though they are not global destinations.

| # | Current route or endpoint | Current page or behavior | Primary attorney task | Unique behavior that must survive | Current tier |
|---|---|---|---|---|---|
| 1 | `/` | The same `Find a Facility` renderer used by Facilities | Choose the next task | None; the duplication is not a durable behavior | Reviewer |
| 2 | `/ccld/facilities` | `Find a Facility` search, typeahead, results, manual-entry guidance, planning links, and reference details | Find and select one facility | Governed facility search, selected-facility context, valid Facility ID continuation, and truthful unavailable/limited states | Reviewer with misplaced support detail |
| 3 | `/ccld/facilities/suggestions` | JSON suggestions for the facility input | Find and select one facility | Bounded suggestions and governed facility identity | Reviewer-supporting endpoint |
| 4 | `/ccld/facilities/detail` | `Facility review hub` or `Facility summary` | Understand and review one facility | Governed facility identity, exact contributing complaints, complaint/date summaries, source availability, reviewer-created state separation, and next-record actions | Reviewer |
| 5 | `/ccld/facilities/intelligence` | `Cross-facility intelligence` over the authorized loaded complaint corpus | Compare facilities | Authorization-before-read, keyset pagination, deterministic ordering, exact count-to-complaint reconciliation, filters, source-coverage states, and recommended-next actions | Reviewer |
| 6 | `/ccld/facilities/review-priority` | Priority table over uploaded public summary CSV fields | Compare facilities | Search; a bounded 100-row result; licensing/visit/citation/POC/status/capacity observations; deterministic cue ordering; and explicit separation from complaint-record coverage | Reviewer with misplaced operator counts |
| 7 | `/ccld` and `/ccld/` | Legacy entry to the record-request form | Find and select one facility | No independent attorney task | Reviewer alias |
| 8 | `/ccld/records/request` | `Request Records` facility/date intake and loaded-or-retrieve decision | Get complaint records for a selected facility | Facility/date context, loaded-record reuse, bounded authorized retrieval, validation, rate-limit/failure states, and safe no-match recovery | Reviewer contextual page |
| 9 | `/ccld/retrieval/jobs` | `Job diagnostics` history | Resolve a retrieval problem | Safe job status, counts, warning/failure summaries, and audit continuity | Operator/support |
| 10 | `/ccld/retrieval/jobs/detail` | `Job diagnostics detail` | Resolve a retrieval problem | Bounded job-specific diagnostics and recovery guidance | Operator/support |
| 11 | `/reviewer` | `Complaint records ready for review` list | Choose the next complaint | Canonical complaint worklist, filters, stable complaint identity, reviewer-created status cues, and record-specific actions | Reviewer |
| 12 | `/reviewer/records` | Alias rendering the same worklist as `/reviewer` | Choose the next complaint | Query/filter continuity only | Reviewer alias |
| 13 | `/reviewer/records/detail` | Complaint/control-number detail workspace | Review one complaint | Source-backed complaint evidence, original-source action, reviewer note/status actions, and return context | Reviewer |
| 14 | `/reviewer/records/substantiated` | Separate substantiated/equivalent worklist | Choose the next complaint | Official finding filter, deterministic paging/sort, and source-link coverage | Reviewer duplicate worklist |
| 15 | `/reviewer/records/serious-topics` | Separate serious-topic worklist | Choose the next complaint | Governed source-category and keyword-assisted-cue filters with cautious semantics | Reviewer duplicate worklist |
| 16 | `/reviewer/facilities/priorities` | Complaint-derived facility priority worklist | Compare facilities | Minimum complaint/finding filters, supported-indicator filters, governed factor explanations, pagination, and queue/detail links | Reviewer duplicate comparison |
| 17 | `/reviewer/facilities/trends` | Monthly or quarterly complaint activity comparison | Compare facilities | Time grain, bounded period count, date dimension, coverage states, deterministic anomaly cues, and exact contributing complaints | Reviewer specialized comparison |
| 18 | `/reviewer/records/matrix.csv` | Complaint-review matrix CSV | Export current review context | Authorized safe CSV fields and current filter/context parity | Reviewer contextual export endpoint |
| 19 | `/reviewer/records/substantiated.csv` | Substantiated/equivalent CSV | Export current review context | Official finding semantics and authorized safe CSV fields | Reviewer contextual export endpoint |
| 20 | `/reviewer/packet/preview` | Packet preview | Prepare review material | Read-only facility/date packet context, included-record reconciliation, source availability, and reviewer-state separation | Reviewer contextual page |
| 21 | `/reviewer/packet/draft` | Printable/copyable packet preparation draft | Prepare review material | Read-only print/copy preparation and explicit no-context state | Reviewer contextual page |
| 22 | `POST /reviewer/records/note` and `POST /reviewer/records/status` | Existing reviewer-created state actions | Record review progress | Authorization, audit, source-derived/reviewer-created separation, and return continuity | Reviewer action endpoints |
| 23 | `/ccld/help` | `Help` with a topic list and disclosure-heavy guidance | Learn a task or term | Task guidance, official-term definitions, troubleshooting, safety, and source limitations | Help |
| 24 | `/help` | Alias for `/ccld/help` | Learn a task or term | Link compatibility only | Help alias |
| 25 | `/feedback` | Safe tester feedback form and result states | Send feedback | Allowlisted context, private-material warning, configured/unconfigured/failure/success states | Reviewer/support bridge |
| 26 | `/operator/source-coverage` and child routes | Source-coverage summary, facilities, jobs, and CSV export | None | Operator-only authorization-before-read and safe deterministic diagnostics | Operator |
| 27 | `/source-records`, `/source-records/{id}`, `/facilities`, and `/facilities/{id}` | Fixture/sample list and detail pages, hidden outside fixture mode | None | Local fixture inspection only | Developer/debug |

Authentication placeholders, health endpoints, and `/api/*` contracts are not
attorney pages. Their security and data contracts remain unchanged.

### Unique behavior on the review-priority route

`/ccld/facilities/review-priority` is not another view of the authorized loaded
complaint corpus. It reads supported uploaded public licensing/visit/citation
summary CSVs through `load_active_facility_review_signals()`. It currently:

- searches by facility name, Facility ID, and facility type;
- returns at most 100 deterministically ordered facilities;
- derives labeled indicators for multiple signal types, complaint-visit
  activity, citation presence, POC-date presence, recent visits, 120-plus-day
  visit gaps, high capacity, and closed status;
- sorts by indicator count and rank, complaint/citation/POC counts, recent
  activity, facility name, and Facility ID;
- shows total visits, complaint visits, citation values, POC dates, last visit,
  status, and capacity; and
- reports loaded, unsupported, and malformed source-row counts that belong in
  operator/support diagnostics rather than the reviewer page.

These licensing and visit observations are useful, but they do not constitute a
distinct attorney destination. They must be preserved as a clearly labeled
`Licensing and Visit Activity` view or filter group inside Compare Facilities.
The implementation must preserve source-domain separation: public summary
observations cannot be blended into loaded-complaint counts or described as
complaint coverage. Operator source counts and malformed-row diagnostics move
to the operator/support tier.

## Route dispositions

`Disposition` uses only the Issue #501 categories. `Transition` states the
eventual legacy-route result; no transition is implemented by this record.

| Current route or endpoint | Disposition | Approved destination or role | Transition and preservation rule |
|---|---|---|---|
| `/` | retain | Home task launch | Replace the duplicate facility renderer only after approved Home frames exist. |
| `/ccld/facilities` | retain | Find a Facility | One facility input; preserve governed search and valid unmatched-ID continuation. |
| `/ccld/facilities/suggestions` | retain | Facility-search support endpoint | Keep bounded and non-navigational. |
| `/ccld/facilities/detail` | retain | Facility Overview | Keep the URL; change page naming and actions only from an approved frame. |
| `/ccld/facilities/intelligence` | retain | Compare Facilities | Canonical cross-facility route and global destination. |
| `/ccld/facilities/review-priority` | merge | Compare Facilities — Licensing and Visit Activity | Preserve every useful summary-field behavior first; then redirect the legacy URL with a deterministic equivalent view/filter. |
| `/ccld` and `/ccld/` | redirect | Find a Facility | Redirect to `/ccld/facilities`; do not preserve an ambiguous unselected request page. |
| `/ccld/records/request` | retain | Contextual Get Complaint Records step | Remove from global navigation; preserve selected facility/date and authorized retrieval behavior. |
| `/ccld/retrieval/jobs` | retain | Operator/support diagnostics | Keep out of primary navigation and reviewer Help. |
| `/ccld/retrieval/jobs/detail` | retain | Operator/support diagnostics | Keep safe job-specific recovery and audit context. |
| `/reviewer` | retain | Complaint Worklist | Canonical complaint-level destination. |
| `/reviewer/records` | redirect | Complaint Worklist | Preserve supported query parameters when redirecting to `/reviewer`. |
| `/reviewer/records/detail` | retain | Complaint Review | Keep record-specific and contextual, not global navigation. |
| `/reviewer/records/substantiated` | convert to view/filter | Complaint Worklist — Finding filter | Preserve official substantiated/equivalent semantics and paging before redirecting any legacy link. |
| `/reviewer/records/serious-topics` | convert to view/filter | Complaint Worklist — Serious review category filter | Preserve source-category versus keyword-assisted-cue meaning before redirecting any legacy link. |
| `/reviewer/facilities/priorities` | merge | Compare Facilities default ordering and filters | Preserve governed factor explanations and supported filters; do not keep a second facility inventory. |
| `/reviewer/facilities/trends` | convert to view/filter | Compare Facilities — Complaint Activity Over Time | Preserve time grain, coverage, anomaly, and contributing-record behavior before redirecting any legacy link. |
| `/reviewer/records/matrix.csv` | retain | Contextual Complaint Worklist export | No global navigation entry; preserve authorization and safe fields. |
| `/reviewer/records/substantiated.csv` | retain | Contextual filtered Complaint Worklist export | Keep until an explicitly governed export-route migration exists. |
| `/reviewer/packet/preview` | retain | Contextual Review Packet Preview | Reach from selected facility/worklist context. |
| `/reviewer/packet/draft` | retain | Contextual Printable Review Packet Draft | Reach from packet preview or selected review context. |
| Note/status POST endpoints | retain | Complaint Review actions | Preserve authorization, audit, and reviewer-created state exactly. |
| `/ccld/help` | retain | Help | Rebuild under #503 after approved Help frames. |
| `/help` | redirect | Help | Redirect to `/ccld/help` and preserve useful fragments. |
| `/feedback` | retain | Feedback | Keep a distinct global destination and safe context bridge. |
| Operator coverage routes | retain | Operator diagnostics | Never place in ordinary reviewer navigation. |
| Fixture/sample routes | retain | Developer/debug | Keep unavailable outside fixture mode and out of reviewer navigation. |

No route is approved for immediate retirement. A legacy reviewer URL may
redirect only after its unique behavior, supported query semantics, recovery
state, and automated evidence have moved to the approved canonical destination.

## Approved navigation

| Order | Current label and route | Approved label and route | Decision |
|---|---|---|---|
| 1 | `Home` — `/` | `Home` — `/` | Retain; make it a task launch. |
| 2 | `Facilities` — `/ccld/facilities` | `Find a Facility` — `/ccld/facilities` | Rename to predict the task. |
| 3 | No global link | `Compare Facilities` — `/ccld/facilities/intelligence` | Add the canonical cross-facility destination. |
| 4 | `Request Records` — `/ccld/records/request` | No global entry | Make record retrieval contextual after facility selection. |
| 5 | `Review` — `/reviewer` | `Complaint Worklist` — `/reviewer` | Rename to identify the object and task. |
| 6 | `Feedback` — `/feedback` | `Feedback` — `/feedback` | Retain as a distinct destination. |
| 7 | `Help` — `/ccld/help` | `Help` — `/ccld/help` | Retain as a distinct destination. |

The approved global order is **Home, Find a Facility, Compare Facilities,
Complaint Worklist, Feedback, Help**. Operator navigation remains a separately
authorized surface. Packet, export, record-request, record-detail, facility-
overview, job, and debug routes are contextual or tier-specific and must not be
added merely because they exist.

The current seven-step guided rail (`Start`, `Facility`, `Dates`, `Request`,
`Records`, `Review`, `Feedback`) is not a global information architecture. A
later implementation must remove it from pages where it implies one mandatory
linear path. Contextual progress may remain only where it helps complete an
active record request and is represented in the approved frames.

## Approved terminology

Official CCLD/source terms remain exact. `Substantiated`, `Unsubstantiated`,
`Inconclusive`, `STRTP`, `Type A citation`, `Type B citation`, and `Plan of
Correction` use the governed inline glossary treatment at first relevant use.
RecordsTracker-invented terms do not receive that deference.

| Context | Approved wording | Supporting description or use | Principal action | Empty or unavailable state | Recovery action |
|---|---|---|---|---|---|
| Home H1 | `Review CCLD Facility Records` | `Choose a task to find a facility, compare loaded public records, or continue complaint review.` | `Find a Facility` | `No recent-work claim is shown unless governed reviewer state supports it.` | `Find a Facility` |
| Facility discovery H1 | `Find a Facility` | `Search public CCLD facility information, then choose the facility you want to review.` | `Review Facility` | `Search for a facility to begin.` | `Clear Search` |
| Facility no match | `No facilities match this search` | State only what the active facility reference returned. | None | Do not imply that the facility does not exist. | `Check the search or enter a valid Facility ID.` |
| Valid unmatched Facility ID | `Facility not found in the directory` | `You can continue with this valid Facility ID even though no directory match is available.` | `Continue with Facility ID {id}` | Keep the entered ID visible. | `Change Facility ID` |
| Facility search unavailable | `Facility search is unavailable` | `You can continue if you already know a valid Facility ID.` | `Continue with a Facility ID` | Do not expose source files, fallback mechanics, or record counts. | `Try Again` |
| Compare Facilities navigation | `Compare Facilities` | Global destination for cross-facility review. | `Review Facility` | See comparison states below. | `Clear Filters` or `Try Again` |
| Compare Facilities H1 | `Find Facilities That May Need Closer Review` | `Compare authorized loaded complaint records and available public licensing or visit information. Open a facility or complaint to review the source.` | `Review Facility` | `No loaded complaint records are available to compare.` | `Find a Facility` or `Get Complaint Records` |
| Compare filtered empty | `No facilities match these filters` | Do not equate a filtered result with no public records. | None | Keep active filters visible. | `Clear Filters` |
| Compare load failure | `Facilities could not be loaded` | Do not render exception text. | None | Preserve the error as an application state. | `Try Again`; secondary `Feedback` |
| Summary-data view | `Licensing and Visit Activity` | `Available public visit, citation, Plan of Correction, status, and capacity information. This view does not show complaint coverage.` | `Review Facility` | `No licensing or visit activity is available for these filters.` | `Clear Filters` |
| Trend view | `Complaint Activity Over Time` | `Compare qualifying loaded complaint activity by month or quarter and open the contributing complaints.` | `Review Complaint` | `No complaint activity matches this period and these filters.` | `Change Dates` or `Clear Filters` |
| Facility page name/H1 | `Facility Overview` | `See the available public record for this facility and choose the next complaint to review.` | `Review Complaint {identifier}` when available; otherwise `Get Complaint Records` | `No loaded complaint records are available for this facility.` | `Get Complaint Records` |
| Record request H1 | `Get Complaint Records` | `Choose a date range for the selected facility. RecordsTracker will show already-loaded complaint records or request records when authorized.` | `Show Loaded Complaint Records` or `Request Complaint Records`, according to the governed state | `No loaded complaint records match this facility and date range.` | `Change Date Range`; request only when authorized |
| Worklist navigation/H1 | `Complaint Worklist` | `Filter loaded complaint records and open the next complaint you want to review.` | `Review Complaint {identifier}` | `No complaint records are ready for review.` | `Find a Facility` or `Get Complaint Records` |
| Worklist filtered empty | `No complaints match these filters` | Distinguish filtering from missing source data. | None | Keep the current filter state visible. | `Clear Filters` |
| Complaint detail | H1 remains the meaningful complaint/control identifier; page label `Complaint Review` | `Review the public complaint record, check the source when needed, and keep reviewer notes and status separate.` | Existing governed note/status actions | `Selected complaint record was not found.` | `Return to Complaint Worklist` |
| Packet preview | `Review Packet Preview` | `Check the included review context before preparing a printable draft.` | `Open Printable Draft` | `No facility and date context was supplied.` | `Return to Facility Overview` or `Complaint Worklist` |
| Packet draft | `Printable Review Packet Draft` | `Read-only preparation for browser print or approved internal copy.` | `Print` | `No facility and date context was supplied.` | `Return to Review Packet Preview` |
| Help | `Help` | `Find guidance by attorney task, product state, or official CCLD term.` | No competing primary action | `No help result matches this search`, if search is implemented | `Clear Search` |
| Feedback | `Feedback` | `Report a problem, request, or confusing experience without private material.` | `Submit Feedback` | Preserve configured, unconfigured, validation, failure, and success states. | State-specific `Try Again`, copy-safe fallback, or return action |
| Job support | `Record Request Diagnostics` | Safe operator/support status and recovery only. | State-specific support action | `No record-request jobs are available.` | `Return to Get Complaint Records` |

The following wording is superseded for future reviewer-facing implementation:
`Facility Review Intelligence`, `Cross-facility intelligence`, `Facility review
priority list`, `Facility review priorities`, `Facility Hub`, `Facility review
hub`, `Optional planning views`, `Reference data details`, `When to use lookup
vs. manual entry`, `Enter a Facility ID directly`, `Review Queue`, and
`Complaint records ready for review` as a page name. Historical changelog text
may retain those terms as history.

## Information tiers

| Tier | Information that belongs here | Information excluded here |
|---|---|---|
| Reviewer | Public facility identity; authorized loaded complaint facts; cautious review indicators; exact contributing complaints; compact source availability and original-source actions; reviewer-created notes/status; contextual record retrieval; packet preparation; safe exports; Feedback | Source file names; loaded/unsupported/malformed reference counts; fallback mechanics; hashes; raw paths; connector metadata; database identities; environment settings; stack traces; uncontrolled exception text |
| Help | Visible task instructions; official CCLD definitions; explanation of missing/unavailable/conflicting/not-applicable states; review-indicator limitations; troubleshooting; safe Feedback guidance | Environment setup; connector/import mechanics; raw artifacts; database or server instructions; operator commands |
| Operator/support | Reference snapshot and freshness; loaded/unsupported/malformed source counts; fallback/availability state; safe retrieval-job diagnostics; source-coverage summaries; bounded recovery guidance; audit-safe operational metadata | Secrets; cookies; tokens; auth claims; private URLs; private paths; raw narrative; stack traces; uncontrolled exceptions |
| Developer/debug | Fixture/sample pages; connector and import internals; schema and database diagnostics; raw-hash/path details where repository governance permits; local debugging guidance | Any exposure in production reviewer pages or ordinary Help |

Moving content out of the reviewer tier does not authorize deleting governed
diagnostics. #502 must identify the existing operator/support destination before
removing reference-source diagnostics from Facilities. If the current operator
coverage surface cannot represent a required diagnostic safely, implementation
must stop for explicit scope rather than hide or discard it.

## Responsive, keyboard, zoom, and print behavior

- **Desktop:** keep one compact primary navigation row when space permits. Keep
  one canonical facility or complaint inventory and an obvious primary action.
- **Narrow desktop:** allow navigation and action groups to wrap in document
  flow. Do not truncate labels, introduce a second navigation model, or detach
  controls from the value or row they affect.
- **Mobile/compact at 390 px:** stack navigation and filters in the same logical
  order; convert tables to labeled rows only where required; retain visible
  field labels; avoid horizontal page scrolling.
- **200% zoom:** use the compact reflow, not a scaled-down desktop layout. Fixed
  or sticky elements must not obscure headings, focused controls, or results.
- **Keyboard:** focus order is skip link, brand/home link, global navigation in
  approved order, page heading/main task, page controls, then contextual/help
  actions. Every control has visible Civic Ledger focus. Redirected or
  fragment-linked pages must place the user at a useful visible heading.
- **Meaning:** active navigation, selected filters, findings, coverage, warning,
  unavailable, and error states use text and semantics in addition to color.
- **Actions:** accessible names identify the affected facility or complaint.
  A repeated row action must say `Review Facility {name or ID}` or `Review
  Complaint {identifier}` to assistive technology even when the visible label
  is shorter.
- **State changes:** filtered results preserve the H1, filter summary, result
  count, and recovery action. Loading uses `aria-busy`; errors use an alert only
  when immediate announcement is appropriate; ordinary empty states do not
  masquerade as errors.
- **Official terms:** inline definitions work by keyboard focus and do not rely
  on hover alone.
- **Print:** hide global navigation, filters, copy buttons, form controls, and
  nonessential actions. Keep page title, selected scope, readable source-backed
  values, limitation text, and non-color status meaning. Print must not create
  a second complaint inventory.

No hamburger menu, tab widget, accordion, or new disclosure pattern is approved
by this decision record. A future approved Figma frame may define a compact menu
or view switch. Until then, implementations must use ordinary document-flow
navigation and controls already governed by the design system.

## Figma and design package

### Existing authoritative references affected

- Figma file `SYszaxbcMK8Ce2ywrUiu4q`, Direction A — Civic Ledger.
- `Product header and navigation` and the responsive stress proofs.
- `Facility review hub — populated` and `Facility review hub — partial and
  failed data states`.
- Cross-facility dashboard and pagination addendum node `59:463`, including
  nodes `59:469`, `59:505`, `59:541`, `59:577`, `59:613`, `59:649`, `59:685`,
  `59:721`, `59:757`, `59:793`, `59:829`, `59:868`, and `59:904`.
- Complaint inventory row, facility identity banner, recommended-next action,
  reviewer action rail, inline glossary, and permitted secondary disclosure.
- Reviewer-detail source-evidence node `64:2` only where the shared shell or
  page-name context appears; its bounded field-evidence behavior is unchanged.

### Exact Issue #501 frames and states still required

The following frames must be created or updated and labeled `Approved
implementation reference — variance requires approval`:

1. `Issue 501 — Product shell navigation`: desktop, narrow desktop, mobile 390
   px, 200% zoom, keyboard focus for every item, active state for every
   destination, long-label stress, and print-with-navigation-hidden.
2. `Issue 502 — Home task launch`: desktop, narrow desktop, mobile 390 px, 200%
   zoom, keyboard focus, no-recent-work state, long-content stress, and print.
3. `Issue 502 — Find a Facility`: initial, search results, selected facility,
   no match, valid unmatched Facility ID, malformed Facility ID, limited
   reference, source unavailable, keyboard focus, narrow desktop, mobile 390
   px, 200% zoom, long-content stress, and print.
4. `Issue 501 — Compare Facilities`: default complaint comparison, applied
   filters, filtered empty, no loaded complaints, partial coverage, unavailable,
   loading, error, pagination first/middle/last and disabled/focus states,
   `Licensing and Visit Activity`, `Complaint Activity Over Time`, source-domain
   separation, desktop, narrow desktop, mobile 390 px, 200% zoom, and print.
5. `Issue 501 — Facility Overview naming and actions`: populated, partial,
   complaint-data unavailable, facility-directory unavailable, invalid/not
   found, direct origin, Compare Facilities origin, keyboard focus, narrow
   desktop, mobile 390 px, 200% zoom, and print.
6. `Issue 501 — Complaint Worklist naming and filters`: default, substantiated
   filter, serious-review-category filter, filtered empty, no records,
   unavailable/error, keyboard focus, narrow desktop, mobile 390 px, 200% zoom,
   and print/export action placement.
7. `Issue 501 — Contextual record request`: selected facility, date selection,
   loaded-record path, authorized request path, validation, rate limit, no
   match, failure, unavailable, keyboard focus, narrow desktop, mobile 390 px,
   and 200% zoom.
8. `Issue 503 — Help by attorney task`: Get started, Understand the
   information, Manage review work, and Troubleshooting; working fragment
   navigation; target focus; no-result if search exists; permitted secondary
   disclosure; keyboard focus; narrow desktop; mobile 390 px; 200% zoom; and
   print.
9. `Issue 501 — Shared shell on contextual pages`: Complaint Review, Review
   Packet Preview, Printable Review Packet Draft, Feedback, configured/
   unconfigured/error/success states, and print where applicable.

### Package status

No editable Figma artifact was accessed or changed in Issue #501 repository
work. No new node ID or Figma approval is claimed. The visual design package is
**pending** as future Figma work, but the product owner explicitly approved this
repository-readable package as the controlled variance for #419, #502, and
#503. Dependent implementation must cite its requirement IDs, provide the
pre-code variance inventory, capture automated exact-route evidence, satisfy
applicable visual gates, and receive explicit visual acceptance.

## Approved requirement mapping

| Decision area | Applicable requirements | Issue #501 addition |
|---|---|---|
| Global destinations and canonical routes | `RT-ACT-001`, `RT-TIER-001`, `RT-RWD-001`, `RT-A11Y-001` | `RT-NAV-001` |
| One facility and complaint inventory | `RT-IA-001`, `RT-IA-002`, `RT-IA-003`, `RT-ID-001` | `RT-IA-004` |
| Plain-language naming and official terms | `RT-GL-001`, `RT-SAFE-001`, `RT-A11Y-002` | `RT-LANG-001` |
| Cross-facility consolidation | `RT-PAG-001`, `RT-STATE-001`, `RT-ST-001`, `RT-ST-002`, `RT-SRC-001`, `RT-DOM-001` | `RT-IA-004`, `RT-NAV-001` |
| Responsive and state coverage | `RT-RWD-001`, `RT-STRESS-001`, `RT-PRINT-001`, `RT-A11Y-001`, `RT-A11Y-002` | No variance approved |
| Reviewer/help/operator/developer separation | `RT-TIER-001`, `RT-SRC-001`, `RT-DOM-001` | No variance approved |

## Stale contract inventory

This is an Issue #501 inventory, not the reusable anti-fossilization process
assigned to #504. Dependent changes must classify each affected artifact under
#504 by using
`records-tracker-reviewer-redesign-artifact-governance.md`, and preserve durable
outcomes while rewriting superseded presentation assertions.

### Application and route contracts to change later

- `src/ccld_complaints/hosted_app/ui_shell.py`: current global labels/order,
  active-route grouping, and the seven-step workflow rail.
- `src/ccld_complaints/hosted_app/app.py`: Home delegates to Facilities; `/help`
  and `/ccld/` aliases; route dispatch and fixture/debug visibility.
- `src/ccld_complaints/hosted_app/ccld_facility_lookup.py`: obsolete Facility
  Hub, planning-view, reference-detail, lookup/manual-entry, review-priority,
  and Request Records wording and links.
- `src/ccld_complaints/hosted_app/reviewer_ui.py`: old cross-facility,
  facility-priority, trend, substantiated, serious-topic, Review Queue, and
  worklist page naming; duplicate route renderers; legacy form actions.
- `src/ccld_complaints/hosted_app/ccld_record_request_ui.py`: `/ccld` alias,
  Request Records naming, Help topic model, lookup/manual-entry context labels,
  and support diagnostics.
- `src/ccld_complaints/hosted_app/feedback.py`: route-title mapping still names
  Review Queue, Request Records, and Job Diagnostics.

These are implementation targets only. This issue changes none of them.

### Tests and exact-string assertions

- `tests/unit/test_hosted_app_scaffold.py`: primary navigation labels/order,
  Home/Facilities duplication, manual-entry disclosure, planning views,
  Request Records, and old H1 markers.
- `tests/unit/test_hosted_ccld_facility_lookup.py`: `Find a Facility`,
  `Facility review hub`, `Facility review priority`, `Cross-facility
  intelligence`, `Optional planning views`, `Reference data details`, lookup
  versus manual entry, direct Facility ID entry, and old action labels.
- `tests/unit/test_hosted_facility_priorities.py` and
  `tests/unit/test_hosted_facility_trends.py`: legacy route/page names,
  independent facility inventories, legacy links, and exact headings.
- `tests/unit/test_hosted_reviewer_ui.py`: `Complaint records ready for review`,
  independent substantiated/serious-topic pages, and old queue/action wording.
- `tests/unit/test_hosted_ccld_record_request_ui.py` and
  `tests/unit/test_hosted_ccld_retrieval_jobs.py`: Request Records and Job
  Diagnostics exact wording and recovery markers.
- `tests/unit/test_hosted_feedback.py`: old workflow-area and route-title copy.
- `tests/unit/test_hosted_ui_evidence_capture.py` and
  `tests/unit/test_hosted_acceptance_checks.py`: legacy route capture lists,
  active-navigation expectations, screenshot labels, and exact presentation
  markers.

Under #504, exact wording in the approved navigation, H1, state, and recovery
tables is governed. Tests should assert the user outcome and accessible result
for other copy instead of preserving full helper paragraphs, disclosure tags,
or old page structure.

Durable tests that must not be weakened include authorization-before-read,
operator/reviewer separation, stable public identifiers, facility/count
reconciliation, deterministic filtering and ordering, keyset pagination,
source-domain separation, official finding/cue semantics, reviewer-state audit
and preservation, safe export fields, no private/technical leakage, keyboard
semantics, non-color meaning, state truthfulness, and print safety.

### Evidence and acceptance contracts

- `scripts/capture-hosted-ui-evidence.ps1`: currently captures every legacy
  specialized route and checks old headings/nav markers.
- `scripts/verify-hosted-reviewer-acceptance.ps1`: route and marker contracts
  must follow canonical destinations and verify legacy redirects after parity.
- `docs/developer/ui-evidence-review.md`: lists separate facility-priority,
  intelligence, priority-worklist, trend, substantiated, and serious-topic
  route captures.
- `docs/developer/hosted-reviewer-acceptance.md`: names the legacy route set and
  page vocabulary as a passing workflow.

The replacement evidence must capture canonical views/filters and redirect
behavior, not silently drop the unique states currently covered by legacy
routes. Browser-observable focus, reflow, and redirect/query preservation remain
required; matching anchor text alone is insufficient.

### User and repository documentation

- `README.md` uses Facility Review Intelligence and describes direct facility
  ID entry as a first-class alternative.
- `CHANGELOG.md` contains both current Unreleased contracts and historical old
  route/page terminology. Update current product descriptions during
  implementation; do not rewrite accurate historical entries merely to remove
  old names.
- `KNOWN_LIMITATIONS.md` and `docs/user/known-limitations.md` describe
  lookup/manual-entry context and specialized intelligence/priority/trend views.
- `docs/user/getting-started.md`, `docs/user/searching-and-filtering.md`, and
  `docs/user/reviewing-records.md` teach old navigation, Facility Hub,
  specialized routes, and direct/manual entry.
- `docs/user/records-tracker-field-source-matrix.md` uses combined
  priority/intelligence destination language that must map to the canonical
  views without changing source-field meaning.
- `DESIGN_AND_USABILITY.md`, `ACCESSIBILITY_REQUIREMENTS.md`,
  `TESTING_STRATEGY.md`, the Product UX Lead Charter, the approved design
  register, and the remediation plan contain durable rules mixed with older
  page names. Preserve the rules and supersede only the route/presentation
  language identified here.

## Ordered implementation sequence

1. **Merge this repository-readable Issue #501 decision record.** No application
   behavior changes in this step.
2. **Consume the approved controlled variance.** The product owner approved
   this repository-readable package for #419, #502, and #503 without claiming a
   Figma update. Each dependent task must record the exact requirements it
   consumes, its pre-code variance inventory, automated evidence, gate results,
   and explicit visual acceptance. The named Figma frames remain useful future
   design work, not a prerequisite for this bounded sequence.
3. **Apply #504 classification governance.** Prefer merging #504 before the
   first dependent UI PR. If scheduling differs, each dependent PR must still
   classify every affected assertion and may not preserve superseded UI or
   weaken durable protections.
4. **Intermediate Compare Facilities consolidation.** Under separately explicit
   implementation authority, migrate complaint-derived priority behavior,
   complaint trends, substantiated/serious-topic entry points, and Licensing and
   Visit Activity to the approved canonical inventories/views. Prove parity,
   source separation, redirects, query mapping, pagination, reconciliation, and
   all states before removing any legacy rendering. The product owner assigned
   this work to #419; this design record does not itself authorize coding.
5. **Implement #502.** Build the distinct Home launch and single-input Find a
   Facility page; apply the six-link global navigation; move Request Records to
   contextual actions; remove reviewer-facing reference mechanics only after a
   safe operator/support destination is identified; implement valid unmatched-
   ID recovery; and update affected contracts/evidence.
6. **Implement #503.** Rebuild Help around the four approved category groups,
   visible primary guidance, working browser fragment/focus behavior, official
   point-of-use definitions, and tier-correct troubleshooting.

Issue #419 repository status: step 4 is implemented on its assigned branch.
Complaint Patterns, Licensing and Visit Activity, and Complaint Activity Over
Time are available under the canonical route, and the three legacy URLs use
query-preserving redirects. The repository evidence is ready for explicit owner
review; hosted/representative-data evidence, visual acceptance, and stakeholder
confirmation remain pending. This status does not start or complete #502 or
#503 and does not claim a Figma update.
7. **Run cross-route visual acceptance.** Capture exact canonical routes,
   merged views, legacy redirects, desktop, narrow, mobile 390 px, 200% zoom,
   keyboard focus, empty/partial/unavailable/error/loading states, and print.
   Classify all applicable approved requirement IDs and record explicit visual
   acceptance before merge recommendation.

Implementation may be split into reviewable branches, but no branch may leave
two equally promoted canonical facility or complaint inventories.

## Completion gates and non-goals

The repository information-architecture decision and its design authority are
complete because this record, its requirement mapping, and the explicitly
accepted controlled variance merged. The named Figma frames remain pending
future design work and must not be described as updated by this decision.

No dependent implementation may:

- invent a new dashboard, navigation destination, score, legal conclusion, or
  source-completeness claim;
- blend public summary observations with loaded-complaint coverage;
- retire or redirect a route before unique behavior and supported queries move;
- expose operator or developer mechanics to solve an attorney task;
- preserve an obsolete disclosure, heading, route, or helper paragraph solely
  because a test asserts it;
- weaken accessibility, authorization, privacy, source traceability, export,
  reviewer-state, pagination, or deterministic-reconciliation contracts; or
- treat this design record as authorization for application, data, deployment,
  or hosted changes.
