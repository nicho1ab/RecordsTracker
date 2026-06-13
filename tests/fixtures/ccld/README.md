# CCLD Fixtures

Add raw CCLD source files under `raw/` and expected extracted JSON under `expected/`.

Every extraction change should add or update fixtures.

Raw fixtures and expected JSON are governed by `.gitattributes` line-ending rules. When an expected JSON file includes a raw SHA-256 hash, the hash must match the Git-normalized fixture bytes that CI reads, not a local working-tree copy with platform-specific line endings. Verify line endings with `git ls-files --eol` when adding or changing raw fixtures.

## Current fixtures

- `raw/157806098_facility_detail.html`: Public CCLD facility detail page fixture for facility `157806098`, including rendered FacilityReports links used for offline discovery regression tests.
- `raw/157806098_inx3.html`: Public CCLD FacilityReports response for facility `157806098`, report index `3`.
- `expected/157806098_inx3.json`: Expected normalized records for the first deterministic CCLD extraction regression test.
- `raw/157806098_inx40_numbered_allegations.html`: Source-shaped CCLD report fixture covering allegation rows where the numeric marker and allegation text appear on the same line.
- `expected/157806098_inx40_numbered_allegations.json`: Expected normalized records for numbered-allegation extraction hardening.
- `raw/157806098_inx41_inline_received_date.html`: Source-shaped CCLD report fixture covering complaint received dates that appear inline in the narrative sentence.
- `expected/157806098_inx41_inline_received_date.json`: Expected normalized records for inline complaint received date extraction hardening.
- `raw/157806098_inx42_missing_visit_date.html`: Source-shaped CCLD report fixture covering missing visit date extraction and report-date proxy delay review flags.
- `expected/157806098_inx42_missing_visit_date.json`: Expected normalized records for missing visit date extraction hardening.
- `raw/157806098_inx43_labeled_finding.html`: Source-shaped CCLD report fixture covering finding values provided through an explicit `Finding:` label.
- `expected/157806098_inx43_labeled_finding.json`: Expected normalized records for labeled finding extraction hardening.
- `raw/157806098_inx44_wrapped_allegation.html`: Source-shaped CCLD report fixture covering allegation text wrapped across adjacent lines.
- `expected/157806098_inx44_wrapped_allegation.json`: Expected normalized records for wrapped-allegation extraction hardening.
- `raw/157806098_inx45_split_finding.html`: Source-shaped CCLD report fixture covering a standalone `Finding` label followed by the normalized finding value on the next line.
- `expected/157806098_inx45_split_finding.json`: Expected normalized records for split finding label extraction hardening.
