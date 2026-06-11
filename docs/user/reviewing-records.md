# Reviewing Records

## Suggested review steps

1. Open the `complaints` table to review complaint dates, findings, and delay fields.
2. Open the `allegations` table to review allegation text linked by complaint ID.
3. Open the `source_documents` table to compare extracted fields to the source URL and raw file hash.
4. Start with records flagged as low confidence when confidence fields are available.
5. Note any extraction issue for correction.

## Delay fields

Delay fields are calculated from extracted dates. If a date is missing or uncertain, the delay should be blank or marked unknown.
