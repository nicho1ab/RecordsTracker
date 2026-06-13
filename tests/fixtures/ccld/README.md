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
- `raw/157806098_inx46_allegations_heading.html`: Source-shaped CCLD report fixture covering an `ALLEGATIONS:` section heading variant.
- `expected/157806098_inx46_allegations_heading.json`: Expected normalized records for allegation heading variant extraction hardening.
- `raw/157806098_inx47_investigation_finding_heading.html`: Source-shaped CCLD report fixture covering an `INVESTIGATION FINDING:` section heading variant.
- `expected/157806098_inx47_investigation_finding_heading.json`: Expected normalized records for investigation finding heading variant extraction hardening.
- `raw/157806098_inx48_allegations_heading_no_colon.html`: Source-shaped CCLD report fixture covering an `ALLEGATIONS` section heading without a trailing colon.
- `expected/157806098_inx48_allegations_heading_no_colon.json`: Expected normalized records for no-colon allegation heading extraction hardening.
- `raw/157806098_inx49_punctuated_finding.html`: Source-shaped CCLD report fixture covering a normalized finding value with trailing punctuation.
- `expected/157806098_inx49_punctuated_finding.json`: Expected normalized records for punctuated finding extraction hardening.
- `raw/157806098_inx50_dashed_finding_label.html`: Source-shaped CCLD report fixture covering a `Finding -` inline label/value layout.
- `expected/157806098_inx50_dashed_finding_label.json`: Expected normalized records for dashed finding label extraction hardening.
- `raw/157806098_inx51_was_received_date.html`: Source-shaped CCLD report fixture covering a `complaint was received in our office on` narrative date phrase.
- `expected/157806098_inx51_was_received_date.json`: Expected normalized records for was-received complaint date extraction hardening.
- `raw/157806098_inx52_split_report_date.html`: Source-shaped CCLD report fixture covering a standalone `Report Date` label followed by the date value.
- `expected/157806098_inx52_split_report_date.json`: Expected normalized records for split report date label extraction hardening.
- `raw/157806098_inx53_split_date_signed.html`: Source-shaped CCLD report fixture covering a standalone `Date Signed` label followed by the signed date value.
- `expected/157806098_inx53_split_date_signed.json`: Expected normalized records for split date signed label extraction hardening.
- `raw/157806098_inx54_split_visit_date.html`: Source-shaped CCLD report fixture covering a standalone `VISIT DATE` label followed by the visit date value.
- `expected/157806098_inx54_split_visit_date.json`: Expected normalized records for split visit date label extraction hardening.
- `raw/157806098_inx55_split_complaint_control.html`: Source-shaped CCLD report fixture covering a standalone `COMPLAINT CONTROL NUMBER` label followed by the complaint control number value.
- `expected/157806098_inx55_split_complaint_control.json`: Expected normalized records for split complaint control number label extraction hardening.
- `raw/157806098_inx56_split_facility_name.html`: Source-shaped CCLD report fixture covering a standalone `FACILITY NAME` label followed by the facility name value.
- `expected/157806098_inx56_split_facility_name.json`: Expected normalized records for split facility name label extraction hardening.
- `raw/157806098_inx57_split_facility_number.html`: Source-shaped CCLD report fixture covering a standalone `FACILITY NUMBER` label followed by the facility number value.
- `expected/157806098_inx57_split_facility_number.json`: Expected normalized records for split facility number label extraction hardening.
- `raw/157806098_inx58_report_type_case.html`: Source-shaped CCLD report fixture covering a title-case complaint investigation report type heading.
- `expected/157806098_inx58_report_type_case.json`: Expected normalized records for report type case hardening.
- `raw/157806098_inx59_spaced_allegation_heading.html`: Source-shaped CCLD report fixture covering an `ALLEGATION (S):` section heading variant.
- `expected/157806098_inx59_spaced_allegation_heading.json`: Expected normalized records for spaced allegation heading extraction hardening.
- `raw/157806098_inx60_findings_heading_no_colon.html`: Source-shaped CCLD report fixture covering an `INVESTIGATION FINDINGS` section heading without a trailing colon.
- `expected/157806098_inx60_findings_heading_no_colon.json`: Expected normalized records for no-colon investigation findings heading extraction hardening.
- `raw/157806098_inx61_received_date_punctuation.html`: Source-shaped CCLD report fixture covering a complaint received date after punctuation in the narrative received-date phrase.
- `expected/157806098_inx61_received_date_punctuation.json`: Expected normalized records for punctuated complaint received date phrase extraction hardening.
- `raw/157806098_inx62_report_type_punctuation.html`: Source-shaped CCLD report fixture covering a complaint investigation report type heading with trailing punctuation.
- `expected/157806098_inx62_report_type_punctuation.json`: Expected normalized records for punctuated report type heading extraction hardening.
- `raw/157806098_inx63_findings_heading_dash.html`: Source-shaped CCLD report fixture covering an `INVESTIGATION FINDINGS -` section heading variant.
- `expected/157806098_inx63_findings_heading_dash.json`: Expected normalized records for dashed investigation findings heading extraction hardening.
- `raw/157806098_inx64_allegation_heading_dash.html`: Source-shaped CCLD report fixture covering an `ALLEGATION(S) -` section heading variant.
- `expected/157806098_inx64_allegation_heading_dash.json`: Expected normalized records for dashed allegation heading extraction hardening.
- `raw/157806098_inx65_report_date_spaced_colon.html`: Source-shaped CCLD report fixture covering a `Report Date :` spaced-colon label variant.
- `expected/157806098_inx65_report_date_spaced_colon.json`: Expected normalized records for spaced-colon report date label extraction hardening.
- `raw/157806098_inx66_date_signed_spaced_colon.html`: Source-shaped CCLD report fixture covering a `Date Signed :` spaced-colon label variant.
- `expected/157806098_inx66_date_signed_spaced_colon.json`: Expected normalized records for spaced-colon date signed label extraction hardening.
- `raw/157806098_inx67_visit_date_spaced_colon.html`: Source-shaped CCLD report fixture covering a `VISIT DATE :` spaced-colon label variant.
- `expected/157806098_inx67_visit_date_spaced_colon.json`: Expected normalized records for spaced-colon visit date label extraction hardening.
