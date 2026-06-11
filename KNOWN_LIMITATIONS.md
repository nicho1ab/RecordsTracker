# Known Limitations

- The public portal remains the public source of record.
- Extracted data is a derived dataset and may contain extraction errors.
- Public source reports may be incomplete, corrected later, or removed.
- Report date may not equal first investigation activity date.
- Delay review flags are screening aids and do not prove that an investigation was delayed.
- Report date may be used as a review proxy only when no first investigation activity date or visit date is available; report date alone does not establish when investigation activity began.
- Narrative dates may require separate extraction and confidence scoring.
- Some older reports may have different layouts or missing fields.
- Single-facility CCLD ingestion can persist normalized records to SQLite when configured with a database path; a dedicated end-user ingestion command is not yet available.
- Fixture-backed ingestion only extracts discovered reports when matching raw report content is supplied by the test loader.
- Accessibility of third-party presentation layers must be validated before release.
- GitHub Actions availability and limits may depend on project policy and platform usage limits.
