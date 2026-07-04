# Design and Usability Governance

## Purpose

This document defines how the local review experience should become useful,
understandable, accessible, visually organized, and pleasant to use across the
current local attorney-review aid workflows and the production-discovery phase.

The initial proof of concept improved the Datasette and SQLite review workflow
with review views, metadata, saved queries, documentation, script guidance, and
source-traceable exports. Datasette is now retained as a validation, inspection,
debugging, local exploration, and export-support layer, not as the primary future
reviewer UX.

Future primary review UX work should prioritize persistent navigation, guided
queues, saved reviewer state, annotations, correction workflows, contextual help,
source traceability, accessible exports, and fewer-click reviewer paths before
considering more Datasette metadata or saved-query UX.

The minimum hosted reviewer workflows, review states, annotation boundaries,
correction boundaries, and tester-readiness expectations are defined in
`PRODUCTION_DISCOVERY_REQUIREMENTS.md`.

## Approved reviewer surface direction

RecordsTracker must become an attorney-facing public-record review workspace.
Default user pages are the reviewer surface and must show only information that
helps attorneys or advocates find a facility, select dates, request or load
records, review complaint records, prepare packet context, print or export, or
submit feedback. Technical, operator, diagnostic, source-mechanics, and
developer details must be preserved in the repository and product, but moved out
of the default reviewer surface when they do not support attorney use.

The approved surface model has three layers:

1. Reviewer surface: the default attorney-facing workflow.
2. Operator diagnostics surface: safe support and runtime visibility for
   administrators or operators, including job states, import counts, diagnostic
   summaries, setup checks, and safe operational metadata.
3. Developer debug surface: local/dev-only implementation detail for maintainers,
   including deeper import, source, and debug details that are not appropriate
   for normal users.

Operator diagnostics must not expose secrets, tokens, private URLs, raw server
paths, stack traces, raw artifact contents, or private material. Developer debug
details must stay local/dev-only unless a later approved task explicitly creates
a safe operator diagnostic view.

All reviewer-facing information must support attorney use. Existing page content
must be removed, refactored, hidden, or reorganized when it does not support
attorney use. Preserve technical, operator, and developer work by moving it to
the correct surface instead of deleting it.

Before any reviewer-facing UI implementation branch, ChatGPT or Codex must
provide a numbered page-change inventory and wait for the user's numbered
approval. The inventory must include the page or route; visible content or
interaction to remove, refactor, or reorganize; why the change supports attorney
use; what operator or developer detail is preserved elsewhere; and whether it
affects feedback, print/export, loaded records, reviewer-created state, or
source-related diagnostics. A design-exploration step using Figma AI or similar
design tooling may be included when useful before implementation.

Every design-affecting handoff must describe what changed, on which pages, and
why it improves attorney use.

## Intended users

The local review experience must support:

- Researchers and analysts reviewing public facility complaint history.
- Advocates reviewing public licensing records.
- Developers maintaining source connectors, extraction logic, schemas, and tests.
- Non-technical reviewers using local Datasette inspection views, CSV exports,
  and future primary review workflows.

The experience should assume that some reviewers are unfamiliar with database
terms, schema names, extraction confidence, or delay calculations.

## Current local review workflows

The local review experience should make these workflows easy to complete:

1. Open the local Datasette database after running a sample or live fetch script.
2. Start with review views rather than normalized implementation tables.
3. Filter complaints by facility number or facility name.
4. Review complaint dates, findings, allegation summaries, and review flags.
5. Inspect source traceability before relying on extracted fields.
6. Compare facility-level complaint counts and date ranges.
7. Export filtered review views or saved-query results as accessible CSV files.
8. Share notes using cautious language that preserves source limitations.

Reviewers should not need to understand every canonical table before completing
basic browsing, triage, source checking, or export tasks.

## Future primary review UX requirements

The future primary review experience should make these workflows easy to
complete without relying on Datasette as the main interface:

1. Resume review with persistent navigation and saved state.
2. Work through guided queues organized by reviewer task, facility, source
  traceability status, review flags, correction needs, and annotation state.
3. Add annotations without changing the preserved raw source record or
  canonical extracted fields.
4. Propose, review, import, or apply corrections with auditability and source
  traceability.
5. See contextual help at the point of use for fields, review flags, source
  traceability, limitations, and export cautions.
6. Export accessible, source-traceable review packets with clear headers and
  cautious public-source language.
7. Complete common reviewer paths with fewer clicks than the retained Datasette
  validation workflow can reasonably provide.

The future workflow must clearly distinguish source-derived values from
reviewer-created state such as review status, annotations, proposed corrections,
tester feedback, and export packet inclusion decisions. Status labels must not
imply source facts, legal conclusions, facility-wide conclusions, or verified
harm beyond what qualified reviewers establish from source records.

