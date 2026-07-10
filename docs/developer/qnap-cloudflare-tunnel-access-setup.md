# Cloudflare Tunnel + Cloudflare Access Setup

Use this runbook to configure Cloudflare Tunnel and Cloudflare Access for the
QNAP-hosted CCLD pilot after the access-layer identity decision has been
recorded. It does not implement the app's OIDC auth layer, change app behavior,
or affect schemas, migrations, retrieval, or source connectors.

This runbook does not contain real secrets, tokens, account IDs, private
hostnames, or tester email addresses. All private operator values use
`<placeholder>` format and must be kept in host-local configuration or a
password manager, never committed.

See [qnap-pilot-access-method-decision.md](qnap-pilot-access-method-decision.md)
section 9 for the recorded access-layer decision, guardrails, and open questions
that must be resolved before sharing a tester-facing URL.

---

## 1. Prerequisites

All of the following must be true before starting Cloudflare Tunnel setup:

- QNAP LAN smoke test has passed. The app and PostgreSQL containers start, Alembic
  migrations run, and `/health` and `/` respond `200` on the local network. See
  [qnap-pilot-deployment-inventory.md](qnap-pilot-deployment-inventory.md)
  section 5 for the confirmed LAN smoke test status.
- The `verify-qnap-pilot-workflow.ps1` script passes against the deployment
  `.env` file.
- The Cloudflare Access identity decision is recorded (open questions in
  [qnap-pilot-access-method-decision.md](qnap-pilot-access-method-decision.md)
  section 9.5 are resolved before sharing a URL).
- A Cloudflare account with an active zone (domain) is available.
- `cloudflared` can be installed or run as a container on the QNAP host.
- No Dream Machine Pro port forwarding is configured for the app port. **Do not
  add router port forwarding for RecordsTracker at any point in this setup.**

---

## 2. Safety Boundaries Before Starting

Read these before any Cloudflare step:

- **Only the app HTTP service is exposed through the tunnel.** QNAP admin UI
  (port 8080/443), Container Station UI, SSH (port 22), SMB (port 445), AFP,
  NAS management services, Docker socket, PostgreSQL port (5432), and any other
  internal QNAP or app service must not be reachable through the tunnel.
- **Cloudflare Access is a network-layer access control.** It is not the app's
  authentication layer. The app keeps `CCLD_HOSTED_TESTER_AUTH_MODE=production`
  and `CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH=disabled`. Cloudflare Access sitting in
  front does not replace the app's hosted auth boundary, session handling, OIDC
  callback, user tables, or role enforcement.
- **No public unauthenticated route.** Cloudflare Access must be configured and
  confirmed blocking before any URL is shared with testers.
- **No Dream Machine Pro port forwarding.** Cloudflare Tunnel does not require
  router or firewall changes. Do not open router ports for this app.
- **Secrets stay outside the repo.** Tunnel tokens, Cloudflare account/zone IDs,
  Access application credentials, private hostname, and tester emails must not
  be committed, pasted into docs or issues, or logged.

---

## 3. Cloudflare Account and Zone Readiness

1. Log in to the Cloudflare dashboard.
2. Confirm the zone (domain) that will host the pilot subdomain is active.
3. Note the Cloudflare account ID. Keep it in a password manager or local notes;
   do not commit it.
4. Confirm the account has access to **Zero Trust â†’ Tunnels** and
   **Zero Trust â†’ Access â†’ Applications**.

---

## 4. Choose a Pilot Hostname Placeholder

Record the intended pilot subdomain in local operator notes. Example pattern:
`<pilot-subdomain>.<your-zone-domain>`. Do not commit the real subdomain.

The subdomain must:
- Not suggest it is a public production service.
- Be easy to revoke (delete the DNS record and tunnel route to disable access).

---

## 5. Create the Cloudflare Tunnel

Using the Cloudflare dashboard:

1. Go to **Zero Trust â†’ Network â†’ Tunnels**.
2. Click **Create a tunnel**.
3. Select **Cloudflared** as the connector type.
4. Give the tunnel a name such as `recordstracker-qnap-pilot`.
5. Copy the tunnel token shown in the dashboard. This token is a secret. Store
   it in a local password manager or the QNAP host's secret storage only.
   **Do not commit it, paste it in docs, or share it in chat.**
6. Note the tunnel ID. Keep it in local operator notes.

---

## 6. Run cloudflared on the QNAP Host

### Option A: Docker container (recommended for QNAP Container Station)

