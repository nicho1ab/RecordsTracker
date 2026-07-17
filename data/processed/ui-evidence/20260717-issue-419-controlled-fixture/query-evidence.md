# Bounded query evidence

`query-and-adjacent-page-regressions.xml` records five passing focused
regressions:

- `test_facility_intelligence_continuations_preserve_filters_and_reject_bad_state`;
- `test_facility_intelligence_rejects_modified_position_and_anchor`;
- `test_facility_intelligence_forward_and_backward_ranges_use_anchor_rank`;
- `test_facility_intelligence_seek_pages_have_no_duplicates_or_omissions`;
- `test_facility_intelligence_reads_only_current_page_and_uses_bounded_sql`.

For continuation requests, the same authorized, import-scoped, filtered,
deduplicated `facility_intelligence_facilities` relation is used for:

- a bounded `LIMIT 1` exact-anchor existence query;
- a scalar count-before-anchor query shaped as
  `SELECT count(*) FROM facility_intelligence_facilities WHERE <rows before anchor>`;
- the bounded `LIMIT 25` keyset page query.

The calculated 1-based anchor rank is authoritative. The requested destination
position is derived from that rank and direction, then compared with the token's
retained position claim. The regressions prove safe rejection when only that
claim changes, when the anchor changes to another existing facility at a
different rank, when the anchor does not exist, when the total is stale, and
when filters or ordering differ. Legitimate forward and backward links retain
the exact `Showing X–Y of Z facilities` ranges.

The SQL regression captures every statement issued for a second-page read of a
51-facility corpus and proves:

- the current page contains exactly 25 facility identities;
- hydration contains only 75 rows for those 25 one-complaint facilities
  (facility, source document, and complaint rows);
- reviewer-created-state lookup receives exactly 25 source-record keys;
- the previous unbounded entity-type corpus reader is not called;
- no captured statement contains `OFFSET`;
- a scalar count-before-anchor query is issued against
  `facility_intelligence_facilities`;
- the current page uses a lexicographic keyset predicate;
- the facility page is bounded by `LIMIT 25`;
- the governed full-filtered-corpus Review next select orders the facilities
  by the priority tuple and is bounded by `LIMIT 1`.

The adjacent-page regression reconciles all 51 stable facility identities over
three continuation links and proves no duplicates and no omissions.
