# Migration Versions

This directory contains the hosted tester domain migrations for controlled
seeded corpus import tables, the first narrow reviewer-created state persistence
scaffold table, the first narrow audit event scaffold table, and the first
narrow reset/reload operational planning metadata scaffold table. Later
revisions add controlled CCLD retrieval jobs, a separate facility-reference
preload table, nullable source-reference allocation columns, and four nullable
historical complaint-observation columns.

Add future revisions here only in focused schema branches that create tested
PostgreSQL table groups for approved hosted tester MVP layers while preserving
source-derived and reviewer-created state separation. The reviewer-created
state scaffold revision must remain narrow: it links to staged source-derived
records and requires authenticated actor attribution. The audit event scaffold
revision must also remain narrow: it records successful reviewer-created state
scaffold writes only, separately from source-derived and reviewer-created rows.
The reset/reload operational metadata revision must remain narrow: it stores
explicitly requested dry-run planning records only, separately from source-
derived, reviewer-created, and audit rows.
The facility-reference revisions must remain source-reference-only and additive;
they must not convert visit-date arrays into complaint events or silently merge
reference rows into canonical facilities.
Revision `20260720_0008` adds a separate offline source-specific snapshot
lifecycle table group for Issue #518. It preserves immutable synthetic fixture
metadata and rows, disappearance evidence, and one active/prior pointer per
source family. It neither backfills the existing facility-reference table nor
creates a live connector, production activation, canonical allocation, or
reviewer-created-state write path.
Revision `20260720_0009` extends only the existing snapshot scope and observation
constraints for `governed_live_query`/`live_query` candidates. It adds no table,
canonical bridge, reviewer write, production command, scheduler, or deployment
behavior. Downgrade refuses to discard the live-scope contract while retained
live-query snapshot history exists.
Revision `20260723_0013` additively allocates only complaint-report agency,
ordered deficiency texts, bounded investigation narrative, and historical
complaint-report contact to existing source-derived complaint rows. Existing
rows remain null until bounded preserved-artifact replay or validated reimport.
The revision does not allocate complaint-report address or city, overwrite
current facility-reference values, or change reviewer-created state.
These revisions do not implement full review workflows, annotations,
corrections, full audit policy coverage, audit UI, audit export, export state,
feedback, retention automation, destructive reset, reload execution, archive
execution, clear execution, relinking, or connector execution.
