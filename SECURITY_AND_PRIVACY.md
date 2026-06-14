# Security and Privacy

## Principles

- Use public data only unless explicitly approved.
- Do not store secrets in source control.
- Do not log credentials, cookies, tokens, or private headers.
- Do not scrape private or authenticated systems.
- Respect source terms, robots directives, rate limits, and applicable law.
- Preserve source traceability and disclaimers.

## Source handling

The initial source is a public portal. Before expanding to new sources, document:

- Source URL
- Terms/conditions reviewed
- Access method
- Rate limiting approach
- Data sensitivity concerns
- Retention approach

## Secrets

Local secrets must use environment variables or untracked `.env` files. `.env` is ignored by Git.

## Hosted tester access

Hosted tester MVP access must be authenticated and limited to explicitly
invited or provisioned testers, operators, and administrators. Anonymous hosted
tester access is not allowed because the hosted workflow includes
reviewer-created state, tester feedback, annotations, proposed corrections,
export decisions, audit history, and potentially sensitive review context.

ADR-0014 selects a managed standards-based OpenID Connect/OAuth 2.0 identity
provider class for the hosted tester MVP. The project must not build custom
password storage for the tester MVP. Provider secrets, client credentials,
tenant IDs, app registrations, callback URLs, hosted URLs, private URLs, tokens,
and account-specific configuration must not be committed.

The current hosted auth boundary scaffold validates only the accepted managed
OIDC/OAuth2 provider class through `CCLD_HOSTED_TESTER_AUTH_PROVIDER_CLASS` and
models authenticated actor identity, account status, role assignments,
project/corpus scopes, authorization targets, and audit-ready actor context for
local/test use. It does not implement provider login, token validation, session
storage, cookies, callback handling, user tables, role tables, provider tenant
configuration, client secrets, or production auth middleware. Protected service
helpers must reject unauthenticated, disabled or revoked, role-denied, and
out-of-scope actors before future reviewer-created workflows are enabled.

The current source-derived HTTP/API read route seam is local/test only and must
receive an explicit fixture or test actor context from the caller. It reuses the
auth boundary to reject unauthenticated, disabled or revoked, role-denied, and
out-of-scope reads before serializing staged source-derived records. It does not
parse or store provider tokens, create sessions or cookies, add production auth
middleware, persist audit events, expose reviewer-created state, or commit
provider, tenant, callback, hosted URL, or secret configuration.

The current reviewer workflow shell is also local/test only and must receive an
explicit workflow shell context backed by the source-derived route context. It
consumes the authenticated source-derived route seam for read-only queue and
detail payloads, preserves the same unauthenticated, disabled or revoked,
role-denied, and out-of-scope rejection behavior, and marks reviewer-created
state persistence and reviewer actions as deferred. It does not authenticate
browser users, parse or store provider tokens, create sessions or cookies, add
production auth middleware, create anonymous reviewer-created state, persist
audit events, or commit provider, tenant, callback, hosted URL, or secret
configuration.

The current reset/reload dry-run seam is local/test only and must receive an
explicit database, actor, and corpus scope context from tests or local callers.
It reuses the auth boundary to require import/reload permission, reject
unauthenticated, disabled or revoked, role-denied, and out-of-scope actors, and
report what a future seeded corpus reset/reload would affect. It performs
read-only inspection queries only. It does not delete, truncate, overwrite,
archive, import, reload, persist audit events, parse or store provider tokens,
create sessions or cookies, add production auth middleware, or commit provider,
tenant, callback, hosted URL, or secret configuration.

Identity storage, sessions, authorization middleware, user tables, role tables,
invitation flow, account recovery, final multi-factor requirements, and user
deprovisioning implementation remain deferred to later implementation
decisions. Future implementation must enforce role, permission, and
project/corpus scope before reviewer-created state is enabled and must preserve
audit identity context without logging credentials, cookies, tokens, private
headers, or unnecessary sensitive narrative content.

ADR-0015 chooses PostgreSQL and Alembic-managed migrations for hosted tester MVP
persistence. Future database implementation must not store provider secrets,
tokens, cookies, private headers, connection strings, or unnecessary sensitive
narrative content. Reviewer-created state, audit events, feedback, export packet
state, and role/scope assignments must remain separated from source-derived
records and must be scoped to authenticated actors or approved system identities
where applicable.

## Public repository hygiene

Public repository content must not include personal paths, account details, secrets, tokens, private URLs, local machine names, personal handles, personal email addresses, or other machine-specific identifiers. Use neutral placeholders such as `<repo-root>`, `<local-project-path>`, `<your-github-org-or-user>`, and `<repository-name>` in examples.

## Logging

Logs must not include secrets or unnecessary personal information. Logs should include source URL, document ID, connector name, and error details.

## Data sensitivity

Even public complaint data may include sensitive narrative content. Treat raw files and exports carefully. Avoid unnecessary redistribution of raw narrative text unless needed for the project purpose.
