# Hosted UI Evidence Review

## Why Evidence Packets Exist

The hosted CCLD RecordsTracker UI changes quickly. Evidence packets give reviewers a repeatable way to inspect the same route set without relying on ad hoc screenshots, stale ports, or manually copied browser state.

Use an evidence packet after each hosted UI branch and before asking another reviewer or ChatGPT to evaluate the UI. The packet captures local UI route, screenshot, text, and accessibility evidence for review.

## What The Packet Captures

The capture command performs GET-only requests against an already-running local hosted app URL. It writes a timestamped folder under ignored `data/processed/ui-evidence/` with:

- `manifest.json` with mode, base URL, viewport, route status, discovered detail links, git state, screenshot status, diagnostic notices, and evidence purpose.
- `route-status.csv` with route status, title, first H1, and generated file paths.
- `route-assertions.csv` with pass/warn/fail checks for common UI review problems.
- `route-text-markers.txt` with titles, headings, buttons, and disclosure summaries.
- `html/` route HTML snapshots when routes respond.
- `text/` plain-text route summaries derived from HTML.
- `accessibility/` lightweight headings, links, forms, and landmark summaries.
- keyboard-flow marker assertions showing whether a route exposes visible
	keyboard-flow guidance for moving through the current hosted review step.
- a facility-hub route capture that exercises `/ccld/facilities/detail` as a
	GET-only navigation surface from directory lookup into existing complaint
	request and review routes.
- a facility-priority route capture that exercises `/ccld/facilities/review-priority`
  as a GET-only view over uploaded public summary-field review cues.
- a facility-intelligence route capture that exercises `/ccld/facilities/intelligence`
  and asserts the cross-facility decision heading plus a recommended-next
  complaint action over authorized loaded records
	as a GET-only dashboard over transparent public summary-field review-priority
	indicators.
- a matrix-export route capture that exercises `/reviewer/records/matrix.csv`
	as a GET-only CSV export over loaded local/test complaint records for the
	stable sample facility/date context.
- a reviewer facility-priorities route capture that exercises
  `/reviewer/facilities/priorities` as a GET-only worklist over authorized
  loaded complaint records with deterministic factors, filters, pagination,
  complaint-review links, and original-source link states.
- a reviewer facility-trends route capture that exercises
  `/reviewer/facilities/trends` as a GET-only monthly/quarterly comparison over
  authorized loaded complaint records with coverage states, visible anomaly
  rules and contributing counts, filters, and complaint-detail links.
- `diagnostics/` git state, recent log, capture command, and non-secret capture settings.
- `screenshots/` route screenshots when local screenshot tooling is available.
- a sibling `.zip` packet after successful capture, suitable for local review
  or upload after the generated files have been checked for unexpected private
  values.

The packet never submits forms, triggers controlled retrieval, loads or imports data, mutates reviewer-created state, runs reset/reload, calls GitHub, performs production authentication, captures cookies, prints response headers, or records environment variable values.

## Port Convention

Use these ports for UI evidence review unless a task handoff says otherwise:

- `8003` = live public CCLD mode
- `8010` = fixture/mock demo mode
- Avoid relying on `8000` for UI review evidence unless the current branch or handoff explicitly says it is the active server.

Before starting a review server, clear stale local hosted processes when appropriate:

```powershell
foreach ($p in 8000,8003,8010) { Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force } }
```

## Live Evidence

Start live mode in one terminal:

```powershell
.\scripts\run-hosted-complaint-retrieval-live.ps1 -Port 8003
```

Capture evidence from another terminal:

```powershell
.\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl http://127.0.0.1:8003 -Mode live
```

Live mode may make public CCLD HTTP requests only if a browser user submits a controlled retrieval form. The capture command itself is GET-only and does not submit retrieval.

For focused issue #416 facility-priorities evidence after the hosted app is
already running, capture only the required reviewer route states:

```powershell
.\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl http://127.0.0.1:8003 -Mode live -Issue416
```

For focused issue #418 complaint-trend evidence after the hosted app is already
running with the governed local records being reviewed:

```powershell
.\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl http://127.0.0.1:8003 -Mode live -Issue418
```

## Fixture/Mock Evidence

Start fixture/mock mode in one terminal:

