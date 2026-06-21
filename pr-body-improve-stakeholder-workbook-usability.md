## Summary
- Improves stakeholder workbook usability for first-time recipients.
- Refines the README worksheet as a workbook landing page with tab guidance, counts/coverage context, and cautious source-of-record/limitations wording.
- Adds focused regression coverage for workbook usability behavior and safe stakeholder-facing wording.

## Validation
- [ ] .\.venv\Scripts\python.exe -m pytest tests/unit/test_stakeholder_extract.py -q
- [ ] .\scripts\lint.ps1
- [ ] .\scripts\docs.ps1
- [ ] git diff --check

## Scope notes
- No source retrieval, parsing, schema, migration, hosted UI, auth, deployment, Datasette, source connector, or live retrieval changes.
- No risk scores, rankings, legal conclusions, source verification claims, complaint-coverage claims, source-completeness claims, or facility-wide conclusions.
- No generated data/processed outputs committed.
