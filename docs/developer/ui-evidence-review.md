# Hosted UI Evidence Review

## Why Evidence Packets Exist

The hosted CCLD RecordsTracker UI changes quickly. Evidence packets give reviewers a repeatable way to inspect the same route set without relying on ad hoc screenshots, stale ports, or manually copied browser state.

Use an evidence packet after each hosted UI branch and before asking another reviewer or ChatGPT to evaluate the UI. The packet is a local review artifact only. It is not an audit export, legal report, source-completeness report, production monitoring artifact, product export, or proof of public-source coverage.

## What The Packet Captures

The capture command performs GET-only requests against an already-running local hosted app URL. It writes a timestamped folder under ignored `data/processed/ui-evidence/` with:

- `manifest.json` with mode, base URL, viewport, route status, discovered detail links, git state, screenshot status, warnings, and the local-review boundary statement.
- `route-status.csv` with route status, title, first H1, and generated file paths.
- `route-assertions.csv` with pass/warn/fail checks for common UI review problems.
- `route-text-markers.txt` with titles, headings, buttons, and disclosure summaries.
- `html/` route HTML snapshots when routes respond.
- `text/` plain-text route summaries derived from HTML.
- `accessibility/` lightweight headings, links, forms, and landmark summaries.
- `diagnostics/` git state, recent log, capture command, and non-secret capture settings.
- `screenshots/` route screenshots when local screenshot tooling is available.

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

## One-Command Convenience Wrapper

For local review, the wrapper can start one hosted mode and capture evidence after the root route responds:

```powershell
.\scripts\run-and-capture-hosted-ui-evidence.ps1 -Mode fixture -Port 8010 -KillExistingPortProcess
```

The wrapper prints the URL, process ID, stop command, and evidence packet path. Use `-KillExistingPortProcess` only when you intentionally want to stop the process currently listening on that port.

## Screenshot Support

The capture command tries to use local Playwright first when available, then local Microsoft Edge or Chrome headless capture. If no screenshot tool is available, the command still writes `manifest.json`, `route-status.csv`, HTML snapshots, text summaries, assertion rows, and accessibility summaries. Screenshot absence is reported in the manifest and command output.

Do not add CI requirements for screenshot capture. Visual comparison screenshots are intentionally out of scope for CI because they are brittle and depend on workstation browser tooling.

## Uploading For Review

Upload or summarize the whole timestamped folder under `data/processed/ui-evidence/`, not individual screenshots. At minimum, include:

- `manifest.json`
- `route-status.csv`
- `route-assertions.csv`
- `route-text-markers.txt`
- `accessibility/`
- `html/` and `text/`
- `screenshots/` when available

Generated evidence is ignored locally and should be reviewed before sharing. Do not share packets that contain unexpected private values, raw source narrative, cookies, provider claims, tokens, private URLs, stack traces, connection strings, or server-specific private paths.

## What It Does Not Prove

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
