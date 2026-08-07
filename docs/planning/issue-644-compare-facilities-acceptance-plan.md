# Issue #644 Compare Facilities acceptance-evidence plan

## Scope and boundary

This mode captures only the local `fixture-demo` hosted application. It reuses
the established #642 interaction and pagination capture, #643 drill-down and
return-context contracts, #648 acceptance-review structure, #670 packet
accounting, and #671 runtime-event ledger. It does not create another launcher,
browser harness, packet format, validator, production data path, or deployment.
It is not deployed-host acceptance evidence.

## Required capture inventory

The packet records Complaint Patterns, Licensing and Visits, Complaint Activity
Over Time, Facility Overview, Complaint Overview/detail, and their canonical
return continuity. It includes populated, filtered-empty, limited/partial,
source-unavailable, not-loaded, controlled-error, selected-facility, pagination,
typeahead, multi-select, chips, hover, active, keyboard-focus, stress, and print
states. Loading is `NOT APPLICABLE` only because no deterministic loading fixture
exists, no loading state is fabricated, and application behavior is not changed
solely to create evidence.

## Viewports and interaction evidence

Required viewports are desktop 1440x1200, measured Surface 1189x671, 500x900,
mobile 390x844, and 1280x900 at observed scale 2.0. The Surface visual-viewport
scale and DPR are derived from its captured browser-state evidence, not supplied
as an external display observation. Pagination must prove disabled Previous on the first page,
both controls enabled on the middle page, disabled Next on the final page,
keyboard focus for both controls, and retained filters/context. Hover and active
evidence uses the established CDP input path.

## Automated gates and human decisions

Before packet accounting, file-index finalization, or ZIP publication, the
Issue #644 coordinator requires a nonempty rendered print PDF with one through
four pages and mandatory density results: 12 desktop, 16 Surface/500px, and 24
mobile/200-percent viewport heights. Each density result records its route,
viewport and document heights, computed ratio, governed ceiling, and outcome.
Captured browser-state viewport metadata is authoritative; conflicting
hard-coded display metadata fails closed. The runtime ledger preserves raw
console and network inventories and permits only the exact Cloudflare beacon
optional-telemetry classification. Packet accounting reconciles physical files,
ZIP entries, manifest, file index, and reported count only after these automated
visual prerequisites pass.

There is one versioned `hosted-ui-acceptance-v1` acceptance record and two
separate human artifacts: independent visual review and owner acceptance. No
standalone Figma matrix artifact is required. Approved-design requirement
classifications belong in the acceptance record when independent review is
completed. Before then, the manifest acceptance state, pending human templates,
and absence of a completed acceptance record truthfully represent the
pre-review state. Automation must not assign a visual PASS or owner decision.
The retained `20260806-003117Z-issue-644-local` packet is diagnostic only;
human review must not begin until automated print, density, and viewport-metadata
prerequisites pass.

The retained diagnostic print used the correct unfiltered, current-page Compare
Facilities route, but printed its 25 normal screen cards as a full vertical
stack and retained the duplicate bottom result orientation. That produced 20
pages, including a nearly empty trailing page. The print-only correction keeps
the page identity, active scope, facility identity, complaint, source, and
status content while compacting current-page cards into concise, single-flow
print rows and suppressing the redundant bottom orientation. It does not alter normal
screen markup, pagination, filtering, or fixture scope.

The separate screen-density investigation found no combined Issue #642/#643
state or stale measurement: the populated desktop route rendered one normal
25-facility page, whose stacked ordinary cards occupied nearly the entire
measured document. RT-PAG-001 retains the approved 25-row seek/keyset page and
the existing content, controls, routes, and evidence contract. The compact
inventory treatment instead groups the same reviewer facts and actions into
responsive rows, preserving normal document flow outside desktop without
hiding content or weakening a density ceiling.

## Stop conditions

Stop before publication if a required state cannot be truthfully captured, any
automated packet gate fails, the fixture scope escapes local demo mode, the
working-tree file boundary changes, or the required validation does not pass.
