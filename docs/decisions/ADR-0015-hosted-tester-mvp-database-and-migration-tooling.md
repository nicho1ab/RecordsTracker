# ADR-0015: Choose Hosted Tester MVP Database and Migration Tooling

## Status

Accepted

## Context

The project is moving toward a user-facing hosted tester MVP. ADR-0010 defined
the physical schema and migration strategy boundary, requiring separated areas
or table groups for import metadata, source-derived imported records,
reviewer-created state, audit events, export packet state, tester feedback, and
operational/reset metadata. ADR-0013 defined operational boundaries for audit
logging, export generation, reset/reload, and tester data retention. ADR-0014
chose a managed standards-based OpenID Connect/OAuth 2.0 provider class and
role/scope implementation direction.

The remaining database and migration decision blocker is the concrete product
and migration tooling direction. Minimal hosted schema/API work, seeded corpus
import/reset, reviewer-created state persistence, audit event persistence,
export packet persistence, tester feedback persistence, and the first
authenticated tester workflow need a relational persistence target and a
repeatable migration path before implementation can proceed safely.

Superseding note: ADR-0016 later approved controlled browser-triggered,
server-executed CCLD retrieval jobs. PostgreSQL remains the production-style
data store for imported source-derived records and any future separated
retrieval-job operational metadata. ADR-0016 does not add schema changes to
ADR-0015; it only approves the future retrieval-job boundary that later schema
or implementation branches must map into separated persistence.

This ADR chooses the database product and migration tooling direction for the
hosted tester MVP. It does not implement schemas, tables, migrations, API
routes, imports, reset commands, authentication middleware, secrets, deployment,
or CI configuration.

## Decision

The hosted tester MVP will use PostgreSQL as the concrete hosted relational
database product for persisted hosted tester state and imported hosted
source-derived records.

The hosted tester MVP will use Alembic-managed migrations in the Python
toolchain as the concrete migration tooling direction. Migrations must be
explicit, reviewable, repeatable in local/test/hosted environments, and paired
with tests at the level of the implemented schema or migration change.

SQLite and Datasette remain retained for validation, inspection, debugging,
local exploration, export support, and transition comparison. They are not the
primary hosted tester persistence store for reviewer-created state, audit
events, export packet state, tester feedback, auth role/scope assignments, or
operational/reset metadata.

This ADR chooses PostgreSQL and Alembic only as the product and migration
tooling direction. It does not choose a hosting provider, cloud service,
managed database plan, connection string, database name, schema names, table
names, columns, indexes, constraints, ORM model, API framework, deployment
pattern, backup policy, or retention duration.

## Persistence Areas Supported

PostgreSQL must support the separated persistence areas required by ADR-0010:

- Import and batch metadata.
- Source-derived imported records.
- Reviewer-created state.
- Audit events.
- Export packet state.
- Tester feedback.
- Operational and reset/reload metadata.
- Authenticated actor references, role assignments, and project or corpus scope
  assignments needed by ADR-0014.

Future schema implementation may represent these as PostgreSQL schemas, table
prefixes, modules, or clearly separated table groups, but the implementation
must make the data-domain boundaries visible in migrations, tests, API access,
and developer documentation.

## Source-Derived Versus Reviewer-Created State Boundary

PostgreSQL schema work must preserve the ADR-0008 and ADR-0010 separation
between source-derived records and reviewer-created state.

Source-derived imported records must preserve source traceability, including
source URL, raw SHA-256 hash, raw path or artifact reference where available,
connector name and version, retrieval timestamp, source document identity,
report index or document type where available, extraction audit context where
available, original extracted values, import batch linkage, validation status,
and cautious public-source limitations.

Reviewer-created state must link to source-derived records through stable
source-derived identities, review item references, or other approved foreign-key
style references. Reviewer-created state must not overwrite source-derived
canonical records, raw source files, source document metadata, extraction audit
records, source URLs, raw hashes, connector metadata, retrieval timestamps, or
original extracted values.

Schema work must not add source-derived canonical fields unless a later data
contract, schema, documentation, migration, and test update explicitly approves
them.

## ADR-0013 Operational Boundary Support

PostgreSQL and Alembic support the ADR-0013 operational boundaries as follows:

- Audit logging: future schema can persist actor references, ISO datetime with
  timezone timestamps, actions, targets, project/corpus scope, import batch or
  reset scope, and relevant before/after or context details without mutating
  source-derived records.
- Export generation: future schema can persist export packets, packet items,
  inclusion/exclusion decisions, generated artifact metadata, source
  traceability references, original extracted values, correction context, and
  export lifecycle audit links.
- Reset/reload: future schema can separate seeded source-derived records from
  reviewer-created state, record import batches, compare against retained
  SQLite/Datasette validation output or validated pipeline artifacts, and track
  reset/reload operations, affected counts, preserved state, archived state, and
  recovery notes.
- Tester data retention: future schema can assign retention behavior by data
  category, including source-derived imported records, raw/source traceability
  references, annotations, proposed corrections, review state, feedback, audit
  events, export packets, import batches, and reset/reload metadata.

This ADR does not set retention durations or implement audit, export, reset, or
retention behavior.

## ADR-0014 Auth Identity and Role/Scope Support

PostgreSQL must support application-owned references to the managed OpenID
Connect/OAuth 2.0 identity provider class chosen by ADR-0014 without storing
provider secrets or credentials.