The first browser-accessible hosted reviewer UI shell is now a local/test,
server-rendered HTML surface at `/reviewer` and `/reviewer/records`. Its design
purpose is functional validation, not polish: local testers can list/search a
seeded source-derived record, see list-level reviewer-created note/status
indicators, open detail, inspect safe source traceability fields and safe
related seeded bundle context, add a reviewer note, set a reviewer status, and
see read-after-write reviewer-created state. Empty, invalid-form, and blocked
states should give clear next steps such as clearing search, returning to the
reviewer list, selecting a seeded record, or retrying valid note/status input.
Narrative
source fields are hidden in the browser shell. It must keep source-derived values visibly separate
from reviewer-created notes/statuses, keep local/test limitations visible, use
semantic headings, tables, labels, and accessible buttons, avoid color-only
meaning, and avoid unsupported legal, facility-wide, completeness, harm, abuse,
neglect, liability, or rights-deprivation conclusions.
Reviewer detail pages should orient first-time testers with a concise record
summary, clear source-traceability explanation, related source/facility/context
sections, visible reviewer-created state summaries, understandable note/status
actions, clear saved-state confirmations, CCLD queue/request/help navigation,
and feedback clues for reporting missing or confusing records.
Reviewer detail facility-context cues should name whether the selected record is
being reviewed from a directory-backed facility hub, a signal-only facility hub,
or a manual request context when the active local/test inputs support that
distinction. They should make next actions visible for returning to the facility
hub, returning to the facility review priority list, returning to the same queue,
opening packet preview/draft, starting a complaint request, and reporting
confusing detail context, while preserving not-source-verification, not-
complaint-coverage, not-source-completeness, and not-legal-finding boundaries.
Reviewer detail source traceability should help testers identify the selected
complaint record, distinguish source-derived identifiers from reviewer-created
state, understand which traceability fields are visible or missing in the
local/test record, and avoid treating missing local/test values as public-source
absence, completeness, legal, facility-wide, harm, abuse, neglect, liability, or
automated-finding conclusions.
When a queue, reviewer detail, packet preview/draft, or feedback cue summarizes
source traceability, it should use the same visible convention: name available
source traceability values, name missing local/test traceability values, remind
testers to check source traceability before relying on source-derived values,
and state that missing local/test traceability is not source-completeness proof.
Reviewer detail source-confidence cues should stay presentation-only and should
use existing source-derived fields, traceability fields, missing-value flags, and
proxy flags only. They may tell testers which loaded complaint values are
present, which expected values are not available in the local/test record, and
when an existing proxy flag applies, but they must not create confidence scores,
automated source verification, source-completeness assertions, source absence
claims, legal conclusions, or new source-derived fields.
Source-confidence next-step cues should be explicit but bounded. When a queue,
reviewer detail, help topic, or feedback prompt names a missing, confusing, or
proxy-related source-derived value, it should direct testers to check reviewer
detail source traceability, use only cautious reviewer-created note/status
wording when helpful, use feedback when the cue or wording remains unclear, and
continue review from the same queue context. It must not imply that the app has
verified, completed, corrected, assigned, claimed, or legally sufficed a source
record.
Reviewer detail field-note guidance should help testers turn those cues into
cautious reviewer-created observations. It should use short examples or action
phrases only as visible writing guidance; it must not generate notes, store note
templates, create new note fields, edit source-derived records, or imply public-
source absence, record completeness, official findings, legal conclusions, or
facility-wide conclusions.
Hosted correction-readiness guidance should stay presentation-only. It should
tell testers to check source traceability first when a source-derived value looks
wrong or incomplete, describe the possible correction concern in a reviewer-
created note for now, and use feedback when the correction path is confusing,
the record appears unexpected, or the tester is unsure whether to use a note or
feedback. It must state that the local/test workflow does not change source-
derived records or submit correction decisions, and it must not imply that a
correction workflow, correction status, correction persistence, correction
decision, export change, or official public-source fact has been implemented.
Reviewer note/status confirmations should make the return path clear: saved
notes/statuses are reviewer-created state, queue progress and note/status cues
are derived from that state, the tester may need to resubmit the same local/test
facility/date request context to refresh the queue display, and the next record
should be chosen from the refreshed queue.
Reviewer detail feedback handoff cues should be record-specific and brief. They
should tell testers what source traceability, source context, note/status
confirmation, same-queue return, queue refresh, unexpected-record, confusing
label, wording, keyboard-flow, or next-step observations to carry into the
existing manual checklist without adding a new feedback workflow.
Reviewer detail checklist bridge cues should connect source-confidence,
field-note, source-traceability, note/status confirmation, and return-to-queue
observations to that same existing manual checklist. They must not duplicate the
checklist, create a new feedback form, persist feedback, send feedback, or imply
export/audit workflow behavior.
Queue-to-detail checklist continuity cues should use the same manual checklist
for queue-level and detail-level observations. Queue filters, filtered-empty
states, no-match/load states, reviewer detail, note/status confirmation,
return-to-queue refresh, and next-record confusion should point to one checklist
without adding another checklist or workflow.
The `/feedback` route is now the first real tester feedback workflow. It should
use an accessible feedback type dropdown, multiline description field, clear
validation, safe unconfigured state, and safe success/failure messages. GitHub
Issues feedback classification should use labels rather than GitHub Projects or
issue types. Existing checklist cues should point testers toward what to include
in feedback without duplicating the feedback form.
Queue, reviewer detail, save confirmation, packet preview, and packet draft
pages should link to `/feedback` with only bounded safe context when testers need
to report confusing queue order, unexpected local/test records, source
traceability questions, note/status action confusion, packet readiness concerns,
copy/print preparation concerns, wording, keyboard flow, or accessibility issues.
Feedback context is a triage aid only; it must not include raw source narrative,
provider claims, tokens, cookies, private URLs, stack traces, server-local paths,
environment values, legal conclusions, source-completeness claims, or new
feedback persistence.
First-run review session orientation should make the end-to-end local/test CCLD
path visible from home, request/help, queue, and reviewer detail: facility lookup
or manual entry, request-context confirmation, loaded local/test queue, reviewer
detail source traceability, source-confidence cues, field-note guidance,
reviewer-created note/status observations, same-queue refresh, next-record
continuation, and manual feedback checklist copy. Orientation must not imply a
saved session, persisted queue state, duplicate checklist, feedback persistence,
auth, workflow engine, browser live fetch, connector execution, or artifact
building from browser requests.
Home and CCLD intake pages should make the start choice explicit: use facility
lookup when the tester knows a name/location/reference detail, use manual
facility/license number entry when they already have the digit identifier, then
set a complaint date range before loading or retrieving records. This start
handoff should point forward to queue, reviewer detail, packet preparation, and
feedback without implying saved sessions, source completeness, legal conclusions,
or new workflow state.
Reviewer detail and request-queue navigation should make next-record movement
clear without implying persisted assignment, record claiming, or production
workflow state. Suggested-next cues should remain derived from the current
facility/date request context and existing reviewer-created note/status rows.
Complaint review matrix CSV exports should be framed as local/test review aids
for spreadsheet comparison. They should include source-derived values and source-
traceability cues in clearly named columns, keep reviewer-created note/status
columns visually and semantically separate when included, and repeat that the CSV
is not a certified report, not source verification, not a complaint-coverage
determination, not a source-completeness proof, and not a legal finding. Matrix
links should appear only where a facility/date context can be carried safely.
Reviewer status filters should read as explicit queue views, not hidden state.
Queue pages should state the active reviewer-created status filter, records
shown under that filter, total records in the same facility/date queue, available
status values, and filtered-empty recovery action in plain visible text. Empty
filtered results should explain that the filter may be hiding records and that
the result is not public-source absence, source completeness, assignment, record
claiming, or persisted workflow state.

