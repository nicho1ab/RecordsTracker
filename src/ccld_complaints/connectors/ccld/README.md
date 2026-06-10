# CCLD Connector

This connector is responsible for discovering, fetching, storing, extracting, and normalizing public CCLD facility report data.

The first implementation should focus on FacilityReports URLs in this format:

```text
https://www.ccld.dss.ca.gov/transparencyapi/api/FacilityReports?facNum=<facility_number>&inx=<index>
```

The connector must follow `SOURCE_CONNECTOR_CONTRACT.md`.
