# Getting Started

This project creates a searchable dataset from public complaint and facility reports.

## What you can do

- Search complaint records.
- Filter by facility, date, allegation category, and finding.
- Open the original public source URL.
- Review calculated delay fields.
- Export structured data.

## Local database

Normalized ingestion results can be stored in the local SQLite database for browsing with Datasette. Stored records include source traceability fields such as source URL, raw file hash, raw path, connector name, connector version, retrieval time, and report index when available.

## Fixture-backed sample mode

From the repository root, run the bundled sample script:

```powershell
.\scripts\run-ccld-sample.ps1
```

The script initializes `data/processed/ccld.sqlite` if needed and writes the available fixture-backed CCLD sample report into SQLite. The bundled facility detail fixture discovers 40 report candidates, but only bundled fixture-backed report content is written. At present, the bundled report fixture is facility `157806098`, report index `3`. It prints the database path and the Datasette command to open it.

This mode uses bundled test fixtures only. It does not make live web requests, and it is the right first check when you want a repeatable local sample.

You can choose a different local database path:

```powershell
.\scripts\run-ccld-sample.ps1 -DbPath data\processed\sample.sqlite
```

## Live CCLD fetch mode

Live mode is explicitly user-invoked and accesses the public CCLD external site. The default is conservative: if you do not provide facility input, the script uses facility `157806098`; if you do not provide a limit, the script fetches one discovered report per facility. The workflow does not crawl statewide, expand searches, or fetch every report unless you explicitly use `-All` and set `-MaxRequests` high enough.

Start with one report so you can confirm the workflow before fetching more:

```powershell
.\scripts\run-ccld-live-fetch.ps1 -Limit 1
```

You can also provide the facility number explicitly:

```powershell
.\scripts\run-ccld-live-fetch.ps1 -FacilityNumber 157806098 -Limit 1 -MaxRequests 1
```

To fetch one discovered report for two or three explicit facilities, pass multiple facility numbers. `-Limit` applies per facility, and `-MaxRequests` is the overall report-request guard:

```powershell
.\scripts\run-ccld-live-fetch.ps1 -FacilityNumber 157806098, 123456789 -Limit 1 -MaxRequests 2
```

```powershell
.\scripts\run-ccld-live-fetch.ps1 -FacilityNumber 157806098, 123456789, 987654321 -Limit 1 -MaxRequests 3
```

For a small text or CSV file, put one facility number per line or use comma-separated values:

```text
facility_number
157806098
123456789
987654321
```

Then pass the file path:

```powershell
.\scripts\run-ccld-live-fetch.ps1 -FacilityInputPath .\facility-numbers.csv -Limit 1 -MaxRequests 3
```

Before making report requests, the live script prints a facility identifier
intake summary. It shows the accepted facility identifiers, duplicate
identifiers ignored, and blank, comment, or header values ignored. Invalid
facility identifiers are rejected before report discovery or fetching begins.

After one report per facility succeeds, try a small larger per-facility limit such as three or five reports. `-MaxRequests` must be at least as large as the total selected report count across all facilities:

```powershell
.\scripts\run-ccld-live-fetch.ps1 -Limit 3 -MaxRequests 5
```

You can choose a different local database path or raw file directory:

```powershell
.\scripts\run-ccld-live-fetch.ps1 -Limit 5 -MaxRequests 5 -DbPath data\processed\live-ccld.sqlite -RawDir data\raw\ccld
```

To fetch every discovered report for facility `157806098`, use `-All` and intentionally raise `-MaxRequests` high enough for the discovered report count:

```powershell
.\scripts\run-ccld-live-fetch.ps1 -All -MaxRequests 50
```

The live script prints a warning before making requests, uses a clear user agent, applies a request timeout, limits report requests unless `-All` is used, enforces `-MaxRequests`, and does not use an aggressive retry loop.

After the run, the script prints a live fetch summary with the number of
facilities requested, facilities with records discovered, facilities with no
records discovered, discovery failures, report candidates discovered, selected,
skipped by limit, fetched, written to SQLite, and failed. The facility summary
shows a status and the same counts by facility so you can spot no-record,
skipped-by-limit, partial-failure, or written-record outcomes before opening logs
or Datasette. Treat failed, skipped, or no-record items as run states in the
derived workflow, not as conclusions about the public source.

