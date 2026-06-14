# Migration Versions

This directory contains the hosted tester domain migrations for controlled
seeded corpus import tables and the first narrow reviewer-created state
persistence scaffold table.

Add future revisions here only in focused schema branches that create tested
PostgreSQL table groups for approved hosted tester MVP layers while preserving
source-derived and reviewer-created state separation. The reviewer-created
state scaffold revision must remain narrow: it links to staged source-derived
records and requires authenticated actor attribution, but it does not implement
full review workflows, annotations, corrections, audit persistence, export
state, feedback, or reset/reload execution.