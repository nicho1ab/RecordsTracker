# ADR-0001: Use Python + SQLite + Datasette for the Initial POC

## Status

Accepted

## Context

The project needs to prove that public complaint records can be extracted, normalized, tested, and presented quickly without building a custom application or adding unnecessary platform complexity.

## Decision

The initial build will use Python, SQLite, and Datasette. Raw source files will be retained in ordinary file storage. Paperless-ngx will not be included in the initial architecture unless a dedicated document-management requirement emerges.

## Reason

The project's primary value is structured extraction, analysis, and repeatable ingestion. A lightweight database and browser UI avoid unnecessary document-management complexity while preserving a path to scale.

## Consequences

- Lower startup complexity.
- Easier fixture-based regression testing.
- Easy local development on Windows and VS Code.
- Future migration to PostgreSQL/Baserow/Metabase remains possible.
