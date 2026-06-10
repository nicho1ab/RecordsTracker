# ADR-0002: Store Raw Source Files in Ordinary File Storage

## Status

Accepted

## Context

The public source portal should remain available, but extraction testing and reproducibility require stable local fixtures and raw source snapshots.

## Decision

The project will store raw source files in `data/raw/` using stable paths and SHA-256 hashes. Structured records will retain source URL, raw path, raw hash, and retrieval timestamp.

## Reason

This preserves traceability without introducing a document-management system during the POC.

## Consequences

- Raw files can become regression fixtures.
- Reprocessing can be tested against known content.
- Storage must avoid sensitive or restricted data unless explicitly allowed.
