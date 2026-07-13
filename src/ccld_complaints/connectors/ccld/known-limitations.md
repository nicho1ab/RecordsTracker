# CCLD Connector Known Limitations

- Report layouts may vary by report type or year.
- The report date may not equal the first investigation activity date.
- Delay review flags are screening aids and do not prove that an investigation was delayed.
- Report date is used as a delay review proxy only when no first investigation activity date or visit date is available.
- Narrative event extraction is limited to governed investigation-findings
  wording with deterministic activity cues and parseable numeric dates. Other
  wording remains unavailable rather than inferred.
- Complaint-report facility address and city elements may be present but blank.
  They are distinguished from unavailable coverage in extraction audit evidence
  but do not yet have canonical storage allocation.
- Existing PostgreSQL rows keep the source-derived values produced at import
  time. Extractor improvements require artifact regeneration and reimport; no
  safe automated in-place refresh command is currently implemented.
- The public portal may change without notice.
- Single-facility ingestion returns validated in-memory records and recorded failures, and can persist normalized records to SQLite when configured with a database path.
- Offline fixture ingestion only extracts reports whose raw fixture content is supplied by the injected loader.
- Live fetching is explicitly user-invoked, currently focused on the single POC facility workflow, and depends on the public portal being available at run time.
- Live fetched raw report files are local by default under `data/raw/ccld`; public narrative content should be handled carefully when sharing outputs.
