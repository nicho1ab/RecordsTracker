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
- Datasette accessibility depends partly on the installed Datasette version, browser, and assistive technology. Validate keyboard navigation, table headers, focus visibility, and exported table usability before treating a release as stable.