Downloaded report files are saved under `data/raw/ccld` by default. The `data/raw` path is ignored by Git so live public source files stay local unless you intentionally move or copy them. Ingestion reads the saved raw files, records their SHA-256 hashes, and writes source traceability fields to the `source_documents` table.

Rerunning the same command updates existing SQLite rows by stable identifiers rather than duplicating the same source documents.

## Local hosted CCLD request page

Developers and local testers can also run the hosted scaffold and open the
CCLD-only request page:

```powershell
.\scripts\run-hosted-scaffold.ps1 -Port 8000
```

Then open `http://127.0.0.1:8000/ccld/facilities` to search local/test CCLD
facility reference data by facility/license number, facility name, city, county,
ZIP code, facility type, or status. To use a full local/test facility CSV, set
`CCLD_FACILITY_REFERENCE_CSV` or place the file at the ignored local path
`data/raw/ccld/facility-reference.csv`. If no full CSV is configured or available,
the lookup falls back to the committed tiny fixture CSV. The page shows which
reference source is active. Use a matching facility to carry the facility/license
number into the request form. Manual entry is still available at
`http://127.0.0.1:8000/ccld/records/request` when you already know the number.
The request form and result queue show a request-context confirmation so you can
check whether the request came from facility lookup or manual entry, which
facility/license number and date range are being used, and which local/test
facility reference source is active. Use the change-facility/date links when the
context is not the one you intended.
Across the hosted CCLD pages, the same terms are used for the same ideas:
facility/license number, CCLD request context, facility/date request, loaded
local/test CCLD records, source-derived records, source traceability, reviewer-
created notes/status, reviewer-status filter, suggested next record, and manual
feedback checklist.

The request page accepts a CCLD facility/license number and optional date range,
reads existing seeded
source-derived records, can load or refresh matching rows from local validated
hosted seeded-corpus output, and links matching rows into the hosted reviewer
UI. It also includes a first-time help page at `/ccld/help`, contextual
facility/date/load/review help, feedback guidance, a structured copyable feedback
checklist for the current request and queue state, and a facility/date-scoped
review queue with one row per matching complaint record, triage summaries,
progress counts, reviewer note/status cues, source-traceability availability
cues, suggested next-record links, and a reviewer-status filter. Reviewer detail
pages include a plain-language record summary, source traceability, source-
confidence cues, related context, reviewer notes/statuses, CCLD return links,
and feedback clues for the selected record. The detail page explains available
and missing source traceability and complaint-field values with local/test
wording, names existing proxy flags when the loaded record supports them, and
asks you to review source context before adding reviewer-created notes or status.
It also includes field-note guidance for phrasing cautious reviewer-created
observations when a value is present, not available locally, proxy-flagged, or
still confusing after source traceability review.
Reviewer detail also bridges those record-specific observations into the existing
manual feedback checklist on the CCLD request queue; it does not create a second
checklist or save feedback.
The request queue uses the same checklist for queue observations and reviewer-
detail observations, including filter confusion, source-confidence questions,
note/status confirmation behavior, return-to-queue refresh behavior, and next-
record navigation confusion.
Missing local/test values should be described as not available in the local/test
record, not as public-source absence, record incompleteness, or data loss. After adding a note or status in reviewer detail, return to the
CCLD request page and submit the same request to see updated progress.
When a note or status is saved, the detail page confirms the reviewer-created
update, shows it in the reviewer-created state section, and links back to the
CCLD request queue so the updated note/status cues can be checked.
Use the same facility/date request context when returning to the queue. In this
local/test MVP, you may need to submit the same request again to refresh queue
progress and note/status cues before continuing to the next record.
Next-record cues are local/test navigation help only. They are derived from the
current CCLD request context and existing reviewer-created note/status rows;
they are not persisted queue assignments, automatic record claims, or official
workflow state.
If a reviewer-status filter shows no queue rows, the records may simply be hidden
by that filter for the same facility/date request context. Use the all-records
recovery action or choose a different status to continue review, and report any
confusing filter behavior in the manual feedback checklist.
The reviewer detail feedback handoff cue tells you which record-specific source
traceability, source context, note/status confirmation, same-queue return, queue
refresh, unexpected-record, confusing-label, wording, keyboard-flow, or next-step
observations to carry into the existing manual feedback checklist.
The local/test browser pages include skip-to-main links, visible start-here or
next-step guidance, specific button/link text, and manual checklist copy
instructions so a first-time tester can use keyboard navigation and visible page
text to move through the MVP flow. Start the review session from home or facility
lookup, confirm the request context, use the loaded local/test queue, open
reviewer detail for source traceability, source-confidence, and field-note cues,
save reviewer notes/status only as tester-created observations when useful,
return to the same queue/request context to refresh progress, continue to the
next record, and copy the single manual feedback checklist. The browser pages do
not save a review session, persist queue state, create a second checklist, save
feedback, run live CCLD retrieval, execute connectors, or build artifacts.
If the request finds no matching rows, the result page searched only currently
loaded local/test source-derived records. It shows the facility/license number,
date range, rows already loaded for that facility before date filtering, and the
local validated load state. Confirm the facility/date context first, then either
change the criteria, use the local validated load action when prepared data is
available, or run the outside-browser live-fetch and artifact-builder workflow
before returning to load/refresh. A no-match page is not proof that the public
portal has no matching records.
The feedback checklist prompts for facility lookup, request criteria, queue
triage and filters, source traceability cues, reviewer detail, note/status save
confirmation, return-to-queue behavior, missing or unexpected records, confusing
wording, and copy friction. It is not saved, sent, emailed, exported, or
persisted by the app; copy it into the agreed external feedback channel
manually. Full/raw facility CSV files must stay out of the repository. The
lookup and request pages do not run live CCLD retrieval, execute connectors,
persist lookup or feedback data, or mutate reviewer notes/statuses from the
browser request page. When matching local validated records are unavailable, it
shows the explicit live-fetch command that must be run outside the hosted UI.
After that outside-browser CCLD pipeline output is validated, a developer/tester
can build the local/test hosted seeded-corpus JSON artifact with:

