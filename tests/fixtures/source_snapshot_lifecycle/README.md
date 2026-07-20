# Offline ArcGIS snapshot lifecycle fixtures

These tiny fixtures are wholly fictional and exist only to exercise Issue #518's
offline source-specific snapshot lifecycle. They are not copies of public
facility records, do not identify a network endpoint, and do not authorize a
live connector or ArcGIS activation.

Each manifest points only to a sibling raw JSON payload and records the SHA-256
of its Git-normalized bytes. Snapshot A and B are valid synthetic observations;
the rejected fixture intentionally contains schema/domain and row defects.

The fictional values follow the exact ArcGIS field types observed from the
approved live layer on 2026-07-20, including string coordinates, integer
`FAC_NBR`/`CLIENT_SERVED`/`FAC_CO_NBR`, and double `FAC_PHONE_NBR`. This corrects
the earlier synthetic type assumptions without copying a live facility row.
