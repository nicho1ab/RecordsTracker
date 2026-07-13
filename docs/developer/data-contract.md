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

Issue #447 also requires incoming null optional facility values not to erase an
already populated value for the same stable facility identity. Explicit numeric
zero remains distinct from null.

## Facility-reference-only allocations

The root contract's issue #447 matrix is authoritative for visit-date arrays,
`CLIENT_SERVED`, the unflattened complaint-information composite, and
`closed_date`. These values stay in the facility-reference domain and must not
be silently promoted into canonical facility or complaint entities. Issue #448
adds deterministic cross-store parity evidence for equivalent canonical inputs
and separately reconciles facility-reference parser/preload results; it does not
create a canonical bridge from facility-reference rows.
