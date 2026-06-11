# CCLD Connector Known Limitations

- Report layouts may vary by report type or year.
- The report date may not equal the first investigation activity date.
- Some reports may include narrative dates that need separate event extraction.
- The public portal may change without notice.
- Single-facility ingestion currently returns validated in-memory records and recorded failures; it does not persist records to SQLite yet.
- Offline fixture ingestion only extracts reports whose raw fixture content is supplied by the injected loader.
