## Summary
- Adds a Reviewer Detail Attorney Workspace blueprint for the target reviewer detail route.
- Defines page purpose, above-the-fold content, actions, visible/collapsed sections, source/raw data handling, diagnostics handling, glossary support, accessibility expectations, visual acceptance criteria, and implementation boundaries.
- Keeps this branch planning-only; it does not implement reviewer detail UI changes.

## Attorney workflow impact
- Establishes the approved product structure needed to turn Reviewer Detail into a true attorney complaint review workspace.
- Keeps source traceability available while preventing the default page from remaining a raw source-data dump.
- Defines how the future implementation should help attorneys understand the complaint, why it matters, what to check next, and how reviewer-created state remains separate from source-derived facts.

## Operator/runtime preservation
- No deployment, QNAP, Docker, Compose, Cloudflare, route, retrieval, auth, schema, migration, export, feedback, or runtime behavior changes.

## Validation
- [x] .\scripts\docs.ps1
- [x] git diff --cached --check

## Boundaries
- Planning/blueprint only.
- No reviewer detail implementation.
- No new routes.
- No schema or migration changes.
- No retrieval, auth, feedback, export, packet, QNAP, Docker, Compose, or Cloudflare changes.
- Future implementation still requires screenshot review against this blueprint.
