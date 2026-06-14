# ADR-0011: Define Hosted Tester MVP Authentication and Access Boundaries

## Status

Accepted

## Context

ADR-0007 recommends a hybrid hosted tester MVP direction: preserve the Python
ingestion and extraction pipeline, retain SQLite and Datasette for validation
and transition comparison, and introduce a hosted reviewer application/API
boundary with a hosted relational reviewer-state store.

ADR-0008 separates source-derived data from reviewer-created state.
Source-derived records preserve public-source-derived values, raw source
traceability, extraction audit context, and data-contract discipline.
Reviewer-created state includes review statuses, annotations, proposed
corrections, correction decisions, tester feedback, export packet decisions,
and audit events.

ADR-0009 defines controlled snapshot import from validated pipeline output for
the tester MVP. ADR-0010 defines physical schema and migration boundaries for
future hosted work, including separated areas or table groups for imports,
source-derived records, reviewer-created state, audit events, exports,
feedback, and operational/reset metadata.

The hosted tester MVP needs authenticated tester access and role boundaries
before app scaffold or implementation work begins. Even though the underlying
source documents are public records, the hosted application will include
reviewer-created state, tester feedback, annotations, proposed corrections,
correction decisions, export packet decisions, audit history, and potentially
sensitive review context. That hosted context must not be exposed anonymously or
treated as official public-source content.

Current note: ADR-0012 later approved scaffold-first sequencing, and later local
implementation PRs added only the local scaffold, setup checks, read-only sample
source-record shell, and semantic/accessibility validation. This ADR still does
not approve authentication, authorization, user tables, role tables, invitation
flows, audit schema, hosted deployment, or anonymous hosted tester access.

This ADR defines the conceptual authentication, access-control, and tester-role
boundary only. It does not choose an authentication provider, implement access
control, define user tables, create role schemas, add authorization middleware,
scaffold an application, or change extraction, import, export, reset/reload, or
database behavior.

## Decision

The hosted tester MVP must require authenticated access.

Anonymous hosted tester access is not allowed.

Tester access must use explicitly provisioned or invited individual tester
accounts where feasible. Each hosted tester action that changes reviewer-created
state, feedback, exports, imports, reloads, resets, roles, or users should be
attributable to an individual account or approved process identity.

The hosted tester MVP must use simple role-based access boundaries. Roles define
what users may do conceptually, while the authentication provider,
authorization middleware, identity storage, session strategy, role/permission
schema, invitation flow, and implementation details are deferred.

Access must be scoped to a seeded corpus, review project, or test project. A
tester invitation does not imply access to all future data, all future review
projects, production environments, administrative functions, import/reload
operations, reset operations, or user/role administration.

## Minimum Roles

The hosted tester MVP must support at least these conceptual roles.

| Role | Conceptual permissions |
|---|---|
| Admin | May manage tester access, user and role assignments, project or corpus scope, and elevated review operations. May view facilities, complaints, source traceability, extraction audit context, reviewer-created state, tester feedback, export packets, and audit history for authorized tester projects. May grant or remove access, disable accounts, approve or perform elevated correction decisions where allowed, and approve destructive reset modes. Admin access does not make annotations, corrections, feedback, or export decisions official public-source facts. |
| Tester reviewer | May view facilities and complaints in assigned tester scope, view source traceability, view extraction audit context, update review statuses or queues where assigned, add annotations, add field-level notes, add source verification notes, propose corrections, submit tester feedback, and prepare export packets when granted export permission. May not manage users or roles, import/reload data, perform destructive reset, or access projects outside assigned scope. Correction decisions and export finalization require explicit permission and auditability. |
| Read-only tester | May view source-derived records, source traceability, extraction audit context, visible known limitations, and read-only review context within assigned tester scope. May view export packets if granted read access. May not add annotations, propose corrections, decide corrections, change statuses or queues, submit official tester feedback through reviewer-state workflows unless separately allowed, create or finalize exports, import/reload data, reset data, manage users or roles, or perform administrative actions. |
| Developer/operator | May perform operational tester-MVP tasks such as scripted import/reload, seeded corpus reload, reset operations, validation checks, troubleshooting, and audit review where authorized. May view source-derived records, import batch metadata, operational/reset metadata, and audit history needed to diagnose tester issues. May not use operational access to bypass reviewer-role boundaries, treat corrections as source facts, or silently delete reviewer-created state. User/role management remains admin-only unless explicitly combined with an admin role. |

