# Known Limitations

- The public portal remains the source of record.
- Extracted data may contain errors.
- Some reports may have missing or inconsistent fields.
- Report date may not be the same as first investigation activity date.
- Delay review flags are screening aids and do not prove that an investigation was delayed.
- When `first_investigation_activity_date` is missing, delay review may rely on visit date or report date as a proxy basis. Report date alone does not establish when investigation activity began.
- Narrative extraction may require manual review.
- The first CCLD extraction fixture covers one public facility report for facility number `157806098`; additional report layouts need their own fixtures before broader use.
- The local sample database is populated only from bundled fixtures. It does not make live web requests and currently writes the single report fixture that has bundled raw content.
- Live CCLD fetch mode is explicitly user-invoked, accepts only provided facility numbers, and depends on the public site being available when the command runs. It does not perform statewide crawling or automatic search expansion.
- Facility identifier intake accepts digit-only public facility numbers, ignores
  duplicate, blank, comment, and header values, and rejects invalid values before
  public report discovery begins.
- Live fetch summaries distinguish no-record, skipped-by-limit, discovery
  failure, report failure, and written-record run states. These are workflow
  states in the derived dataset, not conclusions about the public source.
- Live fetched raw report files are saved under the local ignored `data/raw/ccld` path by default. Treat public narrative content carefully when sharing exports or raw files.
- Live fetched records reflect the public response at retrieval time. Public reports may later change, be corrected, become unavailable, or use layouts the current extractor does not fully understand.
- The local hosted scaffold `/facilities` pages are read-only fixture/sample
  pages backed only by committed tiny public-source facility fixtures and
  manifest placeholder metadata. Source coverage panels and related
  source-record links on those pages are fixture/sample display patterns only.
  They do not load live public-source data, read ignored raw CSVs or generated
  profiling outputs, use SQLite or a hosted database through API routes,
  perform real provider login, persist reviewer-created state, or prove statewide
  coverage, source completeness, official facility status, or legal or
  facility-wide conclusions.
- The hosted seeded corpus import path is controlled and local/test-oriented.
  It stages source-derived records from a validated JSON artifact into the
  PostgreSQL/Alembic import batch and source-derived table group only. A narrow
  local/test read service can list and fetch those staged records with import
  batch context and source traceability, and local/test auth guards can protect
  those service reads by actor role, account status, and scope. A narrow
  local/test HTTP/API route seam can serialize those authenticated
  source-derived reads when tests provide an explicit route context, and a
  narrow local/test read-only reviewer workflow shell can return queue and
  detail payloads over that route seam when tests provide an explicit workflow
  context. The path does not run live crawling, execute connectors, automate
  production imports, implement reset/reload, authenticate browser users,
  validate real provider tokens, create reviewer-created state, expose stateful
  database-backed reviewer views or production API framework behavior, or prove
  source completeness.
- Datasette accessibility depends partly on the installed Datasette version, browser, and assistive technology. Validate keyboard navigation, table headers, focus visibility, and exported table usability before treating a release as stable.
