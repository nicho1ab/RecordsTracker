# Source-to-screen coverage fixtures

`scenarios.json` is a tiny synthetic bundle for contract `1.1.0`. The `base`
object supplies safe aggregate and operator-index metadata; each named scenario
is a deterministic merge override. It contains no source body, narrative, source
URL, private path, credential, authentication claim, or production import row.

The scenarios are:

- `complete-balanced`
- `empty-verified`
- `partial-unavailable-stage`
- `failed-reconciliation`
- `version-mismatch`
- `hash-validation-failure`
- `interrupted-job-previous-accepted-active`
- `raw-733-unresolved`
- `pagination-adjacent-pages`
- `prohibited-content-rejected`
- `transparencyapi-source-unavailable`
- `transparencyapi-read-but-not-rendered`
- `transparencyapi-stage-imbalanced`
- `transparencyapi-reviewed-exception`

The version-mismatch and prohibited-content scenarios are negative producer
fixtures. Hash-failure validation is completed by generating the safe
hash-failure operational state and then corrupting a copied package artifact in
the unit test. Facility IDs are synthetic and exist only to exercise the
operator-only row contract and deterministic ordering.

The TransparencyAPI profiles contain aggregate-only fictional counts. They
exercise explicit unavailable states, rendering and stage-balance failures, and
the existing reviewed-exception path without adding record-level source values.