Specific implementations may add more granular permissions later, but they must
preserve these minimum conceptual boundaries.

## Permission Boundaries

Future implementation must define and test permission categories for:

- Source-derived read permissions.
- Reviewer-state write permissions.
- Correction proposal permissions.
- Correction decision permissions.
- Export permissions.
- Feedback permissions.
- Import/reload permissions.
- Reset and destructive-operation permissions.
- User and role administration permissions.
- Audit-log read permissions.

Source-derived public records may be publicly sourced, but hosted access is
still controlled because the hosted app includes reviewer-created state, tester
feedback, annotations, proposed corrections, correction decisions, export
decisions, audit history, and possibly sensitive review context. Permission
labels, UI labels, exports, documentation, and tests must prevent users from
mistaking reviewer-created state for official public-source content.

## Tester Access Model

Tester access must follow these expectations:

- Testers must be explicitly invited or provisioned.
- Tester access should be scoped to a seeded corpus, review project, or test
  project.
- Tester access should not imply access to all future data, all future projects,
  production environments, or administrative operations.
- Tester actions should be auditable at the level approved for the tester MVP.
- Tester accounts should be removable or disableable.
- Tester access should be easy to revoke.
- Tester limitations should be visible in the UI and documentation.

The hosted tester MVP should prefer individual tester accounts over shared
accounts so annotations, proposed corrections, feedback, export actions, reset
requests, and review-state changes can be attributed where feasible.

## Access to Source-Derived Versus Reviewer-Created Data

Authorized testers may read source-derived data according to their project or
corpus scope. Source-derived read access should include the traceability needed
for safe review: source URL, raw hash, connector metadata, retrieval timestamp,
report context where available, raw path or artifact reference where available,
and extraction audit context where available.

Reviewer-created state must be permissioned more carefully than source-derived
read access. Annotations, field-level notes, source verification notes,
proposed corrections, correction decisions, feedback, export packets, export
packet items, and audit events are not public-source facts. They are hosted
review workflow state and must remain distinguishable from imported
source-derived values.

Role permissions must prevent users from confusing reviewer-created state with
official public-source content. A user who can read a source-derived complaint
does not automatically have permission to add annotations, propose corrections,
decide corrections, change review statuses, include records in export packets,
or view administrative audit history.

## Export Access

Export packet creation should require a role allowed to curate or export review
data. Export finalization or generated export delivery must be permissioned and
auditable.

Exports must preserve source traceability, including source URLs, raw hashes,
connector metadata, retrieval timestamps, report context where available, and
extraction audit context where relevant. Exports must include cautious
public-source language and distinguish source-derived fields from
reviewer-created notes, proposed corrections, correction decisions, feedback,
and export packet decisions.

Read-only testers may view export packets when granted read access, but they may
not create, modify, finalize, or generate exports unless a later ADR explicitly
approves that behavior.

## Import, Reload, and Reset Access

Import and reload operations should be admin/operator-only for the tester MVP.
They must use the controlled import boundary from ADR-0009 and the physical
separation principles from ADR-0010.

Destructive reset must require elevated permission. Reset/reload actions must be
auditable and must record who or what initiated the action where available, when
it occurred, which corpus or project was affected, which import batch or
artifact was used where applicable, what scope was reset, and whether
reviewer-created state was preserved or removed.

Reset/reload must not silently delete reviewer-created state unless an explicit
approved reset mode does so. Imported source-derived data must remain separate
from reviewer-created state, including annotations, proposed corrections,
correction decisions, tester feedback, export packet state, and audit events.

## Audit Expectations

Future implementation must make these activities auditable at the level
approved for the tester MVP, without designing the final audit schema in this
ADR:

- Login and access events where appropriate for the tester MVP.
- Role changes.
- Review status changes.
- Annotation creation and update.
- Proposed correction creation.
- Correction decisions.
- Export packet creation, update, and export.
- Import, reload, and reset actions.
- Tester feedback submission.
- Administrative user changes.

