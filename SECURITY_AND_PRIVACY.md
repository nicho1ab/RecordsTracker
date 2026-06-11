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

## Public repository hygiene

Public repository content must not include personal paths, account details, secrets, tokens, private URLs, local machine names, personal handles, personal email addresses, or other machine-specific identifiers. Use neutral placeholders such as `<repo-root>`, `<local-project-path>`, `<your-github-org-or-user>`, and `<repository-name>` in examples.

## Logging

Logs must not include secrets or unnecessary personal information. Logs should include source URL, document ID, connector name, and error details.

## Data sensitivity

Even public complaint data may include sensitive narrative content. Treat raw files and exports carefully. Avoid unnecessary redistribution of raw narrative text unless needed for the project purpose.
