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

Authentication provider details, identity storage, sessions, authorization
middleware, user tables, role tables, invitation flow, account recovery,
multi-factor requirements, and user deprovisioning implementation remain
deferred to later implementation decisions. Secrets, tokens, private URLs, and
account-specific configuration must not be committed.

## Public repository hygiene

Public repository content must not include personal paths, account details, secrets, tokens, private URLs, local machine names, personal handles, personal email addresses, or other machine-specific identifiers. Use neutral placeholders such as `<repo-root>`, `<local-project-path>`, `<your-github-org-or-user>`, and `<repository-name>` in examples.

## Logging

Logs must not include secrets or unnecessary personal information. Logs should include source URL, document ID, connector name, and error details.

## Data sensitivity

Even public complaint data may include sensitive narrative content. Treat raw files and exports carefully. Avoid unnecessary redistribution of raw narrative text unless needed for the project purpose.