Deferred production-readiness work such as auth provider integration, audit UI,
exports, reset/reload execution, deployment, and persisted feedback remains
tracked in project docs, but it is sequenced behind the local/test CCLD MVP
workflow unless it unlocks tester value or resolves a concrete MVP-blocking risk.

```powershell
.\scripts\build-hosted-ccld-artifact.ps1 -DbPath data\processed\ccld.sqlite -FacilityNumber 157806098 -Overwrite
```

When the hosted app is configured for GitHub Issues feedback, use `/feedback` to
submit bug reports, feature requests, or new data source suggestions. If GitHub
feedback is not configured, the page says so and does not send feedback.

An optional QNAP-first Docker Compose runtime is available for production-like
testing with PostgreSQL in Docker. It uses the same hosted scaffold pages, keeps
real database settings in an untracked `.env` file, and does not add production
sign-in, public hosting approval, completed CCLD retrieval jobs, or connector
execution. Developers should use
[docs/developer/qnap-docker-runtime.md](../developer/qnap-docker-runtime.md) for
those runtime steps. Operators can use `scripts/verify-qnap-pilot-workflow.ps1`
to verify the untracked `.env`, Docker Compose configuration, running containers,
PostgreSQL readiness, and route surface before inviting testers. QNAP is the
first pilot runtime, not a permanent platform lock-in. Operators should also use
the [QNAP pilot operator checklist](../developer/qnap-pilot-operator-checklist.md)
before inviting early testers.

The hosted request page now includes the first controlled browser-triggered,
server-executed CCLD retrieval job slice for complaint records. When the server
is configured with retrieval enabled, PostgreSQL, and raw source storage, use the
record type control and the controlled retrieval button to request CCLD complaint
records for one facility/date range. All supported record types currently means
complaint records only. If retrieval is not configured, the page shows safe
setup-required guidance and creates no retrieval job. Retrieval status messages
show what you entered, whether records were imported, where to review imported
records, and when to use `/feedback` for confusing wording or behavior. The
browser does not scrape or receive connector credentials.

Developers running the local scaffold can opt into a fixture-backed successful
retrieval demo with `CCLD_RETRIEVAL_DEMO_MODE=mock-success` only when explicit
local-dev auth and retrieval raw storage are configured. That demo lets the
browser exercise the successful job/import/history/detail/queue flow without
live CCLD calls. It is not production retrieval, not a public-source completeness
check, and still supports complaint records only.

Open `http://127.0.0.1:8000/ccld/retrieval/jobs` to see recent controlled
retrieval job history for the current local/test scope. The page shows the
facility/license number, date range, record type, job state, timestamps,
imported-record count, safe warnings or errors, and a review-queue link when a
job imported records. Use it to check what was submitted and what happened after
the initial request page. It is not an audit export, source-completeness report,
or legal conclusion. Use a history-row detail link to open one job at
`/ccld/retrieval/jobs/detail?job_id=` when you need the same safe status,
timestamp, count, raw-artifact-preserved, review-link, help, history, and
feedback context for a single job. The detail page does not show raw source
narrative content, raw artifact contents, raw server paths, or private values.

