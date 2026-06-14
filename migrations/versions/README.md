# Migration Versions

This directory contains the hosted tester domain migrations for controlled
seeded corpus import tables, the first narrow reviewer-created state persistence
scaffold table, and the first narrow audit event scaffold table.

Add future revisions here only in focused schema branches that create tested
PostgreSQL table groups for approved hosted tester MVP layers while preserving
source-derived and reviewer-created state separation. The reviewer-created
state scaffold revision must remain narrow: it links to staged source-derived
records and requires authenticated actor attribution. The audit event scaffold
revision must also remain narrow: it records successful reviewer-created state
scaffold writes only, separately from source-derived and reviewer-created rows.
These revisions do not implement full review workflows, annotations,
corrections, full audit policy coverage, audit UI, audit export, export state,
feedback, retention automation, or reset/reload execution.