Future schema/API implementation may persist provider subject references,
issuer or tenant/environment references where applicable, tester display labels
where approved, role assignments, project/corpus scope assignments, account
status snapshots or revocation markers, operator/system identity references,
and access review metadata.

Authorization enforcement remains an application/API responsibility. Database
constraints and indexes may support integrity and query safety, but they do not
replace authenticated request handling, role checks, project/corpus scope
checks, disabled-account rejection, audit context capture, or access review.

## Migration Tooling Direction

Alembic migrations must follow these principles when future implementation adds
schemas or tables:

- Migrations must be checked into the repository as reviewable source files.
- Migrations must be runnable in local and automated test environments.
- Migrations must have deterministic ordering and stable identifiers.
- Migration PRs must distinguish structural changes from imports, data loads,
  reset/reload operations, and reviewer-created state updates.
- Migrations must not silently perform destructive reset, source-derived value
  rewrites, or reviewer-created state deletion.
- Migration implementation must include rollback or recovery guidance
  appropriate to the tester MVP layer being changed.
- Schema-affecting migrations must include tests for data-domain separation,
  source traceability, reviewer-state preservation, auditability, and
  reset/reload behavior at the level implemented.

Alembic autogeneration may be used as a drafting aid only when the generated
revision is reviewed and edited as an explicit migration. Autogenerated changes
must not be accepted blindly.

## What Remains Blocked

The following implementation remains blocked until schema/API implementation
decisions or focused implementation PRs define the concrete layer being built:

- Application code.
- Database tables, PostgreSQL schemas, table groups, indexes, constraints,
  triggers, views, ORM models, or seed data.
- Alembic configuration files, migration scripts, migration commands, CI
  migration jobs, or database bootstrap scripts.
- API routes for source-derived records, reviewer-created state, audit events,
  exports, reset/reload, feedback, imports, auth roles, or access scope.
- Import artifact format, import logic, seeded corpus load logic, reset
  commands, destructive reset modes, or comparison implementation.
- Auth middleware, provider configuration, secrets, connection strings, hosted
  URLs, deployment, cloud database provisioning, QNAP, Azure, AWS, DNS, public
  URL, or production public launch behavior.
- Retention automation, archival jobs, deletion workflows, backup/restore
  implementation, monitoring, or incident response.
- Unbounded hosted live crawling, generic hosted connector execution, automatic
  public-source expansion, and any retrieval job outside ADR-0016.

No schema changes are approved by this ADR.

## Implementation Now Allowed

After this ADR, future focused branches may implement database and migration
behavior against PostgreSQL and Alembic, provided each branch stays inside its
approved layer and includes focused validation.

Allowed follow-up implementation includes:

1. Minimal PostgreSQL/Alembic project wiring for local and test environments
   without domain tables, secrets, hosted URLs, deployment, or CI secret
   configuration.
2. Minimal hosted schema/API scaffold for seeded source-derived records and
   reviewer-created state after the schema/API branch defines the exact tables,
   migration files, validation, and rollback or recovery expectations.
3. Import batch and seeded corpus persistence from validated pipeline output
   after import artifact and schema/API details are approved.
4. Reviewer-created state, audit event, export packet, tester feedback, and
   reset/reload metadata persistence after focused schema/API implementation
   branches define and test each layer.
5. Auth role/scope persistence needed for the first authenticated tester
   workflow after auth integration and schema/API branches define the concrete
   references and authorization tests.

Each implementation branch must preserve the public portal as the source of
record, preserve raw source files and source traceability, keep source-derived
records separate from reviewer-created state, attribute reviewer-created state
to authenticated actors where applicable, capture ADR-0013 audit context where
implemented, load seeded hosted data only from controlled snapshot imports from
validated pipeline output, avoid committed secrets, and identify what remains
deferred.

## Consequences

Benefits:

- PostgreSQL gives the hosted tester MVP a practical relational persistence
  target for source-derived imports, reviewer-created state, audit events,
  export packet state, tester feedback, reset/reload metadata, and role/scope
  references.
- Alembic fits the existing Python-centered project and provides repeatable,
  reviewable migrations for local, test, and future hosted environments.
- SQLite and Datasette remain available for validation and transition
  comparison without carrying reviewer-created hosted state.
- The decision unblocks minimal schema/API scaffold work while preserving
  source traceability and data-domain separation.

Tradeoffs and risks:

- PostgreSQL adds operational setup compared with the current local SQLite
  validation database.
- Alembic migrations require discipline; autogenerated migrations must be
  reviewed to avoid weakening data-domain separation or traceability.
- Database product selection does not by itself solve API design, hosted
  deployment, secrets management, backups, retention, or auth integration.
- Future hosted implementation must avoid using database convenience as a reason
  to blend source-derived facts with reviewer-created workflow state.

## Work Not Approved By This ADR

This ADR does not approve implementation of:

- Application code.
- Database tables.
- Schemas.
- Migrations.
- Migration configuration.
- API routes.
- Import logic.
- Reset commands.
- Auth middleware.
- Secrets.
- Provider configuration.
- Connection strings.
- Hosted URLs.
- Deployment.
- CI configuration.
- Audit tables or event stores.
- Reviewer-created state persistence.
- Export builder logic.
- Hosted live crawling or hosted connector execution outside the ADR-0016
  controlled CCLD retrieval-job boundary.
- Production public launch.

No source-derived canonical fields are added or changed.