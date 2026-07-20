# Governed ArcGIS live-query connector fixtures

These bounded fixtures exercise Issue #518's fixed endpoint, identity, schema,
pagination, reconciliation, and immutable-evidence behavior without making a
network request. Facility rows are wholly fictional and are not copied from the
live California source. The metadata preserves only the approved public source
identifiers needed to test drift detection.

- `catalog.html` and `licenses.html` model nonempty official HTML responses.
- `item.json`, `service.json`, and `layer.json` model the approved ArcGIS
  identity and exact 19-field schema.
- `object-ids.json`, `page-00000.json`, and `page-terminal.json` model an exact
  two-row reconciliation plus the mandatory empty terminal page.

These fixtures do not authorize export, replicas, redirects, activation,
canonical allocation, reviewer display, scheduling, deployment, or production
database mutation.
