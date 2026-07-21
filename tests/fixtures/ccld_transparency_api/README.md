# CCLD TransparencyAPI connector fixtures

These fictional, source-shaped fixtures exercise the governed facility-reference connector
without making network requests or containing real facility/contact data.

- `facility-detail-sentinel.json` proves that HTTP 200 is insufficient when the response is
  the official not-found sentinel.
- `facility-reports-list.json` contains ordered report metadata and an intentionally unusable
  `fakeout.gov` `REPORTPAGE` value. The connector preserves but never follows that value.
- `facility-report-valid.html` is a minimal helper response for list/helper reconciliation.

Bulk CSV fixtures are constructed in tests from the exact versioned header tuples so all seven
export identities, quoted commas, variable complaint blocks, leading zeros, and malformed tails
remain compact and deterministic.
