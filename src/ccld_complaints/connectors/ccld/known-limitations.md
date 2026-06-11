# CCLD Connector Known Limitations

- Report layouts may vary by report type or year.
- The report date may not equal the first investigation activity date.
- Delay review flags are screening aids and do not prove that an investigation was delayed.
- Report date is used as a delay review proxy only when no first investigation activity date or visit date is available.
- Some reports may include narrative dates that need separate event extraction.
- The public portal may change without notice.
- Single-facility ingestion returns validated in-memory records and recorded failures, and can persist normalized records to SQLite when configured with a database path.
- Offline fixture ingestion only extracts reports whose raw fixture content is supplied by the injected loader.
- Live fetching is explicitly user-invoked, currently focused on the single POC facility workflow, and depends on the public portal being available at run time.
- Live fetched raw report files are local by default under `data/raw/ccld`; public narrative content should be handled carefully when sharing outputs.
