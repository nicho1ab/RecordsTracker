# Stakeholder Facility Overview Extract

This extract is a review aid derived from locally loaded public CCLD complaint
records. It is not a certified report, legal finding, or source-completeness
proof.

## What this extract is

A summary of facility-level complaint counts and key fields drawn from records
that were loaded into the local SQLite database from publicly available CCLD
complaint report data.

## What this extract is not

- It does not make legal conclusions.
- It does not make facility-wide conclusions about a facility's conduct, safety,
  or compliance.
- It does not claim to be source-complete. Zero or low counts do not prove that
  no complaints exist; they reflect only what was loaded.
- It does not independently verify any finding or allegation. Finding/resolution
  values are source-derived values extracted from publicly available reports.
- It does not include verified severity determinations, risk scores, or rankings.
- It does not include raw narrative allegation text.

## Source of record

The public CCLD portal (ccld.dss.ca.gov) remains the source of record.
Verify important details against the public source before citing this extract.

## Counts and coverage

Counts are based only on currently loaded records. A facility may have additional
complaint records in the public source that were not retrieved or loaded.

## Finding/resolution values

Finding/resolution values such as "Substantiated", "Founded", or "Sustained" are
extracted from publicly available CCLD complaint investigation reports and are
not independently verified by RecordsTracker. Do not restate them as independently
verified findings.

## Limitations column

Each row in facility-overview.csv, substantiated-complaints.csv, and
complaint-records.csv includes a Limitations column repeating this scope note
for use when rows are shared or excerpted outside this package.

## complaint-records.csv

This file contains one row per loaded complaint record for all facilities in
this extract, regardless of finding/resolution status.

- **FindingGroup** classifies each record into SubstantiatedOrEquivalent,
  NotSubstantiatedOrEquivalent, or UnknownOrMissing based on the source-derived
  finding value. This is not an independent legal determination.
- **ComplaintType** is a source-derived document type field when available;
  otherwise "not available".
- **AllegationCategory** is a source-derived category label when extracted;
  otherwise "not available". Raw narrative allegation text is not included.
- **KeywordReviewCues** is a deterministic keyword-based review-cue label
  derived from source-extracted non-narrative fields (finding, allegation
  category). A match signals a possible serious allegation topic as a review
  aid only. It is not a severity score, not a risk score, not a verified
  finding, and not a legal classification. A non-match does not confirm the
  absence of serious topics.
- Counts reflect only loaded records. Additional complaint records may exist
  in the public source that were not retrieved or loaded.
