# Known Limitations

- The public portal remains the public source of record.
- Extracted data is a derived dataset and may contain extraction errors.
- Public source reports may be incomplete, corrected later, or removed.
- Report date may not equal first investigation activity date.
- Narrative dates may require separate extraction and confidence scoring.
- Some older reports may have different layouts or missing fields.
- Single-facility CCLD ingestion currently returns structured records in memory and does not persist them to SQLite yet.
- Fixture-backed ingestion only extracts discovered reports when matching raw report content is supplied by the test loader.
- Accessibility of third-party presentation layers must be validated before release.
- GitHub Actions availability and limits may depend on project policy and platform usage limits.
