# QNAP Pilot Tester Invitation Decision

Use this guide before inviting early ylc.org testers to the QNAP-hosted CCLD
pilot. It records the access-control decision that must exist before tester
accounts, links, or credentials are shared.

This decision is required before inviting early ylc.org testers.

This is an operator decision gate, not an implementation of access control. The
current QNAP pilot can be configured, verified, and documented, but real external
tester authentication is not implemented yet.

## 1. Purpose

- Confirm that tester invitation is an explicit decision before early ylc.org
  users are invited.
- Confirm that the pilot remains a public-interest hobby project, not a DSCC
  project.
- Confirm that the current runtime has a production-mode auth boundary, but no
  real login, OIDC/OAuth2 callback handling, sessions, cookies, user tables, or
  invitation workflow.
- Confirm that this guide does not implement identity provider integration,
  access management, account storage, or deployment.

## 2. Who May Be Invited

Invite only explicitly approved named individuals or a small approved group.
Before an invitation is sent, record the intended role and scope.

Minimum role categories are the ADR-0011 and ADR-0014 categories:

- Operator/admin: approves access, reviews evidence, manages scope decisions,
  and can revoke access when the approved access method supports it.
- Tester reviewer: reviews assigned CCLD source-derived records and may create
  reviewer-created observations only when the approved access method and current
  implementation allow it.
- Read-only tester: views assigned source-derived records, source traceability,
  visible limitations, and safe review context only.
- Developer/operator: performs approved operational checks such as verifier,
  route evidence, seeded import evidence, troubleshooting, and backup readiness.
- System/process identity: used only for approved automated or scripted work
  where the operator has explicitly recorded why it is needed.

Do not grant broad admin/operator access by default. A tester invitation does
not imply access to all future data, all projects, non-CCLD sources,
statewide/public-source expansion, private sources, destructive operations, or
administrative functions.

## 3. Access Scope

The invitation decision must scope access to:

- The QNAP pilot environment only.
- The seeded or imported test corpus approved for the pilot.
- CCLD-only review workflows.
- Approved pilot routes only.
- The minimum role needed for the tester's task.

Do not grant broad future-data, all-project, statewide, private-source,
cross-environment, import/reload, reset, user/role administration, audit export,
or raw artifact access unless that specific access is separately approved and
documented.

## 4. Approval And Revocation

Before testers are invited, record:

- Who approved the tester or tester group.
- Which role and scope each tester receives.
- How access will be revoked.
- Who can perform revocation.
- How revocation will be recorded.
- How stale or unused access will be reviewed.
- How tester feedback and GitHub Issues will be triaged.

If real external authentication is not ready, the decision record should say so
plainly and should not substitute local-dev fixture auth, shared credentials, or
manual route obscurity for production authentication.

## 5. Current Auth Limitation

The current scaffold does not implement:

- Real login.
- Real OIDC/OAuth2 callback handling.
- Sessions or cookies.
- User tables.
- Self-service signup.
- A tester invitation workflow.
- Provider token exchange.
- Production password login.
- Account management UI.

Local-dev fixture auth is not production authentication. QNAP pilot mode must
keep `CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH=disabled` and must use
`CCLD_HOSTED_TESTER_AUTH_MODE=production`. Testers should not be invited into a
production-like environment until the operator has a deliberate access approach
for how they will authenticate, how their access is scoped, and how their access
can be revoked.

## 6. Evidence Packet Required Before Invitation

Before sending invitations, confirm the evidence packet contains:

- QNAP verifier output.
- Seeded import evidence command output.
- Route evidence command output.
- Auth readiness notes reviewed.
- Feedback configuration decision: intentionally disabled or fully configured.
- Retrieval configuration decision: intentionally disabled or fully configured
  with persistent raw artifact storage.
- PostgreSQL backup plan.
- Raw artifact backup plan.
- Known limitations acknowledged.
- A statement that no public-source completeness, legal, facility-wide, harm,
  abuse, neglect, liability, or rights-deprivation conclusions are made from the
  pilot evidence.

## 7. Do-Not-Do List

- Do not invite testers until the access method is deliberately approved.
- Do not use local-dev fixture auth as production authentication.
- Do not share `.env` or secrets.
- Do not commit provider secrets, callback URLs, tokens, tenant IDs, private
  URLs, hosted URLs, cookies, private headers, or connection strings.
- Do not give testers broad admin/operator access by default.
- Do not treat tester feedback, review notes, route evidence, retrieval status,
  or seeded import evidence as official public-source facts.
- Do not make public-source completeness, legal, facility-wide, harm, abuse,
  neglect, liability, or rights-deprivation conclusions.