The first browser-accessible CCLD record request page is a local/test, server-
rendered HTML surface at `/ccld/records/request`. Its design purpose is to
return the MVP to the original user flow: enter a CCLD facility/license number,
optionally narrow by date range, see matching seeded CCLD records when they
already exist, load or refresh matching rows from local validated hosted seeded-
corpus output when needed, and continue into the hosted reviewer UI. Empty,
invalid, and load-result states should use plain language that distinguishes
missing local/test validated records from public-source completeness. The page
must not offer non-CCLD source selection, imply hosted live crawling, imply
generic connector execution, or hide the required outside-browser handoff when
broader retrieval requires an explicit live-fetch command and local/test
artifact build command before browser load/refresh.
No-match states should also explain that the browser searched currently loaded
local/test source-derived rows only, prompt testers to confirm facility/date
criteria before assuming records are missing, and point to the existing local
validated load or outside-browser preparation workflow without running those
steps from the browser.
The next guided version of that page can organize matching complaints as a
facility/date-scoped review queue, provide first-time workflow and key-term
help, show reviewer notes/status indicators from existing reviewer-created
state reads, and include a structured copyable feedback checklist without adding
feedback persistence.
That UI must keep source-derived records visibly separate from reviewer-created
notes/statuses and avoid implying production readiness or public-source
completeness. ADR-0016 now approves a future controlled browser-triggered,
server-executed CCLD retrieval job boundary; until that implementation exists,
current pages must not imply that live retrieval is available. When implemented,
job status UI must stay explicit, semantic, accessible, and non-conclusive,
showing safe state/count/warning messages rather than raw stack traces,
secrets, or public-source completeness claims.
The workflow-completion version can add progress counts and reviewer-status
filters derived from existing reviewer-created state so testers can distinguish
not-started, in-review, needs-follow-up, reviewed, and blocked records without
adding persisted queue state.
Queue usability should keep improving through presentation-only guidance when it
helps testers triage CCLD records: list-level triage summaries, note/status cues,
source-traceability availability cues, suggested next-record links, clear
filtered-empty states, and meaningful reviewer-detail actions are product
requirements when they reduce confusion without adding new persistence or
changing note/status behavior.
Queue summaries should not overstate confidence in displayed source-derived
values. When fields look missing, confusing, or proxy-related, the queue should
direct testers to reviewer detail source-confidence cues before they rely on the
values in reviewer-created notes/status or manual feedback. Queue summaries and
cards should also make the next safe action clear: check reviewer detail source
traceability, write cautious reviewer-created observations only when helpful,
use feedback if source-confidence wording remains confusing, and continue from
the same queue context.
Filtered-empty queue states should explain that records are hidden by the
selected reviewer-status filter for the same facility/date request context, not
necessarily missing from local/test data or public source material, and should
provide a clear way to show all records again.
First-run accessibility polish is also MVP usability work, not cosmetic polish:
skip-to-main links, clear start-here sections, visible next-step instructions,
specific button/link text, and manual feedback-copy guidance are required when
they help a tester complete the CCLD facility lookup, request, queue, detail,
notes/status, and feedback loop without prior explanation.
The CCLD facility lookup version can add a local/test reference-data search path
before the request page so testers do not need to know the full facility/license
number. It should support a configured full local/test CSV with a committed tiny
fixture fallback, show which reference source is active, support searching safe
available CSV fields, show bounded readable results, carry the selected
facility/license number into the request form, preserve manual entry, and clearly
state that lookup rows are local/test reference assistance rather than complaint
source truth or completeness proof.
When a selected facility has its own hub route, the hub should remain a
facility-directory context page rather than a new data source. It may show safe
directory fields, summarize already-loaded local/test complaint-review context,
and offer links or forms into existing request, reviewer queue, packet preview,
and packet draft routes. It must keep directory data separate from complaint
records and must not imply complaint coverage, source completeness, license
validity, legal conclusions, official findings, assignment, claiming,
correction application, export approval, certified report status, retrieval
submission, or source-derived/reviewer-created mutation.
Facility review signals on that hub may summarize supported uploaded public
summary fields when they help testers decide what to review next. They should
use cautious `review cue` wording, prefer concise scalar counts/dates/statuses,
and direct testers to complaint request, loaded records, reviewer queue, and
source traceability checks. They must not score facilities, verify sources,
confirm complaints, imply complaint absence, or treat licensing/visit/citation
summary rows as legal findings, complaint records, license validity, complaint
coverage, or source-completeness proof.
If a facility number has uploaded public summary signals but no current local
directory row, the hub may render as a signal-only facility hub. It should say
the facility-directory record is not available locally, show only safe summary
fields, preserve normal next actions, and avoid implying a directory problem,
verified source state, complaint coverage, source completeness, legal findings,
license validity, assignment, claiming, correction, or export readiness.
Facility review priority pages may group those same review cues across facilities
to help testers choose which facility hub to open next. Default ordering should
be transparent and cue-based rather than opaque scoring, with facilities that
have multiple cue types, complaint visit activity, citation indicators, POC
indicators, recent visit activity, high capacity, closed status, or long visit
gaps surfaced clearly. Rows should link to facility hubs and keep the same
not-legal-finding, not-source-verification, not-complaint-coverage, and not-
source-completeness boundaries visible.
Facility review intelligence dashboards may combine the same uploaded public
summary-field review cues with active local/test facility-directory context to
help reviewers decide where to spend time first. They should show why each
facility appears, support transparent filters and sorting over existing public
fields, and link to facility hubs, complaint requests, and reviewer queues. They
must not introduce risk scores, wrongdoing determinations, legal conclusions,
complaint coverage, source verification, source completeness, assignment,
claiming, correction, packet lifecycle, export readiness, or source-derived or
reviewer-created mutation.
The request and queue pages should also make the active request context visible:
whether it came from facility lookup or manual entry, which facility/license
number and date range are being used, which local/test facility reference source
is active, and how to change facility/date criteria before reviewing queue
results.
Request and queue friction cues should keep recovery links close to the current
state. When a request has a facility/license number, pages should link to the
facility hub or signal-only facility hub when active local/test inputs support
one, the facility review priority list, the same request/queue path, and the
complaint request flow. No-match and filtered-empty states should state that no
loaded local/test records matched the current request context or filter, explain
what to try next, and avoid implying complaint coverage, source completeness,
source verification, legal findings, assignment, claiming, correction, or export
approval.
CCLD local/test pages should use the same plain-language terms for repeated
concepts: facility/license number, CCLD request context, facility/date request,
loaded local/test CCLD records, source-derived records, source traceability,
reviewer-created notes/status, reviewer-status filter, suggested next record,
and manual feedback checklist.

Near-term hosted work should pass the deferred-readiness/product-benefit gate in
`GOVERNANCE_INVENTORY.md`. MVP usability is not cosmetic polish: user-friendly
layout, clear forms, contextual help, efficient facility lookup, understandable
results, accessible structure, and low-friction reviewer actions are product
requirements when they help local/test CCLD testers complete the workflow without
creating avoidable rework. Backend readiness, hardening, or checklist work should
be sequenced when it unlocks that workflow or removes a concrete MVP-blocking
risk.

The hosted scaffold and first local-only read-only source-derived views now
exist. Detailed hosted visual design may begin from that real shell, but early
design work must stay inside local-only, fixture/sample, read-only boundaries
until later implementation decisions approve database, import, authentication,
reviewer-state, deployment, or workflow behavior. The document-governance
dashboard concept may inspire later hosted reviewer UX patterns such as left
navigation, dashboard/status cards, review queues, source-traceability health
panels, contextual onboarding/help, light and dark mode support, and audit/
change-history patterns, but it must not be copied literally. Any adapted
design must preserve this project's source-traceability, accessibility,
cautious-language, tester feedback, and reviewer-state boundaries.

## Design principles

- Prefer review workflows over raw implementation exposure.
- Hosted CCLD pages should present as an attorney-focused public-record review
  workspace: serious, calm, source-traceability focused, and organized around
  selecting a facility, retrieving complaint records, reviewing key dates and
  findings, identifying cautious review flags, opening records for legal review,
  and preserving source-derived versus reviewer-created separation.
- Review flag wording must stay cautious. Use terms such as `Review flag`,
  `Needs source check`, `Possible delay indicator`, `Missing in local record`,
  and `Source traceability available`. Do not use UI language that implies
  legal conclusions, official findings, source completeness, facility-wide
  conclusions, verified harm, abuse, neglect, liability, or rights-deprivation.
- Product-ready hosted CCLD design should avoid a stacked-card scaffold look.
  Ordinary page sections should be structural, not automatically boxed. Use
  explicit framing only for intentional product components such as the launch
  hero, facility selector, retrieval confirmation, recovery panel, metric cards,
  worklist cards, and collapsed technical details. Technical counts, machine-
  readable states, feedback checklists, local/operator actions, and full field
  tables should be visually secondary or collapsed unless they are the current
  primary user task.
- Hosted CCLD pages should follow the So What rule: every visible object should
  directly help the legal user answer the page's primary question, make a review
  decision, or take the next action. If an item is secondary, technical,
  repetitive, or mainly diagnostic, remove it from the primary view, collapse it
  in a clearly labeled details block, or move it to Help. Do not let boundary
  reminders, machine-readable state, feedback checklists, local/operator
  commands, or explanatory panels compete with the page's main legal-review
  decision.
- Facility-centered case briefs should answer what to review about the facility
  and why before presenting the full worklist. They may summarize only existing
  safe source-derived values and reviewer-created note/status cues: facility
  scope, complaint record counts, source traceability availability, cautious
  review-flag counts, findings represented, reviewer-created notes/statuses, and
  one suggested first record with explainable source-derived reasons. They must
  not present an automated legal score, legal conclusion, facility-wide
  conclusion, source-completeness claim, or proof that no complaint exists.
- Reviewer detail action panels should turn the opened priority record into a
  guided review loop: understand the complaint and review flags, check source
  traceability, save existing reviewer-created status and/or note state, confirm
  that source-derived fields remain unchanged, then return to the facility queue
  or open the next priority record. The panel must remain presentation-only over
  existing note/status actions and audit paths; it must not create assignments,
  legal decisions, workflow-engine state, new reviewer-created state kinds,
  source edits, exports, annotations, corrections, auth, or schema changes.
- Local/test review packet previews may summarize what would be prepared for
  attorney handoff from the current facility/date context: included complaint
  records, why each record is included, reviewer-created status/note cues,
  review flags, findings, and source traceability readiness. They must remain
  read-only preparation views and must not generate final exports, downloadable
  legal packets, packet persistence, delivery, legal conclusions, source-
  completeness claims, schema changes, or new workflow/persistence domains.
