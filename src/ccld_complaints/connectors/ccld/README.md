# CCLD Connector

This connector is responsible for discovering, fetching, storing, extracting, and normalizing public CCLD facility report data.

The first implementation should focus on FacilityReports URLs in this format:

```text
https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=<facility_number>&inx=<index>
```

The connector must follow `SOURCE_CONNECTOR_CONTRACT.md`.

## Initial deterministic extraction

The first implemented fixture covers facility `157806098` with report index `3`.

The extractor reads the public FacilityReports HTML response, preserves the raw source file, and deterministically extracts labeled fields from the report text:

- Facility number and facility name
- Report type, report date, date signed, and visit date
- Complaint received date and complaint control number
- Allegation text
- Normalized finding
- Days from complaint received date to report date

The normalized output uses the canonical entities in `DATA_CONTRACT.md`; the CCLD facility number is stored as `external_facility_number` on the facility record.