```powershell
.\scripts\run-hosted-complaint-retrieval-demo.ps1 -Port 8010
```

Capture evidence from another terminal:

```powershell
.\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl http://127.0.0.1:8010 -Mode fixture
```

Fixture/mock mode uses committed fixtures and does not make live CCLD calls.

Focused issue #416 fixture evidence uses the same route set and assertions:

```powershell
.\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl http://127.0.0.1:8010 -Mode fixture -Issue416
```

## One-Command Convenience Wrapper

For local review, the wrapper can start one hosted mode and capture evidence after the root route responds:

```powershell
.\scripts\run-and-capture-hosted-ui-evidence.ps1 -Mode fixture -Port 8010 -KillExistingPortProcess
```

The wrapper prints the URL, process ID, stop command, evidence packet path, and
evidence ZIP path. Use `-KillExistingPortProcess` only when you intentionally
want to stop the process currently listening on that port.

## Screenshot Support

The capture command tries to use local Playwright first when available, then local Microsoft Edge or Chrome headless capture. If no screenshot tool is available, the command still writes `manifest.json`, `route-status.csv`, HTML snapshots, text summaries, assertion rows, and accessibility summaries. Screenshot absence is reported in the manifest and command output.

Do not add CI requirements for screenshot capture. Visual comparison screenshots are intentionally out of scope for CI because they are brittle and depend on workstation browser tooling.

## Uploading For Review

Upload or summarize the sibling ZIP created by the capture command, or the whole
timestamped folder under `data/processed/ui-evidence/`, not individual
screenshots. The point is to review the actual rendered UI, including labels,
links, buttons, screenshots, page text, and HTML, so exact tester instructions
can be written from what the site actually shows.

Evidence is not useful if no one reviews it. At minimum, include:

Upload or summarize the whole timestamped folder if you do not use the ZIP.

- `manifest.json`
- `route-status.csv`
- `route-assertions.csv`
- `route-text-markers.txt`
- `accessibility/`
- `html/` and `text/`
- `screenshots/` when available

Generated evidence is ignored locally and should be reviewed before sharing. Do not share packets that contain unexpected private values, raw source narrative, cookies, provider claims, tokens, private URLs, stack traces, connection strings, or server-specific private paths.

The capture command creates a sibling ZIP for every successful run and prints
both paths. When the hosted tester-readiness verifier is run with
`-IncludeCapture`, it also packages the generated timestamped evidence folder
into a sibling ZIP and prints both paths. The ZIP is a local UI review artifact
for route, screenshot, text, and accessibility review. After the packet is
reviewed for private values, the ZIP can be uploaded to ChatGPT or shared as a
convenience copy of the same local review artifact. Do not commit generated
evidence folders or ZIP packets unless a specific repository workflow explicitly
says to do so.

## Review Scope

The evidence packet is a lightweight UI review aid. It does not replace:

- accessibility audits or assistive-technology review;
- source traceability validation;
- extraction or schema tests;
- security review;
- production monitoring;
- audit exports;
- legal review;
- public-source completeness analysis.

It should help reviewers answer whether the current UI route surfaces are coherent, accessible enough for local review, mode-labeled correctly, and free of obvious stale-port, navigation, disclosure, and private-value problems.

## Packet preview / draft evidence route semantics

Evidence captures include explicit route labels for packet preview and draft variants to avoid ambiguity when context (facility/date) is missing:

- `packet-preview-empty`: A preview route capture made without facility/date query context. The UI must present explicit guidance (e.g., "No facility/date packet context was supplied.") and must not silently show "Date range: not provided" alongside included records.
- `packet-preview-context`: A preview route capture made with facility/date query context (stable seeded context). This route should list included records and render the date range.
- `packet-draft-empty`: A draft route capture made without facility/date query context. The UI must present explicit guidance and must not show "Date range: not provided".
- `packet-draft-context`: A draft route capture made with facility/date query context. Drafts intentionally hide the workflow rail for print/copy; evidence assertions should mark the draft workflow-step check as `PASS` with a message describing the intentional skip.

These route captures are route-level UI evidence for reviewing screen content, route behavior, and packet-preparation context. Review backend retrieval status and export persistence through the dedicated job, database, and operator evidence paths.