- Print-ready packet drafts may provide a cleaner browser-print and copy-ready
  presentation of the same local/test packet context. They should hide app
  navigation and technical chrome in print, keep packet title, scope,
  limitations, summaries, included records, and copyable text visible, and make
  the no-context state explicit. They must not create server-side export files,
  packet lifecycle state, finalization, delivery, persistence, legal reports, or
  production export behavior.
- Packet preview and packet draft copy/print preparation guidance should be a
  visible tester convention, not an icon-only or hidden convention. Before a
  tester uses browser copy or print, the UI should state that packet readiness
  means local/test review readiness only and identify the active facility/date
  context, included local/test records, records needing source check, records
  needing reviewer-created status/note attention, what source traceability
  available means for checking important source-derived values, possible
  correction-readiness concerns, how to send feedback for confusing or risky
  packet/export-readiness content, and that the page is not a legal report,
  final export, certified report, product-generated export, packet lifecycle
  state, or source-completeness proof.
- Use the restrained legal-review visual system: page background `#F5F7FA`,
  white surfaces, tinted support panels near `#EEF7F6`, primary text near
  `#17212B`, muted slate text, deep teal primary actions, accessible blue focus,
  soft borders, and sparing amber/red/green status colors with text labels.
- Make the first useful screen obvious after a script completes.
- Preserve the public portal as the source of record.
- Keep every derived record connected to source URL, raw hash, connector details,
  and retrieval time.
- Treat Datasette as a retained validation and inspection layer while
  production-discovery defines the future primary review experience.
- Favor stable, documented local workflows over account-specific services or
  optional paid platform features.
- Treat extracted records as review aids, not authoritative conclusions.

## Reviewer action and workflow rules

- Top navigation may remain visually styled as navigation tabs or buttons.
- In-page action groups must be consistent and must not mix buttons and links in
  the same visual action group.
- Do not use ordered lists for buttons, form controls, dropdowns, or other
  non-text interactive elements.
- Use primary buttons for the main action and secondary buttons for alternate
  actions in the same workflow.
- Put rare, bulk, export, diagnostic, or alternate-path actions into a
  consistent "More actions" pattern.
- Avoid unnecessary confirmation or review steps after a user has already made a
  clear non-destructive selection.
- Treat too many clicks, repeated inputs, excessive scrolling, dead-end pages,
  and duplicate summaries as global UX problems to identify and fix across the
  app.

## Facility and record request workflow rules

- When a user selects a facility from typeahead, the app should immediately
  resolve or search that facility.
- After facility selection, date range pickers should appear immediately.
- Facility ID and selected date range should persist across related workflow
  pages.
- Request Records should move toward one intelligent action: use already-loaded
  records when present, retrieve missing records for the selected facility/date
  range when needed, then show the ready queue.
- Users should not need to choose between "view existing queue" and "request
  records" when the app can decide safely.

## Reviewer language and source-detail rules

- Review all reviewer-facing terminology for clarity and consistency.
- Avoid technical reviewer-facing labels such as `source-derived rows`,
  `intelligence views`, `source cues`, `operator/runtime`, `retrieval metadata`,
  and `source traceability mechanics`.
- Prefer user-centered labels such as `Complaint records`, `Records ready`,
  `Review flags`, `Needs attention`, `Packet preparation`, and `Report an
  issue`.
- Safety warnings must exist where needed, but they must not dominate attorney-
  facing pages. Provide concise guardrails without overwhelming the workflow.
- Source reliability is built into the controlled import model. Default reviewer
  pages should not require attorneys to interpret source traceability mechanics.
- A simple user-facing indication that the record came from CCLD is enough in
  most reviewer contexts.
- Deeper source fields, hashes, raw artifact references, connector metadata, and
  import details belong in operator or developer surfaces unless a user-facing
  problem requires attention.

## Approved page direction

- Home should become a compelling product start page, not documentation. It
  should capture the user and make the primary paths obvious.
- Facility lookup should focus on finding and selecting the correct facility.
- Facility results should show "Open Facility Hub" only when imported records or
  useful review context exist; otherwise emphasize requesting complaint records.
- Facility Hub should become an attorney case-review summary.
- Review Queue should have one primary record view and should not duplicate the
  same records as equally prominent cards and tables.
- Reviewer detail should focus on complaint review, not source/import
  inspection.
- Packet preview and draft should be packet-focused, context-aware, and
  print-ready.
- Print actions should invoke a printable version and browser print dialog, not
  merely navigate to another page that still requires a separate print action.
- Job Status likely should leave the main reviewer navigation. Keep job progress
  inline where needed and preserve Job Status as an operator/support diagnostics
  surface.
- Help should become a user-focused help-center-style page with search, clear
  categories, and common task articles. It should not include operator setup
  topics.
- Feedback should be standardized across pages and integrated with GitHub safely.

## Feedback and help direction

- Use one GitHub feedback flow for bugs, feature requests, confusing workflow or
  page reports, packet/export issues, source/data concerns, and new data source
  requests.
- Each page should have an unobtrusive report or feedback action.
- Feedback may safely capture page context when available: route, page title,
  facility/license number, date range, complaint/control number, job ID, visible
  workflow state, and user action attempted.
- Feedback safety guidance should be concise and must not dominate pages.
- Help should use search or category-style organization, avoid a numbered topic
  list that repeats collapsible sections below, and keep topics user-focused:
  Find a facility, Request complaint records, Review complaint records, Prepare
  a packet, Print or export, Report an issue, and Understand review flags.
- Operator setup topics belong in operator docs or diagnostics, not reviewer
  Help.

## Batch loading direction

The command-based batch complaint loader may load by facility type and date
range for operator/data-loading use. It must use the same controlled
retrieval/import path as browser retrieval and support dry-run/apply, manifests,
resume, rate limiting, 366-day window handling, and skip/already-loaded
behavior. It is not a reviewer-facing redesign.

## RecordsTracker UI/product improvement approval inventory

This inventory is the user-review gate before any reviewer-facing UI
implementation branch. It captures approved product direction for RecordsTracker
as an attorney public-record review workspace, not a prettier copy of the public
CCLD site. The current app must move attorneys toward finding a facility,
choosing dates, loading or retrieving records, reviewing complaint records,
preparing packet context, printing or exporting, and sending feedback.

Future implementation details are not approved by this inventory. Each later
implementation branch must name the item numbers it implements, stay within the
implementation boundary for those items, and avoid unrelated route, template,
style, retrieval, database, batch-loader, deployment, or QNAP runtime changes.
The user must approve the numbered item or item group before implementation
begins.

Operator and support diagnostics must be preserved even when they leave the
primary attorney-facing navigation. Job state, import counts, safe runtime
warnings, setup guidance, source traceability, raw-artifact-preserved signals,
and other support details belong in operator/support or developer surfaces when
they do not help the attorney complete review. They must not expose secrets,
tokens, private URLs, server-local paths, stack traces, raw artifact contents,
or unnecessary narrative source text.

### Home/start page

1. **UI-01 - Make Home the review start.** Current problem: Home still reads
   too much like orientation documentation and competes with secondary links.
   Proposed change: lead with the primary RecordsTracker path: find a facility,
   choose dates, get complaint records, review records, prepare packet context,
   and report an issue. User benefit: first-time attorneys see where to start
   without reading setup context. Implementation boundary: presentation,
   navigation labels, and safe links only; no new workflow state, auth,
   retrieval behavior, or persistence. Audience: attorney-facing. Figma
   AI/design exploration: yes, for first-screen hierarchy and navigation.