On the QNAP host, run `cloudflared` as a detached container. Replace
`<tunnel-token>` with the actual token from step 5 â€” keep it in the QNAP
host's environment or Container Station secret configuration, not in committed
files:

```bash
docker run -d --restart unless-stopped \
  --name cloudflared \
  cloudflare/cloudflared:latest \
  tunnel --no-autoupdate run --token <tunnel-token>
```

Do not include the real token in any script committed to the repository. If
using a `.env`-style file for the token, keep that file untracked.

### Option B: Native cloudflared binary

If a native QNAP binary is available:

```bash
Start the Cloudflare tunnel using host-local Cloudflare-managed configuration or a host-local service definition. Do not place tunnel tokens in repository files, examples, scripts, logs, screenshots, or copied terminal output.
```

### Confirming the connector is active

After starting the connector, return to the Cloudflare dashboard
(**Zero Trust â†’ Tunnels**) and confirm the tunnel shows **Healthy** with at
least one connected connector. A **Healthy** state confirms the QNAP host can
reach Cloudflare.

---

## 7. Route Only the App HTTP Service Through the Tunnel

In the Cloudflare dashboard, configure the tunnel's **Public Hostname**:

1. Go to **Zero Trust â†’ Tunnels**, select the tunnel, then **Configure â†’
   Public Hostnames**.
2. Add a public hostname:
   - **Subdomain**: `<pilot-subdomain>` (the placeholder chosen in section 4).
   - **Domain**: `<your-zone-domain>`.
   - **Service type**: `HTTP`.
   - **URL**: `http://localhost:<CCLD_HOSTED_PORT>` or
     `http://<qnap-lan-ip>:<CCLD_HOSTED_PORT>`, where `CCLD_HOSTED_PORT` is
     the port from the QNAP `.env` file (default `8000`).
3. Save the public hostname. Cloudflare will create the CNAME DNS record
   automatically.

**Do not add a public hostname route for any other QNAP service.** Only the
app HTTP service on `CCLD_HOSTED_PORT` should have a public hostname entry.

---

## 8. Configure Cloudflare Access Before Sharing Any URL

Cloudflare Access must be configured and confirmed blocking before the pilot
URL is shared with any tester.

1. Go to **Zero Trust â†’ Access â†’ Applications**.
2. Click **Add an application** â†’ **Self-hosted**.
3. Configure:
   - **Application name**: `RecordsTracker Pilot` (or similar).
   - **Application domain**: `<pilot-subdomain>.<your-zone-domain>`.
   - **Session duration**: choose a short session for the pilot (e.g., 8 hours
     or 24 hours). Record the chosen duration in local operator notes.
4. Add an **Access policy**:
   - **Policy name**: `Tester allowlist`.
   - **Action**: Allow.
   - **Include rule**: Emails â€” list the individually approved tester email
     addresses. Keep this list in local operator notes only.
   - Add a second policy with **Action: Block** and no include rules, or rely
     on Cloudflare Access's default deny for all non-matching requests.
5. Choose the **identity method** and record it in the access-method decision
   doc (section 9.5). Options include:
   - **One-time PIN (email OTP)**: Cloudflare sends a one-time code to the
     tester's email. No external identity provider required. Good for a small
     named tester group.
   - **Google identity**: requires testers to have a Google account.
   - **Microsoft identity**: requires testers to have a Microsoft/Azure AD
     account.
   - **Another supported Cloudflare Access identity provider**: see Cloudflare
     documentation for available options.
6. Save the Access application.

---

## 9. Verification: Smoke Test Access Controls

Perform all of the following before sharing the pilot URL:

### 9.1 Confirm no public unauthenticated route

Open a private/incognito browser window and navigate to:
```
https://<pilot-subdomain>.<your-zone-domain>/
```
Cloudflare Access should redirect to a login/verification page. The app itself
should not be visible without authentication.

### 9.2 Confirm Access blocks a non-tester session

Using a private/incognito session, complete the Cloudflare Access authentication
flow with an email address that is **not** in the allowlist. Cloudflare Access
should deny the request and show an access-denied message. The app must not
be reachable.

### 9.3 Confirm Access allows an approved tester

Using the allowlisted test email, complete the Cloudflare Access authentication
flow. After verification, the app landing page should load and `/health` should
return `200`. Confirm the app shows the CCLD review shell (not a provider login
page â€” the app's own OIDC auth is not yet implemented and protected routes will
show sign-in-required state).

### 9.4 Confirm no QNAP management service is reachable

From outside the LAN, confirm that QNAP admin ports and internal services
are not accessible through the tunnel or through any other route:

