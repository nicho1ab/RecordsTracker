# Hosted Tester Migrations

This directory is the Alembic script location for hosted tester MVP PostgreSQL
migrations.

The first domain migration creates only the controlled seeded corpus import
table group: import batch metadata and generic source-derived record staging.
The second domain migration creates one narrow reviewer-created state scaffold
table linked to staged source-derived records. It proves the persistence
boundary for authenticated local/test reviewer-created state without adding full
reviewer workflows, annotations, corrections, auth tables, audit tables, export
tables, feedback tables, reset/reload tables, API routes, live crawling, hosted
connector execution, deployment behavior, or production automation.

Future schema branches must add reviewed migration files with focused tests for
the implemented table groups and must preserve the ADR-0010 and ADR-0015
separation between source-derived records and reviewer-created state.