2. **UI-02 - Remove runtime mechanics from primary Home navigation.** Current
   problem: attorney-facing navigation can make Job Status and runtime concepts
   feel like normal review steps. Proposed change: remove operator/runtime
   surfaces from the main attorney path while keeping a support/diagnostics
   entry available outside the primary review flow. User benefit: attorneys stay
   focused on review tasks, while operators can still troubleshoot. Implementation
   boundary: navigation placement only; do not remove existing diagnostics,
   routes, safe job history, or support metadata. Audience: both. Figma
   AI/design exploration: no.
3. **UI-03 - Shorten Home safety guidance.** Current problem: repeated caution
   text can dominate the start page before a user takes action. Proposed change:
   keep a concise public-record and non-legal-conclusion reminder near the start
   path, with deeper limitations linked from Help. User benefit: safety remains
   visible without burying the workflow. Implementation boundary: copy and link
   organization only; do not weaken source, limitation, or accessibility
   boundaries. Audience: attorney-facing. Figma AI/design exploration: no.

### Facility lookup

4. **UI-04 - Resolve selected typeahead facilities immediately.** Current
   problem: selecting a facility can still leave the user needing another search
   or confirmation step. Proposed change: when a user chooses a facility from
   typeahead, immediately resolve/search that facility and carry the selected
   facility/license number forward. User benefit: fewer clicks and less doubt
   about whether the selected facility is active. Implementation boundary:
   browser/form flow over existing lookup data only; no new facility import,
   external query, source-derived mutation, or retrieval behavior. Audience:
   attorney-facing. Figma AI/design exploration: no.
5. **UI-05 - Show date pickers right after facility selection.** Current
   problem: date narrowing is not always presented as the next visible step.
   Proposed change: reveal start/end date controls immediately after a facility
   is selected or resolved. User benefit: attorneys can define the review scope
   before requesting or loading records. Implementation boundary: presentation
   and form flow only; do not add saved sessions, date inference, or retrieval
   expansion. Audience: attorney-facing. Figma AI/design exploration: no.
6. **UI-06 - Make facility results action-specific.** Current problem: results
   can repeat details and present "Open Facility Hub" even when there is little
   review context. Proposed change: show "Open Facility Hub" only when imported
   records or useful review context exist; otherwise emphasize requesting
   complaint records for that facility/date scope. User benefit: users choose
   the next useful action instead of landing on a sparse hub. Implementation
   boundary: result presentation and action labels only; do not change lookup
   matching, source data, import behavior, or facility reference schemas.
   Audience: attorney-facing. Figma AI/design exploration: no.

### Facility review hub

7. **UI-07 - Turn Facility Hub into an attorney case-review summary.** Current
   problem: the hub can feel like a collection of data panels instead of a legal
   review starting point. Proposed change: summarize facility identity, selected
   date scope, loaded complaint counts, review flags, source-traceability
   availability, reviewer-created status/note cues, and the next useful review
   action. User benefit: attorneys can understand what is ready to review before
   opening the queue. Implementation boundary: summarize existing safe
   source-derived and reviewer-created read data only; no scoring, legal
   conclusion, source-completeness claim, new query domain, or persistence.
   Audience: attorney-facing. Figma AI/design exploration: yes, for case-review
   summary layout.
8. **UI-08 - Make "Review next" focused and default-visible.** Current problem:
   priority guidance can be diluted by long panels or repeated lists. Proposed
   change: show one compact "Review next" area with the suggested complaint
   record and cautious source-derived/reviewer-created reasons. User benefit:
   attorneys can continue review without hunting for the next record.
   Implementation boundary: use existing ordering/cues only; do not add
   assignment, record claiming, workflow-engine state, or legal priority scores.
   Audience: attorney-facing. Figma AI/design exploration: yes, for compact
   priority layout.
9. **UI-09 - Preserve hub diagnostics outside the primary view.** Current
   problem: import, raw-source, and operator context can crowd the attorney hub.
   Proposed change: move deeper mechanics into collapsed support details or a
   support/diagnostics surface, while leaving a simple CCLD/source-traceability
   indication in the attorney view. User benefit: attorneys see review context
   first, and support staff retain diagnostic visibility. Implementation
   boundary: organization only; do not remove source traceability, raw-artifact
   preservation indicators, auditability, or safe operator metadata. Audience:
   both. Figma AI/design exploration: no.

### Request Records workflow

10. **UI-10 - Replace split queue/request choices with one intelligent action.**
    Current problem: users must decide between "View existing queue" and
    "Request records" even when the app can safely use loaded records and
    retrieve missing records. Proposed change: provide one primary action for
    the selected facility/date range that uses already-loaded records when
    present, retrieves missing complaint records when permitted, and then shows
    the ready queue. User benefit: fewer decisions and clearer forward motion.
    Implementation boundary: orchestrate existing controlled CCLD request and
    queue paths only; do not broaden retrieval scope, add statewide crawling,
    change batch-loader behavior, or alter import semantics. Audience:
    attorney-facing. Figma AI/design exploration: no.
11. **UI-11 - Compact request-context confirmation.** Current problem:
    repeated confirmations and duplicated copy slow down non-destructive review
    actions. Proposed change: show the selected facility/license number, date
    range, record type, and change links once, near the primary action. User
    benefit: attorneys can verify scope without being forced through redundant
    steps. Implementation boundary: copy and layout only; do not remove
    validation messages, rate-limit messages, or source-completeness cautions.
    Audience: attorney-facing. Figma AI/design exploration: no.
12. **UI-12 - Keep retrieval progress inline only when it helps review.**
    Current problem: Job Status can appear as a separate review destination.
    Proposed change: show concise queued/running/completed/failed progress and
    ready-queue links inside the Request Records flow, with full job history in
    support diagnostics. User benefit: attorneys know when records are ready
    without entering operator pages. Implementation boundary: safe status/count
    display only; do not expose stack traces, raw artifact paths, raw source
    contents, credentials, or private host details. Audience: both. Figma
    AI/design exploration: no.
13. **UI-13 - Keep batch complaint loading operator-facing.** Current problem:
    batch loading can be confused with an attorney request workflow. Proposed
    change: keep batch complaint loading in operator/data-loading documentation
    and diagnostics, not in the attorney review path. User benefit: attorneys
    avoid bulk-loader concepts, while operators keep the controlled dry-run/apply
    path. Implementation boundary: navigation/documentation placement only; do
    not change batch CLI behavior, manifests, resume, rate limiting, retrieval,
    import, or QNAP runtime state. Audience: operator-facing. Figma
    AI/design exploration: no.

### Review queue

14. **UI-14 - Use one primary queue record presentation.** Current problem:
    queue pages can duplicate the same records as equally prominent cards and
    tables. Proposed change: choose one primary scannable record presentation
    with secondary details available on demand. User benefit: attorneys scan,
    compare, and open records with less vertical waste. Implementation boundary:
    presentation only over existing queue data; do not change filtering,
    ordering semantics, reviewer-created state, retrieval, or export behavior.
    Audience: attorney-facing. Figma AI/design exploration: yes, for the queue
    density and record-row pattern.
15. **UI-15 - Replace source mechanics with review cues.** Current problem:
    raw source/import labels can make the queue feel like a data dump. Proposed
    change: show complaint dates, finding/status, review flags, note/status
    cues, source-traceability availability, and why a record may need attention
    in user-centered terms. User benefit: attorneys can decide what to open
    next without interpreting implementation fields. Implementation boundary:
    label and summary changes using existing fields only; do not create
    confidence scores, legal classifications, or new canonical fields. Audience:
    attorney-facing. Figma AI/design exploration: yes, for cue hierarchy.
