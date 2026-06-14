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
  manifest placeholder metadata. They do not load live public-source data, read
  ignored raw CSVs or generated profiling outputs, use SQLite or a hosted
  database, run import/sync, authenticate users, persist reviewer-created state,
  or prove statewide coverage, source completeness, official facility status,
  or legal or facility-wide conclusions.
- Datasette accessibility depends partly on the installed Datasette version, browser, and assistive technology. Validate keyboard navigation, table headers, focus visibility, and exported table usability before treating a release as stable.
