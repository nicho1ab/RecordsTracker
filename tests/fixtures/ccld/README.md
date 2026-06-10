# CCLD Fixtures

Add raw CCLD source files under `raw/` and expected extracted JSON under `expected/`.

Every extraction change should add or update fixtures.

## Current fixtures

- `raw/157806098_facility_detail.html`: Public CCLD facility detail page fixture for facility `157806098`, including rendered FacilityReports links used for offline discovery regression tests.
- `raw/157806098_inx3.html`: Public CCLD FacilityReports response for facility `157806098`, report index `3`.
- `expected/157806098_inx3.json`: Expected normalized records for the first deterministic CCLD extraction regression test.