16. **UI-16 - Make status filters explicit queue views.** Current problem:
    filtered-empty states can look like missing public records. Proposed change:
    always state the active reviewer-created status filter, records shown under
    it, total records in the same facility/date queue, available status values,
    and the clear-filter action. User benefit: attorneys understand that a
    filter hid records, not that records are absent. Implementation boundary:
    copy and status-filter presentation only; do not add persisted queue state,
    assignments, claiming, or source-completeness assertions. Audience:
    attorney-facing. Figma AI/design exploration: no.
17. **UI-17 - Standardize queue feedback entry.** Current problem: queue-level
    feedback guidance can be bulky or inconsistent with detail pages. Proposed
    change: provide a small "Report an issue" action that routes to the shared
    GitHub-backed feedback flow with safe queue context. User benefit: testers
    can report confusing queue order, filters, labels, or missing context from
    the page where they noticed it. Implementation boundary: safe context
    handoff only; do not add duplicate feedback forms, feedback persistence, raw
    narrative source text, private URLs, or secrets. Audience: both. Figma
    AI/design exploration: no.

### Reviewer detail page

18. **UI-18 - Lead detail with complaint review, not raw source inspection.**
    Current problem: the reviewer detail page still looks too much like a
    raw-source/data dump. Proposed change: start with complaint identity,
    facility/date context, finding/status, key dates, allegations/categories
    when safe, review flags, and the attorney's next action. User benefit:
    attorneys can understand the record before opening technical detail.
    Implementation boundary: presentation and ordering only over existing safe
    fields; do not change extraction, source-derived values, note/status
    behavior, or legal meaning. Audience: attorney-facing. Figma AI/design
    exploration: yes, for detail-page information architecture.
19. **UI-19 - Summarize source traceability, preserve full diagnostics.**
    Current problem: attorneys need confidence that source traceability exists
    but should not have to parse hashes, connector fields, and import mechanics
    by default. Proposed change: show a simple source indication and source-check
    reminder in the main detail view; keep full traceability fields, hashes,
    raw-artifact-preserved indicators, connector/capture details, and import
    context in a collapsed support area or operator/developer surface. User
    benefit: source traceability remains available without overwhelming the
    review. Implementation boundary: organization only; do not remove
    traceability, raw-source preservation, audit context, or safe source metadata.
    Audience: both. Figma AI/design exploration: no.
20. **UI-20 - Make note/status actions a guided review loop.** Current problem:
    reviewer-created state controls can feel separate from the complaint review
    task. Proposed change: group current status, notes, cautious field-note
    guidance, save actions, confirmation, return-to-queue, and next-record
    links as one action panel. User benefit: attorneys can review, save an
    observation, and continue. Implementation boundary: use existing note/status
    actions and audit path only; do not add new state kinds, annotations,
    corrections, assignments, claiming, or workflow-engine behavior. Audience:
    attorney-facing. Figma AI/design exploration: yes, for action-panel layout.
21. **UI-21 - Reduce repeated detail confirmations and safety copy.** Current
    problem: repeated confirmations and warnings consume vertical space after a
    user has made a safe action. Proposed change: consolidate saved-state
    confirmation, queue refresh guidance, and limitations into concise messages
    near the relevant action. User benefit: users see what happened and where to
    go next without rereading the same cautions. Implementation boundary: copy
    and message placement only; do not weaken validation, audit, source, or
    public-record limitations. Audience: attorney-facing. Figma AI/design
    exploration: no.
22. **UI-22 - Keep detail navigation task-based.** Current problem: mixed
    links/buttons and repeated paths make it hard to continue from detail.
    Proposed change: provide consistent actions for back to queue, next record,
    packet preview/draft, feedback, and Help, with diagnostics in "More
    actions" or support areas. User benefit: attorneys can move through the
    review loop without guessing which controls are primary. Implementation
    boundary: navigation and labels only; do not create new routes unless a
    later approved implementation branch requires them. Audience:
    attorney-facing. Figma AI/design exploration: no.

### Packet draft

23. **UI-23 - Make packet draft copy/print-ready.** Current problem: packet
    draft content can still feel like an app page instead of an attorney handoff
    draft. Proposed change: present title, facility/date scope, limitations,
    included records, review reasons, reviewer-created cues, source-traceability
    readiness, and copy-ready text in a print-focused layout. User benefit:
    attorneys can prepare a review handoff with fewer cleanup steps.
    Implementation boundary: browser presentation and print styling only; do
    not create server-side export files, packet lifecycle state, final reports,
    delivery, persistence, or legal conclusions. Audience: attorney-facing.
    Figma AI/design exploration: yes, for print/copy layout.
24. **UI-24 - Hide app chrome in printable draft output.** Current problem:
    navigation and technical chrome can appear in printed packet drafts.
    Proposed change: keep necessary packet context visible and suppress
    non-packet navigation in print styles. User benefit: printed drafts are
    cleaner and easier to share internally for review. Implementation boundary:
    print presentation only; do not change export generation, download behavior,
    route authorization, or packet contents. Audience: attorney-facing. Figma
    AI/design exploration: no.
25. **UI-25 - Make no-context packet draft states explicit.** Current problem:
    packet pages without facility/date context can feel broken or empty.
    Proposed change: state that packet draft needs a selected facility/date
    context and link back to facility lookup or Request Records. User benefit:
    users can recover without guessing. Implementation boundary: empty-state
    copy and navigation only; do not create saved packet state or infer context.
    Audience: attorney-facing. Figma AI/design exploration: no.

### Packet preview/export

26. **UI-26 - Focus packet preview on readiness.** Current problem: preview can
    mix packet preparation, source checks, and app mechanics. Proposed change:
    show active facility/date context, included record counts, records needing
    source check, reviewer-created note/status attention, possible correction
    concerns, and packet/export issue feedback. User benefit: attorneys can
    decide whether the current packet context is ready for copy/print review.
    Implementation boundary: read-only summaries from existing data only; do not
    generate final exports, add packet persistence, edit source-derived records,
    or create legal reports. Audience: attorney-facing. Figma AI/design
    exploration: yes, for readiness checklist hierarchy.
27. **UI-27 - Separate preview, printable draft, and unavailable final export.**
    Current problem: packet actions can blur whether the app is previewing,
    printing, downloading, or finalizing. Proposed change: label actions
    precisely and state when browser print/copy is the current path. User
    benefit: users know what each packet action does before clicking.
    Implementation boundary: labels, help text, and action grouping only; do not
    add final export generation, file storage, delivery, or lifecycle state.
    Audience: attorney-facing. Figma AI/design exploration: no.
28. **UI-28 - Route packet concerns into shared feedback.** Current problem:
    packet/export concerns can lack a standard reporting path. Proposed change:
    add a small feedback action for packet readiness, print/copy, confusing
    included records, or source-check concerns. User benefit: packet issues are
    reported through the same GitHub-backed flow as other product feedback.
    Implementation boundary: safe context handoff only; do not include raw
    narrative text, private details, or generated packet content in feedback
    context. Audience: both. Figma AI/design exploration: no.

### Feedback

29. **UI-29 - Standardize one unobtrusive feedback action.** Current problem:
    feedback prompts vary across pages and can interrupt review. Proposed
    change: use one small "Report an issue" or equivalent action across Home,
    lookup, request, queue, detail, packet, and Help. User benefit: users can
    report problems without leaving the review path mentally. Implementation
    boundary: links/forms to existing `/feedback` flow only; do not add a
    second feedback workflow or new persistence. Audience: both. Figma
    AI/design exploration: no.
