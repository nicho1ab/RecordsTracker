# Migration Versions

This directory contains the hosted tester domain migrations for controlled
seeded corpus import tables, the first narrow reviewer-created state persistence
scaffold table, the first narrow audit event scaffold table, and the first
narrow reset/reload operational planning metadata scaffold table. Later
revisions add controlled CCLD retrieval jobs, a separate facility-reference
preload table, and nullable issue #447 source-reference allocation columns.

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
These revisions do not implement full review workflows, annotations,
corrections, full audit policy coverage, audit UI, audit export, export state,
feedback, retention automation, destructive reset, reload execution, archive
execution, clear execution, relinking, or connector execution.
