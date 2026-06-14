# Hosted Tester Migrations

This directory is the Alembic script location for future hosted tester MVP
PostgreSQL migrations.

The scaffold intentionally does not include domain migration versions yet. The
next schema branch must add reviewed migration files with focused tests for the
implemented table groups and must preserve the ADR-0010 and ADR-0015 separation
between source-derived records and reviewer-created state.