30. **UI-30 - Keep feedback context safe and allowlisted.** Current problem:
    page context is useful but can become risky if broad query strings or source
    details are included. Proposed change: carry only safe fields such as route,
    page title, facility/license number, date range, complaint/control number,
    job ID, visible workflow state, and action attempted. User benefit: support
    receives useful reports without exposing private or sensitive material.
    Implementation boundary: safe context handling only; never include tokens,
    cookies, provider claims, private URLs, server paths, stack traces, raw
    narrative source text, or secrets. Audience: both. Figma AI/design
    exploration: no.
31. **UI-31 - Normalize feedback states.** Current problem: unconfigured,
    validation, success, and failure feedback states can feel different from
    page to page. Proposed change: use consistent accessible labels, validation,
    copyable fallback summary, safe success/failure messages, and return links.
    User benefit: testers can complete or recover from feedback submission
    reliably. Implementation boundary: presentation over existing GitHub-backed
    feedback flow only; do not add GitHub Projects, issue types, local feedback
    persistence, or token exposure. Audience: both. Figma AI/design exploration:
    no.

### Help

32. **UI-32 - Rebuild Help as a user-focused help center.** Current problem:
    Help can read like a numbered topic list or setup guide instead of task
    support. Proposed change: provide search or category-style organization for
    finding a facility, requesting complaint records, reviewing complaint
    records, preparing a packet, printing/exporting, reporting an issue, and
    understanding review flags. User benefit: attorneys find task help without
    scanning operator setup content. Implementation boundary: Help content and
    layout only; do not add new support workflows, search infrastructure, or
    source behavior unless separately approved. Audience: attorney-facing.
    Figma AI/design exploration: yes, for help-center organization.
33. **UI-33 - Move operator setup topics out of reviewer Help.** Current
    problem: operator setup and diagnostics can make Help feel technical.
    Proposed change: keep operator setup, environment, import, batch loading,
    and diagnostics topics in operator docs or support diagnostics. User
    benefit: attorney Help stays focused on review tasks while operators keep
    their references. Implementation boundary: information architecture only; do
    not remove operator guidance from the repository or support surfaces.
    Audience: both. Figma AI/design exploration: no.
34. **UI-34 - Keep safety and source explanations concise in Help.** Current
    problem: safety warnings can either dominate pages or disappear into dense
    text. Proposed change: provide short articles explaining public-source
    limits, review flags, source traceability, missing values, packet readiness,
    and feedback reporting in user language. User benefit: users can learn the
    boundaries when they need them. Implementation boundary: content only; do
    not weaken source traceability, public-record limitations, or legal
    conclusion restrictions. Audience: attorney-facing. Figma AI/design
    exploration: no.

### Job Status/operator diagnostics

35. **UI-35 - Move Job Status out of primary attorney navigation.** Current
    problem: Job Status appears like a normal attorney review destination.
    Proposed change: remove it from the primary attorney nav while preserving a
    support/operator diagnostics route and contextual links from Request Records
    when a job is relevant. User benefit: attorneys see the review workflow, and
    operators keep troubleshooting access. Implementation boundary: navigation
    placement only; do not remove job history/detail pages, safe status data, or
    retrieval auditability. Audience: both, with operator-facing diagnostics.
    Figma AI/design exploration: no.
36. **UI-36 - Keep diagnostics safe and support-oriented.** Current problem:
    diagnostic pages can expose too much implementation detail if treated as
    general user pages. Proposed change: show safe request context, job state,
    timestamps, counts, raw-artifact-preserved indicators, warning/error
    summaries, setup guidance, and queue links when records exist. User benefit:
    operators can support the pilot build without exposing sensitive internals.
    Implementation boundary: diagnostic presentation only; do not expose
    secrets, private URLs, server paths, stack traces, raw source contents,
    provider claims, or unnecessary narrative text. Audience: operator-facing.
    Figma AI/design exploration: no.
37. **UI-37 - Keep job progress visible at the point of need.** Current
    problem: moving Job Status out of primary nav could hide useful request
    progress. Proposed change: keep concise job progress and recovery links
    inline on Request Records and related pages when a job affects the current
    facility/date context. User benefit: attorneys do not lose visibility into
    whether records are ready. Implementation boundary: contextual status
    display only; do not add polling requirements, new scheduler behavior,
    broader audit UI, or retrieval changes. Audience: both. Figma AI/design
    exploration: no.

### Cross-page navigation, persistence, and action consistency

38. **UI-38 - Persist facility/date context across related pages.** Current
    problem: users may need to re-enter or reconstruct facility/date context
    across lookup, request, queue, detail, packet, feedback, and Help. Proposed
    change: carry facility/license number, selected date range, record type, and
    safe page context through URLs, forms, or existing route context where
    appropriate. User benefit: users stay in one review session flow.
    Implementation boundary: safe context propagation only; do not add saved
    sessions, cookies, production auth behavior, durable queue state, or hidden
    source keys. Audience: attorney-facing. Figma AI/design exploration: no.
39. **UI-39 - Standardize links, buttons, and action hierarchy.** Current
    problem: mixed links/buttons, ordered-list buttons, duplicate action groups,
    and inconsistent labels add friction. Proposed change: use primary buttons
    for the main action, secondary buttons for alternate actions, descriptive
    links for navigation, and avoid ordered lists for interactive controls. User
    benefit: actions become predictable and keyboard flow becomes clearer.
    Implementation boundary: markup, labels, and styling only; do not change
    route behavior, permissions, or data operations. Audience: both. Figma
    AI/design exploration: no.
40. **UI-40 - Use "More actions" for secondary work.** Current problem: rare,
    export, diagnostic, support, and alternate-path actions compete with the
    main review task. Proposed change: place secondary actions in a consistent
    "More actions" pattern or support area. User benefit: common actions stay
    visible and secondary actions remain discoverable. Implementation boundary:
    action grouping only; do not remove export support, diagnostics, source
    traceability, or feedback paths. Audience: both. Figma AI/design exploration:
    yes, for shared action-group patterns.
41. **UI-41 - Make cross-page wording consistent.** Current problem: repeated
    concepts use different labels across pages, such as source-derived rows,
    source cues, runtime, intelligence views, or feedback checklist. Proposed
    change: use consistent user-centered labels such as Complaint records,
    Records ready, Review flags, Needs attention, Packet preparation, Job
    diagnostics, and Report an issue. User benefit: screen reader users,
    first-time testers, and attorneys do not have to infer that different terms
    mean the same workflow concept. Implementation boundary: terminology only;
    do not rename canonical fields, schemas, database columns, or source
    contracts. Audience: both. Figma AI/design exploration: no.

### Recommended implementation sequence

1. **Approval checkpoint:** the user reviews and approves item numbers or a
   smaller item group. No UI implementation begins before this checkpoint.
2. **PR 1 - Navigation, diagnostics placement, and global action language:**
   UI-02, UI-03, UI-29, UI-30, UI-31, UI-35, UI-36, UI-37, UI-39, UI-41.
   This separates attorney navigation from operator diagnostics while
   preserving support access and safe feedback.
3. **PR 2 - Start, lookup, request, and carried context:** UI-01, UI-04, UI-05,
   UI-06, UI-10, UI-11, UI-12, UI-13, UI-38. This creates the smoother
   facility/date/request path before deeper page redesign.
4. **PR 3 - Facility hub and review queue:** UI-07, UI-08, UI-09, UI-14,
   UI-15, UI-16, UI-17, UI-40. This makes loaded complaint review scannable
   before changing detail pages.
5. **PR 4 - Reviewer detail review loop:** UI-18, UI-19, UI-20, UI-21, UI-22.
   This moves detail from raw-source inspection toward complaint review while
   preserving source traceability and existing note/status behavior.
6. **PR 5 - Packet preview, packet draft, and print/copy readiness:** UI-23,
   UI-24, UI-25, UI-26, UI-27, UI-28. This keeps packet work read-only and
   separates preview, print/copy, and final export language.
