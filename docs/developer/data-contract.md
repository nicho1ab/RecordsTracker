# Developer Data Contract Guide

The root `DATA_CONTRACT.md` is authoritative.

## Schema changes

Any schema change must update:

- `DATA_CONTRACT.md`
- `schemas/*.schema.json`
- Database migration or initialization SQL
- `docs/user/data-dictionary.md`
- Tests and fixtures

## Null handling

Use database nulls for unknown values. Do not use empty strings to represent unknown extracted data.
