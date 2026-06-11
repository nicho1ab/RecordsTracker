# CCLD Connector Known Limitations

- Report layouts may vary by report type or year.
- The report date may not equal the first investigation activity date.
- Delay review flags are screening aids and do not prove that an investigation was delayed.
- Report date is used as a delay review proxy only when no first investigation activity date or visit date is available.
- Some reports may include narrative dates that need separate event extraction.
- The public portal may change without notice.
- Single-facility ingestion returns validated in-memory records and recorded failures, and can persist normalized records to SQLite when configured with a database path.
- Offline fixture ingestion only extracts reports whose raw fixture content is supplied by the injected loader.