7. **PR 6 - Help center refinement:** UI-32, UI-33, UI-34. This can happen
   earlier if testers are blocked by Help confusion, but it should not absorb
   operator setup topics into attorney Help.

Items that need Figma AI or similar design exploration before implementation:
UI-01, UI-07, UI-08, UI-14, UI-15, UI-18, UI-20, UI-23, UI-26, UI-32, and
UI-40.

### Stop conditions for implementation branches

- Stop if the user has not approved the specific inventory item numbers for the
  branch.
- Stop if a Figma AI/design-exploration item is selected and the implementation
  branch lacks an approved design direction or explicit user decision to skip
  that exploration.
- Stop if the branch needs schema, migration, database, retrieval, batch-loader,
  QNAP runtime, deployment, production auth, or connector changes not already
  approved for that item group.
- Stop if a change would remove source traceability, raw-source preservation
  indicators, auditability, safe job diagnostics, or operator/support access
  instead of moving them to the correct surface.
- Stop if attorney-facing pages would expose secrets, private URLs, server-local
  paths, raw stack traces, raw artifact contents, provider claims, credentials,
  or unnecessary narrative source text.
- Stop if an item needs new canonical fields, legal classifications,
  confidence scores, source-completeness claims, assignments, record claiming,
  workflow-engine state, packet lifecycle state, or final export behavior.
- Stop and split the branch if implementation crosses unrelated page groups or
  cannot be validated with focused UI/accessibility tests plus the required
  repository checks.

## Usability principles

- Put the most common review fields together in human-readable views.
- Use plain labels in retained Datasette metadata where table or column names are
  terse.
- Preserve useful saved queries for validation, inspection, local exploration,
  and export support.
- Prioritize future reviewer state, queues, annotations, corrections,
  contextual help, and fewer-click paths over additional Datasette-primary UX.
- Keep scripts explicit about what to open next.
- Make empty, missing, or unknown values understandable in documentation and
  exports.
- Avoid requiring users to join tables manually for routine review tasks.
- Keep review terminology consistent across views, saved queries, exports, and
  documentation.

## Visual design principles

- Use visual organization to support scanning, comparison, and repeated review.
- Keep review pages quiet, dense, and readable rather than promotional or
  decorative.
- Prefer clear column order, labels, descriptions, and saved-query names over
  visual novelty.
- Do not add a frontend framework during production-discovery only to improve
  appearance or bypass architecture decisions.
- Do not add decorative graphics, branding treatments, or custom styling that
  distracts from source review and traceability.
- If future presentation styling is added, it must preserve keyboard access,
  visible focus indicators, contrast, semantic structure, and readable exports.

## Accessibility requirements

All user-facing review output must follow `ACCESSIBILITY_REQUIREMENTS.md`.

At minimum:

- Use semantic headings in documentation.
- Use descriptive link text.
- Keep Datasette table columns clearly named and documented.
- Preserve keyboard-operable workflows.
- Preserve visible focus indicators in any presentation layer.
- Do not use color alone to communicate findings, warnings, flags, or status.
- Use clear CSV headers in exports.
- Define field meanings and limitations in user documentation.
- Document known accessibility blockers in `KNOWN_LIMITATIONS.md` before any
  stable release.

## Terminology and plain-language rules

- Use "review flag" or "flagged for review" for screening indicators.
- Use "derived dataset" for extracted local data.
- Use "public portal" or "public source" for the source of record.
- Use "unknown" in user-facing explanations when a value is unavailable.
- Avoid unexplained acronyms in end-user documentation.
- Define technical terms such as raw hash, connector, extraction audit, and source
  traceability before expecting non-technical reviewers to use them.
- Do not describe missing dates as proof that an event did not happen.
- Do not describe a delay flag as proof that an investigation was delayed.

## Retained Datasette table and view usability expectations

Datasette review views retained for validation, inspection, debugging, local
exploration, and export support should:

- Put high-value review fields near the beginning of the view.
- Include facility number and facility name when reviewing complaint records.
- Include complaint control number when available.
- Include source URL and source traceability fields where reviewers need to verify
  extracted data.
- Group delay calculation fields and review flags in a predictable order.
- Prefer review views for common workflows and normalized tables for lower-level
  detail.
- Use metadata labels and descriptions to explain views, columns, and saved
  queries.
- Avoid exposing users to ambiguous status or flag columns without explanatory
  documentation.

The retained local review views should remain aligned with
`docs/user/local-review-workflow.md`.

## Saved-query expectations

Saved queries retained for validation, inspection, local exploration, and export
support should:

- Support common review tasks such as filtering complaints by facility, viewing
  records with review flags, checking source traceability, summarizing allegation
  counts, and listing newest reports.
- Use clear names and descriptions.
- Include source traceability columns when the query result may be exported or
  used for review notes.
- Avoid implying that review flags are conclusions.
- Prefer parameterized queries for reviewer-entered values such as facility
  number.

## Export usability expectations

CSV exports should:

- Keep clear, stable header rows.
- Preserve source traceability columns when records may be cited, shared, or
  reviewed outside Datasette.
- Include enough context for reviewers to understand facility, complaint, finding,
  dates, review flags, and source details.
- Avoid unexplained abbreviations.
- Avoid color-only or formatting-only meaning.
- Be documented as derived review outputs, not official source records.
- Include caution language in surrounding notes when exporting delay review flags.

## Source traceability expectations

Every extracted record must remain traceable to its source document. Review
experiences should make it easy to inspect:

- Source URL.
- Raw SHA-256 hash.
- Raw path when available locally.
- Connector name and version.
- Retrieval timestamp.
- Report index or document type when available.
- Extraction audit details when field-level review is needed.

Source traceability must not be removed to simplify a view, query, export, or
presentation layer when the output may be used for review or citation.

## Delay-flag caution language

Delay review flags are screening aids. They do not prove that an investigation
was delayed.

Use language such as:

```text
flagged for review based on available extracted dates
```

Do not use language such as:

```text
delayed investigation
```

unless a qualified reviewer has independently verified the source record and the
project has documented an approved basis for that conclusion.

Report date may be used as a review proxy only when no first investigation
activity date or visit date is available. Report date alone does not establish
when investigation activity began. Missing dates must be described as missing
from extracted fields, not as evidence that an event did not occur.

## POC scope versus later product work

Proven in the proof of concept and retained for local attorney-review aid:

- SQLite review views that support common reviewer tasks.
- Datasette metadata with clearer labels, descriptions, and saved queries.
- Script output that tells reviewers what command or view to open next.
- User documentation for browsing, filtering, source checking, and exporting.
- Accessible CSV export guidance.
- Fixture-backed tests for extraction and review behavior.
- Small usability improvements that preserve the existing Python, SQLite, and
  Datasette architecture.

Belongs in current production-discovery:

- Product requirements for persistent navigation, saved reviewer state, guided
  queues, annotations, corrections, collaboration, contextual help, accessible
  exports, tester feedback, hosted tester readiness, reset/reload processes, and
  fewer-click reviewer paths.
- Architecture boundaries for ingestion, storage, validation, review state,
  correction state, export generation, and future presentation.
- ADRs comparing production-stack options without selecting a stack before the
  requirements are reviewed.

Belongs in future production-build or production-operations work:

- A custom frontend application.
- Full review queues, assignment workflows, or reviewer accounts.
- Interactive dashboards beyond validation, inspection, or prototype work.
- Role-based access control for a hosted product.
- Custom charting or visualization layers.
- PDF report generation unless accessibility can be validated.
- Optional paid services or account-specific platform features unless explicitly
  approved and documented.

Production-discovery should define the primary reviewer UX requirements while
preserving source traceability, accessibility, cautious public-source language,
raw source preservation, and deterministic extraction safeguards.