Return to `/ccld/records/request` and use the local validated CCLD load action
to load or refresh matching source-derived rows from that JSON artifact. The
artifact builder and request page do not run live CCLD retrieval from the
browser.

## Start Datasette

After the sample or live database is populated, run the command printed by the script:

```powershell
datasette "data/processed/ccld.sqlite" --metadata "data/processed/ccld.datasette-metadata.json"
```

Open the local URL printed by Datasette in a browser.

If you wrote live results to a different database path, open that path instead:

```powershell
datasette "data/processed/live-ccld.sqlite" --metadata "data/processed/live-ccld.datasette-metadata.json"
```

The printed command includes a Datasette metadata file. That metadata adds the project title, database description, review-oriented table and view descriptions, column notes, suggested sort fields, delay flag caution language, source traceability explanations, and saved query examples. See [Local Review Workflow](local-review-workflow.md) for the guided review steps.

Open the `review_home` saved query first. It lists the main review tasks and points to the low-noise complaint review, detailed complaint review, delay triage, facility comparison, source verification, and CSV export paths.

The saved query examples include `review_home`, `complaint_review_start_here`, `complaints_by_facility`, `complaint_review_export_with_traceability`, `records_with_delay_review_flags`, `facilities_with_delay_review_flags`, `source_traceability_by_facility`, `newest_reports`, `allegation_summary_by_facility`, and `source_traceability_check`.

## Where to start

Start with the `review_home` saved query. It is a small task menu inside Datasette, not a dashboard or custom web interface. Use it to choose whether you want to review complaints, find records needing closer review, compare facilities, verify sources, or export CSVs.

Then open `complaint_review_start_here` or `complaint_first_pass_review` for the guided, source-traceable, low-noise complaint list.

## Tables to open first

After `review_home` and `complaint_review_start_here`, use these Datasette views in this order:

1. `complaint_first_pass_review` is the low-noise first-pass review view. It combines facility number, facility name, complaint dates, finding, allegation count and summary, one review flag summary, source URL, raw SHA-256 hash, raw path, connector metadata, retrieval time, report index, and IDs for lower-level follow-up.
2. `complaint_review_summary` is the fuller complaint review view. It adds detailed delay calculations, separate review flag columns, extraction confidence, and broader complaint review context.
3. `facility_complaint_summary` gives one row per facility with complaint count, allegation count, earliest and latest complaint received dates, and a count of records with delay review flags.
4. `delay_review_flags` shows only complaint records with one or more delay or review flags. Use it as a triage list for closer review, not as proof that an investigation was delayed.
5. `source_traceability_review` lists source URL, raw SHA-256 hash, raw path, connector name, connector version, retrieval time, and report index so reviewers can confirm where each record came from.

Then use these normalized tables when you need lower-level detail:

1. `facilities` lists the facility identifiers and names. Use this table to confirm that the database contains the facility you intended to review.
2. `source_documents` lists each public source document, source URL, raw file hash, connector name, connector version, retrieval time, and report index when available. Use this table to verify source traceability before relying on extracted complaint fields.
3. `complaints` lists complaint dates, findings, delay fields, review flags, and complaint control numbers. Use this table for the main complaint review.
4. `allegations` lists allegation text and categories linked to each complaint by complaint ID.
5. `events` lists dated events extracted from reports when available.
6. `extraction_audit` lists field-level extraction methods, source text, confidence, and warnings when available.

The table and column names are intentionally close to the data contract so exported CSV files remain understandable outside Datasette.

## Accessibility notes

Datasette pages are browser-based tables. Use keyboard navigation, browser zoom, and built-in search or filter controls as needed. Exported CSV files include clear table headers; keep those headers when sharing exports so screen reader users and spreadsheet users can understand each field.

Do not rely on color alone when reviewing exported findings or status fields. Keep source URL and raw hash columns in review exports so records can be checked against the public source.

## Important limitation

The dataset is derived from public source reports. The public portal remains the source of record.

Live fetched records reflect what the public site returned at the time of retrieval. Public reports may later change, be corrected, become unavailable, or use layouts the current extractor does not fully understand. Delay review flags are screening aids only and do not prove that an investigation was delayed.
