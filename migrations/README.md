# Hosted Tester Migrations

This directory is the Alembic script location for hosted tester MVP PostgreSQL
migrations.

The first domain migration creates the controlled seeded corpus import table
group: import batch metadata and generic source-derived record staging. Later
domain migrations add separate reviewer-created state, audit event, reset/reload
planning metadata, controlled CCLD retrieval job metadata, and a dedicated
facility-reference preload table. The issue #447 revision adds only nullable
source-reference columns for three visit-date arrays and client-served context;
it does not backfill or rewrite existing rows. Those migrations preserve
separated operational metadata and do not add full
reviewer workflows, annotations, corrections, auth tables, export tables,
feedback tables, public deployment behavior, non-CCLD sources, direct browser
crawling, statewide crawling, or production automation.

Future schema branches must add reviewed migration files with focused tests for
the implemented table groups and must preserve the ADR-0010 and ADR-0015
separation between source-derived records and reviewer-created state.
