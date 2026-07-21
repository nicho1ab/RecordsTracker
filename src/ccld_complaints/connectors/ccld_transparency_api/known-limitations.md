# Known limitations

- Issue #554 establishes connector and immutable snapshot infrastructure only. It does
  not activate the source in reviewer reads, change precedence, backfill canonical rows,
  schedule refreshes, or deploy the connector.
- Facility Number is unique only within one validated current source family. It is not a
  permanent facility identity and may be reused after ownership, relocation, or
  relicensing changes.
- Source disappearance is retained for reconciliation and never proves closure or
  deletion.
- Current bulk/detail observations remain distinct from complaint/report-time values.
- Address and telephone non-overwrite resolution applies only to blank, omitted, or
  governed placeholder observations. Conflicting populated values are retained for later
  governed reconciliation.
- The connector preserves safe response metadata but deliberately excludes cookies,
  authentication headers, and other unapproved header values.
- A prior accepted taxonomy or county artifact is not automatically substituted. Such a
  fallback requires an explicit later policy even though Issue #554 permits one.
- Source-owner authorization evidence remains outside Git. Repository documentation
  records the approved implementation boundary but not private correspondence.
