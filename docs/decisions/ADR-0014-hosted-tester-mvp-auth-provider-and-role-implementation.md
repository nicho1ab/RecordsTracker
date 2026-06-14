# ADR-0014: Choose Hosted Tester MVP Auth Provider and Role Implementation Direction

## Status

Accepted

## Context

The project is moving toward a user-facing hosted tester MVP. ADR-0011 already
requires authenticated, invited or provisioned, role-scoped tester access and
rejects anonymous hosted tester access. ADR-0013 defines operational boundaries
for audit logging, export generation, reset/reload, and tester data retention.

The remaining authentication decision blocker is provider direction. The next
hosted implementation branches need enough direction to design the first
authenticated tester workflow, later schema/API work, audit identity capture,
role checks, revocation, and scoped tester access without committing secrets,
deployment configuration, hosted URLs, user tables, or provider-specific
application settings in this ADR.

This ADR chooses the authentication provider class and role implementation
direction for the hosted tester MVP. It does not implement authentication or
authorization.

## Decision

The hosted tester MVP will use a managed standards-based OpenID Connect and
OAuth 2.0 identity provider class for authentication.

The implementation direction is:

- Use an external managed identity provider that supports OpenID Connect,
  OAuth 2.0 authorization code flow with PKCE, issuer metadata discovery,
  signed ID tokens, token expiration, and account disablement or revocation.
- Prefer provider-managed user identity, password handling, account recovery,
  and multi-factor capability instead of building custom password storage in
  this project.
- Keep the application responsible for project/corpus authorization decisions,
  role checks, source-derived versus reviewer-created state separation, audit
  context capture, and cautious public-source workflow boundaries.
- Store secrets, client credentials, provider URLs, tenant IDs, app
  registrations, callback URLs, and environment-specific configuration outside
  the repository.

This ADR accepts the provider class and implementation direction only. A later
implementation PR may choose the concrete provider instance for the environment
being built when it adds configuration documentation, tests, and deployment or
local development behavior for that layer.

The hosted tester MVP must not implement local password authentication, shared
reviewer accounts, anonymous reviewer-created state, or unauthenticated write
paths for reviewer-created state.

## Roles Needed for the MVP

The hosted tester MVP must implement the ADR-0011 role boundaries as the minimum
role set. Implementations may use finer permissions later, but they must
preserve these role categories:

- Admin: manages tester access, role assignments, project or corpus scope, and
  elevated tester-MVP operations. Admins may approve elevated reset modes and
  may view audit history for authorized tester projects. Admin actions do not
  make annotations, corrections, feedback, export decisions, or review status
  official public-source facts.
- Tester reviewer: views assigned source-derived records and source
  traceability, changes review status where allowed, adds annotations and
  notes, proposes corrections, submits tester feedback, and prepares export
  packets when granted export permission. Tester reviewers may not manage users
  or roles, import or reload data, perform destructive reset, or access projects
  outside assigned scope.
- Read-only tester: views assigned source-derived records, source
  traceability, extraction audit context, visible limitations, and read-only
  review context. Read-only testers may not create reviewer-created state,
  decide corrections, change statuses, create or finalize exports, import,
  reset, reload, or manage access.
- Developer/operator: performs approved operational tester-MVP tasks such as
  scripted import/reload, reset support, validation checks, troubleshooting,
  and audit review where authorized. Developer/operator access must not bypass
  reviewer-role boundaries or silently delete reviewer-created state.
- System: represents an approved process identity for scheduled, scripted, or
  automated work. System identity must be distinguishable from human tester,
  admin, and operator accounts in audit context.

The authorization implementation may represent these as provider groups,
provider app roles, application roles, database-backed assignments, or a
combination after schema/API decisions are accepted. Regardless of storage, the
application must enforce project or corpus scope before reviewer-created state
is enabled.

## Authorization Boundaries Before Reviewer-Created State

Before testers can create or update reviewer-created state, implementation must
enforce all of these boundaries:

- External tester access must be authenticated and role-scoped.
- No anonymous reviewer-created state is allowed for the hosted tester MVP.
- Reviewer-created state must be attributable to authenticated actors or an
  approved system identity.
- Source-derived public records remain source-derived and must not be
  overwritten by reviewer-created state.
- Read access to a public-source-derived record does not imply permission to
  annotate, propose corrections, decide corrections, change review status,
  submit workflow feedback, include records in export packets, finalize exports,
  import/reload, reset, or administer users.
- Authorization must be scoped to an assigned project, corpus, seeded test
  corpus, or equivalent tester-MVP review scope.
- Import, reload, destructive reset, user/role administration, export
  finalization, correction decision, and audit-log access must require elevated
  roles or explicit permissions.
- Hosted live crawling, hosted connector execution, automatic source expansion,
  and production public launch are not approved by this ADR.

Authorization checks must protect the reviewer-created state domain separately
from source-derived records. Labels, exports, APIs, and UI behavior must not
present reviewer-created state as official public-source content.

## Identity Claims and Audit Attributes

To support ADR-0013 audit logging, authenticated actor context must provide or
derive the following minimum identity attributes before affected audited actions
are enabled:

