# Known Limitations

- The public portal remains the public source of record.
- Extracted data is a derived dataset and may contain extraction errors.
- Public source reports may be incomplete, corrected later, or removed.
- Report date may not equal first investigation activity date.
- Delay review flags are screening aids and do not prove that an investigation was delayed.
- Report date may be used as a review proxy only when no first investigation activity date or visit date is available; report date alone does not establish when investigation activity began.
- Narrative dates may require separate extraction and confidence scoring.
- Some older reports may have different layouts or missing fields.
- Live CCLD ingestion can persist normalized records to SQLite for one or more explicitly provided facility numbers when configured with a database path; it does not perform statewide crawling or automatic search expansion.
- Live facility identifier intake accepts digit-only public facility numbers,
  ignores duplicate, blank, comment, and header values, and rejects invalid
  values before public report discovery begins.
- Live fetch summaries distinguish no-record, skipped-by-limit, discovery
    failure, report failure, and written-record run states. These are workflow
    states in the derived dataset, not conclusions about the public source.
- Fixture-backed ingestion only extracts discovered reports when matching raw report content is supplied by the test loader.
- Live CCLD fetching is explicitly user-invoked through the local script and depends on the public site being available when the command runs.
- Live fetched raw report files are saved under the local ignored `data/raw/ccld` path by default and should be treated carefully because public narrative content may be sensitive.
- The local hosted scaffold `/source-records` list uses fixture/sample records
    and local sample filtering/search plus fixture/sample-only source
    traceability summary panels only. It does not load live public-source data,
    read from SQLite or a hosted database through API routes, authenticate
    users, persist reviewer-created state, deploy publicly, or prove source
    completeness.
- The hosted seeded corpus import path is controlled and local/test-oriented.
    It stages source-derived records from a validated JSON artifact into the
    PostgreSQL/Alembic import batch and source-derived table group only. A
    narrow local/test read service can list and fetch those staged records with
    import batch context and source traceability, and local/test auth guards can
    protect those service reads by actor role, account status, and scope. A
    narrow local/test HTTP/API route seam can serialize those authenticated
    source-derived reads when tests provide an explicit route context. The path
    does not run live crawling, execute connectors, automate production imports,
    implement reset/reload, authenticate browser users, validate real provider
    tokens, create reviewer-created state, expose database-backed reviewer
    views or production API framework behavior, or prove source completeness.
- The local hosted scaffold `/facilities` list and detail pages use committed
    tiny public-source facility fixtures and manifest placeholder metadata only.
    The facility detail source coverage panel and related source-record links
    are fixture/sample display patterns only.
    They do not read ignored raw CSVs, generated profiling outputs, SQLite, a
    hosted database, live public-source data, import output, authentication
    state, or reviewer-created state, and they do not prove source
    completeness, statewide coverage, official facility status, or legal or
    facility-wide conclusions.
- Accessibility of third-party presentation layers must be validated before release.
- GitHub Actions availability and limits may depend on project policy and platform usage limits.
