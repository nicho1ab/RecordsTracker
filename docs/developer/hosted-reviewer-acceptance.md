**Purpose**: Acceptance checklist for validating the hosted local/test reviewer flow without performing persistent changes.

- **Environment**: An already-running hosted scaffold (non-auth) serving reviewer UI.

- **Ports/URLs**:
  - **Live**: `http://127.0.0.1:8003`
  - **Fixture/mock**: `http://127.0.0.1:8010`

- **Commands**:
  - Run tests: `./scripts/test.ps1`
  - Capture evidence (fixture): `./scripts/capture-hosted-ui-evidence.ps1 -BaseUrl http://127.0.0.1:8010 -Mode fixture`
  - Verify acceptance checks (non-mutating): `./scripts/verify-hosted-reviewer-acceptance.ps1 -BaseUrl http://127.0.0.1:8010 -Mode fixture -IncludeCapture`

- **Context sample**:
  - Facility: `157806098`
  - Date range: `2026-01-01` to `2026-01-31`

- **Acceptance flow (manual)**:
1. Start the scaffold server for the chosen mode (live or fixture). Confirm reachable at the port above.
2. Open the reviewer UI: `/reviewer` and inspect the Worklist.
3. Open Packet Preview with no context: `/reviewer/packet/preview` — the page MUST show explicit guidance such as "No facility/date packet context was supplied." and MUST NOT display a passive label "Date range: not provided" alongside included records.
4. Open Packet Preview with context: `/reviewer/packet/preview?facility_number=157806098&start_date=2026-01-01&end_date=2026-01-31&request_context_origin=manual_entry` — the page SHOULD list included records and show the date range.
5. Open Packet Draft with no context: `/reviewer/packet/draft` — page MUST show explicit guidance and MUST NOT present "Date range: not provided".
6. Open Packet Draft with context: `/reviewer/packet/draft?facility_number=157806098&start_date=2026-01-01&end_date=2026-01-31&request_context_origin=manual_entry` — page SHOULD show the draft UI (note: draft intentionally hides workflow rail for print/copy; this is expected).
7. Run `./scripts/capture-hosted-ui-evidence.ps1 -BaseUrl <url> -Mode fixture` to produce the evidence packet and `route-assertions.csv`.
8. Inspect `route-assertions.csv` inside the produced packet. There MUST be rows for `packet-preview-empty`, `packet-preview-context`, `packet-draft-empty`, and `packet-draft-context`. Workflow-step assertions for `packet-draft-*` routes must be `PASS` with a message that indicates the draft intentionally hides the workflow indicator and the assertion was skipped.

- **What this proves**:
  - Preview routes explicitly indicate missing context and do not silently label results with a misleading passive date-range message.
  - Draft routes intentionally hide the workflow rail; evidence capture reflects this choice and does not flag it as a warning.

- **What this does not prove**:
  - End-to-end persistence or remote retrieval writes (the acceptance script and checklist are non-mutating by default).

- **Post-acceptance**:
  - Upload the produced evidence packet(s) to the reviewer acceptance folder for audit.
  - If additional exploratory write checks requested, run `./scripts/verify-hosted-reviewer-acceptance.ps1 -BaseUrl <url> -Mode fixture -RunWriteChecks` (ONLY when a dedicated test/staging instance is OK to receive transient reviewer-created state).

- **Notes**:
  - The acceptance script `scripts/verify-hosted-reviewer-acceptance.ps1` defaults to non-mutating route GET checks and will only run the capture script when `-IncludeCapture` is provided.
  - If `gh` is available and you're preparing a PR/merge, run `gh pr status` to confirm checks before merging.