- Stable provider subject identifier for the authenticated account or process.
- Provider issuer or tenant/environment identifier where applicable.
- Display name or tester label suitable for review workflows when available.
- Email address or other contact identifier when approved for the tester access
  model and available from the provider.
- Role or permission assignments used by the application.
- Project, corpus, or tester-scope assignments used by the application.
- Actor category: Tester, Operator, Admin, Developer/operator, or System.
- Account status sufficient to prevent disabled or revoked accounts from
  changing reviewer-created state.

Audit events must eventually capture actor, timestamp, action, target, and
relevant before/after or context details where applicable. Timestamps for system
generated audit events must use ISO datetime with timezone. Audit context must
not store secrets, tokens, cookies, private headers, unnecessary sensitive
narrative content, or provider credentials.

## External Tester Access Lifecycle

External tester access must be scoped, approved, disabled, and reviewed through
an explicit lifecycle:

- Scope: tester access must be limited to a specific seeded corpus, review
  project, tester project, environment, role, and permission set.
- Approval: an Admin or authorized operator must approve or provision tester
  access before the tester can use hosted workflows.
- Invitation or provisioning: testers must use individual accounts where
  feasible; shared accounts are not approved for reviewer-created workflows.
- Disablement: access must be revocable without changing access for unrelated
  testers, projects, corpora, or environments.
- Review: access assignments must be reviewable before external tester use and
  periodically during tester-MVP operation. Review must include disabled users,
  stale invitations where applicable, role assignments, corpus/project scope,
  operator access, and system identities.

The access lifecycle implementation remains deferred until provider, schema,
API, and operational tooling decisions define where assignments, invitations,
disablement records, and access reviews are persisted or verified.

## What Remains Blocked

The following implementation remains blocked until database, schema, API,
configuration, provider-instance, deployment, or storage decisions define the
concrete layer being built:

- User, role, permission, session, invitation, project-scope, or corpus-scope
  persistence.
- Database tables, migrations, indexes, constraints, ORM models, or seed data
  for identity, access, roles, sessions, or audit events.
- API routes, middleware, decorators, guards, endpoints, or UI changes for
  login, logout, callback handling, role checks, invitations, access review,
  revocation, or administration.
- Auth provider tenant/app registration, client credentials, callback URLs,
  hosted URLs, cloud configuration, CI secrets, environment variables committed
  to the repo, or deployment behavior.
- Final multi-factor policy, account recovery policy, backup/restore behavior,
  production public launch, public URL behavior, QNAP, Azure, AWS, or cloud
  database behavior.
- Audit table or event-store implementation.
- Reviewer-created state persistence.
- Source import, hosted live crawling, hosted connector execution, or automatic
  public-source expansion.

No schema changes are approved by this ADR.

## Implementation Now Allowed

After this ADR, future focused branches may implement authentication and
authorization behavior against the accepted provider class and role boundaries,
provided each branch stays inside its approved layer and includes focused
validation.

Allowed follow-up implementation includes:

1. A concrete database product and migration tooling decision that accounts for
   identity, role, scope, and audit needs without creating tables in that ADR.
2. Minimal hosted schema/API scaffold work that reserves separate areas for
   provider identity references, application role/scope assignments,
   reviewer-created state, and audit events after schema decisions are accepted.
3. Auth integration implementation using a managed OpenID Connect/OAuth 2.0
   provider class, externalized configuration, and tests for authenticated,
   unauthenticated, disabled, role-denied, and out-of-scope access paths.
4. First authenticated tester workflow over a seeded, source-traceable corpus
   after seeded source-derived records and the relevant authorization checks are
   implemented.
5. Access lifecycle implementation for invitations or provisioning, revocation,
   access review, and operator/system identities after persistence and API
   decisions are accepted.

Each implementation branch must preserve source-derived versus reviewer-created
state separation, preserve source traceability, avoid anonymous
reviewer-created state, avoid committed secrets, meet accessibility and
security/privacy expectations, keep cautious public-source language visible,
and identify what remains deferred.

## Consequences

Benefits:

- The project can move from conceptual access boundaries to implementable auth
  integration without building custom password handling.
- Authenticated tester actions can be tied to provider identity, application
  roles, project/corpus scope, and ADR-0013 audit context.
- External tester access can be invited or provisioned, scoped, revoked, and
  reviewed before reviewer-created state is enabled.
- The decision keeps provider secrets, tenant/app details, hosted URLs, and
  deployment configuration out of the repository.

Tradeoffs and risks:

- A standards-based provider class still requires later provider-instance,
  configuration, callback, session, and deployment decisions.
- Role and scope enforcement will require schema/API work before the hosted app
  can safely support reviewer-created state.
- Provider-managed identity reduces password risk but does not remove the need
  for application-level authorization, audit capture, access review, and
  revocation tests.

## Work Not Approved By This ADR

This ADR does not approve implementation of:

- Application code.
- Auth middleware.
- API routes.
- Schemas.
- Database tables.
- Migrations.
- Secrets.
- CI secrets.
- Provider configuration.
- Hosted URLs.
- Deployment.
- User or role administration UI.
- Reviewer-created state persistence.
- Audit tables or event stores.
- Source import.
- Hosted live crawling.
- Hosted connector execution.
- Production public launch.

No source-derived canonical fields are added or changed.