Audit events should preserve actor or process identity where available,
timestamp, relevant project or corpus scope, relevant source-derived or
reviewer-created target, and enough context to understand what changed without
erasing prior history or exposing secrets.

## Options Considered

Each option was evaluated against tester safety, auditability, ease of setup,
access revocation, privacy/security, correction and annotation accountability,
export control, future production readiness, and implementation complexity.

| Option | Evaluation |
|---|---|
| No authentication for tester MVP | Easiest setup and lowest implementation work, but unacceptable for tester safety. It exposes reviewer-created state, annotations, proposed corrections, feedback, exports, and audit context without attribution or revocation. Auditability, correction accountability, export control, privacy/security, and production readiness are poor. |
| Single shared tester account | Simple setup and slightly better than anonymous access, but weak auditability and revocation. Corrections, annotations, feedback, and export actions cannot be reliably attributed to individuals. Access removal requires changing credentials for everyone. Poor fit for production readiness and confusing for accountability. |
| Invite/provisioned individual tester accounts | Strong tester safety, auditability, correction and annotation accountability, and revocation. Setup is more work than anonymous or shared-account access, but it keeps tester feedback, review-state changes, correction proposals, and export actions attributable where feasible. Good foundation for production readiness without choosing a provider yet. |
| Role-based tester access | Strong fit for separating read-only review, active review, administrative access, and operator functions. Improves export control and reset/reload safety. Adds some implementation complexity, but a small conceptual role set is appropriate for the tester MVP. Best paired with individual tester accounts. |
| Organization/team-scoped access | Useful if a future provider supports group assignment, but too provider-specific for this ADR. Can simplify provisioning and revocation at scale, but may blur project-specific access unless roles and corpus scopes remain explicit. Good future option, deferred until provider and implementation decisions. |
| External identity provider integration | Strong production direction for security, account lifecycle, and possible multi-factor or single sign-on support, but provider choice is intentionally deferred. It can improve privacy/security and revocation, but it increases implementation complexity and may introduce platform-specific assumptions before hosted MVP architecture is fully sequenced. |

## Recommended Direction

The hosted tester MVP should require authenticated access using explicitly
provisioned or invited individual tester accounts.

The tester MVP should use simple role-based access with at least admin, tester
reviewer, read-only tester, and developer/operator roles. Provider choice,
identity storage, session strategy, authorization middleware, invitation flow,
role schema, and permission schema remain deferred.

Import, reload, and reset should be admin/operator-only. Destructive reset must
require elevated permission and auditability. Export packet creation,
finalization, and generated export delivery must be permissioned and auditable.
Reviewer-created actions should be attributable where feasible.

This recommendation does not approve a production access model. It defines the
minimum tester-MVP access boundary that later implementation must satisfy.

## Consequences

Benefits:

- Protects reviewer-created state, annotations, proposed corrections, tester
  feedback, export packet decisions, and audit history.
- Supports auditability for review actions, correction decisions, export
  actions, import/reload/reset operations, feedback, and administrative changes.
- Prepares for production roles without overbuilding the tester MVP.
- Makes revocation and scoped tester access part of the implementation contract.

Tradeoffs and risks:

- Authentication adds implementation work before testers can use the hosted app.
- Too much role complexity could delay the tester MVP.
- Too little role separation could make corrections, exports, reset/reload, or
  reviewer-created state unsafe or confusing.
- Provider choice remains deferred, so implementation work must still decide
  provider, sessions, storage, middleware, account recovery, and any
  multi-factor requirements later.

## Deferred Decisions

This ADR explicitly defers:

- Authentication provider.
- Identity storage.
- Session strategy.
- Authorization middleware.
- Role and permission schema.
- Invitation flow.
- Passwordless or single sign-on approach.
- Account recovery.
- Multi-factor authentication requirements.
- Production access governance.
- Audit log schema.
- User deprovisioning implementation.

## Work Not Approved By This ADR

No schema changes are approved by this ADR.

This ADR does not approve:

- Authentication implementation.
- Authorization implementation.
- User tables.
- Role tables.
- Invitation implementation.
- Audit schema implementation.
- App scaffold.
- Import/reload/reset implementation.
- Export implementation.
- Correction workflow implementation.
- Hosted deployment.