# Project Charter

## Project name

CCLD Complaints Data POC

## Problem statement

Public complaint and inspection records are available through the CCLD public portal, but the portal is not optimized for structured analysis, bulk review, comparison, delay analysis, or repeatable research workflows.

## Primary goal

Create a proof of concept that ingests public facility reports, stores raw source evidence, extracts structured complaint fields, validates data quality, and presents searchable records without building a custom web application.

## Initial source

California Community Care Licensing Division public facility/report portal.

Initial facility:

- Facility: A. Miriam Jamison Children's Center
- Facility number: 157806098

## Target users

- Researchers and analysts reviewing facility complaint history
- Advocates reviewing public licensing data
- Developers maintaining source connectors and extraction logic
- Non-technical users browsing extracted records

## Success criteria

- Raw public source reports can be downloaded or reproducibly retrieved.
- Structured complaint fields can be extracted into SQLite.
- Each structured record links back to source URL and raw file hash.
- Fixture-based regression tests prevent previously working extraction from breaking.
- Documentation is generated and maintained for developer and end-user audiences.
- The presentation layer meets ADA digital accessibility requirements.
- The project can add future source connectors without rewriting the architecture.

## Non-goals

- Do not create a custom web application during the POC.
- Do not rely on paid GitHub features that are not available in the user's University of Illinois GitHub Enterprise account or organization.
- Do not treat portal data as complete, authoritative, or guaranteed accurate.
- Do not use LLM extraction where deterministic parsing is reliable.
- Do not include Paperless-ngx in the initial architecture unless a document-management requirement emerges.