- QNAP admin UI on ports 8080 and 443: should not be accessible from outside
  the LAN through any Cloudflare route.
- Container Station UI: should not be accessible.
- SSH (port 22), SMB (port 445): should not be accessible through the tunnel.
- PostgreSQL (port 5432): should not be accessible from outside the LAN.
- No other QNAP or Docker service should have a public hostname configured in
  the Cloudflare tunnel.

### 9.5 Confirm the app health route responds through the tunnel

```
https://<pilot-subdomain>.<your-zone-domain>/health
```
Should return `200` with `"status": "ok"` after Access authentication passes.

### 9.6 Confirm the app auth status route is safe

```
https://<pilot-subdomain>.<your-zone-domain>/auth/status
```
Should return `200` and summarize auth mode and provider-class placeholder
state only. Must not expose provider subjects, issuers, raw claims, tokens,
client secrets, or connection strings.

---

## 10. Evidence to Capture (Without Secrets)

Record the following in local operator notes or the evidence packet. Do not
include tunnel tokens, account/zone IDs, Access credentials, real email
addresses, or private hostnames in committed files:

- Tunnel name and confirmation that it showed **Healthy** in the dashboard.
- Access application name and domain pattern (use `<placeholder>` for the real
  subdomain).
- Identity method selected (e.g., "one-time PIN").
- Session duration selected.
- Confirmation that the unauthenticated smoke test was denied.
- Confirmation that the non-allowlisted email smoke test was denied.
- Confirmation that the allowlisted test email could reach the app landing page
  and `/health`.
- Confirmation that no QNAP management port or internal service is reachable
  through the tunnel.
- Confirmation that Dream Machine Pro port forwarding was not configured.
- Confirmation that `CCLD_HOSTED_TESTER_AUTH_MODE=production` and
  `CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH=disabled` remain in the deployment `.env`.
- Date the tunnel was created and Access was confirmed blocking.

---

## 11. Rollback: Disable the Public Route and Remove the Tunnel

To take the app back to LAN-only at any time:

1. In the Cloudflare dashboard, go to **Zero Trust â†’ Tunnels**, select the
   tunnel, and delete the public hostname for the pilot subdomain. This removes
   the public route and the CNAME DNS record. The QNAP LAN service and
   containers are not affected.
2. Alternatively, delete the entire tunnel. This disconnects all connectors and
   removes all public hostname routes.
3. Stop and remove the `cloudflared` container on the QNAP host:
   ```bash
   docker stop cloudflared && docker rm cloudflared
   ```
4. Confirm the pilot URL is no longer reachable from outside the LAN.
5. Record the rollback date and reason in local operator notes.

The app containers, PostgreSQL, and all QNAP-local data are unaffected by
tunnel rollback. Rollback does not remove tester data or reset the database.

---

## 12. Relationship to the App Auth Boundary

Cloudflare Access is a network-layer access control at the edge. It is not the
app's authentication, authorization, or session layer.

| Concern | Responsibility |
|---|---|
| Who can reach the pilot URL from the internet | Cloudflare Access (email allowlist) |
| App production auth mode (blocks anonymous workflow routes) | `CCLD_HOSTED_TESTER_AUTH_MODE=production` in `.env` |
| Real OIDC login, sessions, user tables, role enforcement | Deferred â€” not yet implemented |
| Raw source data, reviewer-created state, audit boundaries | App data model (ADRs 0008â€“0015) |
| QNAP host, containers, volumes, database | QNAP operator responsibility |

Do not tell testers that Cloudflare Access is their login. Testers should
understand that protected workflow routes inside the app (such as
`/ccld/records/request` and `/reviewer`) will show a sign-in-required page
until the app's own OIDC login is implemented.

---

## 13. Do-Not-Do List

- Do not commit tunnel tokens, Cloudflare credentials, private hostnames,
  account IDs, zone IDs, tester email addresses, or Access policy secrets.
- Do not configure Dream Machine Pro port forwarding for the app.
- Do not add a public hostname route for any QNAP admin, SSH, SMB, NAS,
  Container Station, Docker socket, or database service.
- Do not share the pilot URL before Cloudflare Access is confirmed blocking.
- Do not treat Cloudflare Access as a replacement for the app's hosted auth
  boundary.
- Do not configure the tunnel to proxy the entire QNAP host or all ports.
- Do not use `CCLD_RETRIEVAL_DEMO_MODE=mock-success` in the QNAP pilot
  deployment.
- Do not make public-source completeness, legal, facility-wide, harm, abuse,
  neglect, liability, or rights-deprivation conclusions from pilot evidence.

