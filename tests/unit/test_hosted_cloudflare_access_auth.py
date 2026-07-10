from __future__ import annotations

import base64
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from ccld_complaints.hosted_app.app import route_response
from ccld_complaints.hosted_app.auth import (
    AUTH_MODE_ENV,
    AUTH_PROVIDER_CLASS_ENV,
    CLOUDFLARE_ACCESS_ALLOWED_EMAIL_DOMAINS_ENV,
    CLOUDFLARE_ACCESS_ALLOWED_EMAILS_ENV,
    CLOUDFLARE_ACCESS_ASSERTION_HEADER,
    CLOUDFLARE_ACCESS_AUD_ENV,
    CLOUDFLARE_ACCESS_PROVIDER_CLASS,
    CLOUDFLARE_ACCESS_TEAM_DOMAIN_ENV,
    LOCAL_DEV_AUTH_ENV,
    CloudflareAccessAuthError,
    HostedAuthConfigError,
    authenticate_cloudflare_access_token,
    load_hosted_auth_runtime_config,
)
from ccld_complaints.hosted_app.feedback import GitHubFeedbackConfig
from ccld_complaints.hosted_app.reviewer_ui import LOCAL_REVIEWER_UI_SCOPE

TEAM_DOMAIN = "example.cloudflareaccess.com"
AUDIENCE = "placeholder-aud-tag"
KID = "placeholder-key-id"
NOW = datetime(2026, 7, 10, 12, 0, 0, tzinfo=UTC)
RAW_ASSERTION_MARKER = "raw.jwt.must.not.render"


class MockGitHubIssueClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def create_issue(
        self,
        *,
        repo: str,
        token: str,
        title: str,
        body: str,
        labels: Sequence[str],
    ) -> Mapping[str, Any]:
        self.calls.append(
            {
                "repo": repo,
                "token": token,
                "title": title,
                "body": body,
                "labels": tuple(labels),
            }
        )
        return {"number": 101, "html_url": f"https://github.com/{repo}/issues/101"}


PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC_NUMBERS = PRIVATE_KEY.public_key().public_numbers()


def test_cloudflare_access_domain_allowed_jwt_enables_feedback_submission() -> None:
    client = MockGitHubIssueClient()
    token = _token(email="tester@example.invalid")

    status, _content_type, body = route_response(
        "/feedback",
        method="POST",
        request_body=_valid_form_bytes(),
        request_headers={CLOUDFLARE_ACCESS_ASSERTION_HEADER: token},
        auth_runtime_config=_cloudflare_auth_config(
            allowed_domains="example.invalid",
            allowed_emails="",
        ),
        feedback_context=None,
        github_feedback_config=_github_config(),
        github_feedback_client=client,
        cloudflare_jwks_fetcher=_jwks_fetcher,
        cloudflare_auth_now=NOW,
    )
    html = body.decode("utf-8")

    assert status == 201
    assert "Feedback submitted" in html
    assert len(client.calls) == 1


def test_cloudflare_access_exact_allowed_email_enables_feedback_with_mocked_github() -> None:
    client = MockGitHubIssueClient()
    token = _token(email="invited@another.invalid")

    status, _content_type, body = route_response(
        "/feedback",
        method="POST",
        request_body=_valid_form_bytes(),
        request_headers={CLOUDFLARE_ACCESS_ASSERTION_HEADER: token},
        auth_runtime_config=_cloudflare_auth_config(
            allowed_domains="",
            allowed_emails="invited@another.invalid",
        ),
        github_feedback_config=_github_config(),
        github_feedback_client=client,
        cloudflare_jwks_fetcher=_jwks_fetcher,
        cloudflare_auth_now=NOW,
    )
    html = body.decode("utf-8")

    assert status == 201
    assert "Feedback submitted" in html
    assert len(client.calls) == 1
    issue_body = client.calls[0]["body"]
    assert "Submitted by: Cloudflare Access tester" in issue_body
    for forbidden in (
        token,
        RAW_ASSERTION_MARKER,
        "invited@another.invalid",
        f"https://{TEAM_DOMAIN}",
        "provider_subject",
        "provider_issuer",
        "github-token-not-rendered",
    ):
        assert forbidden not in html
        assert forbidden not in issue_body


def test_cloudflare_access_missing_header_blocks_production_feedback() -> None:
    status, _content_type, body = route_response(
        "/feedback",
        method="POST",
        request_body=_valid_form_bytes(),
        request_headers={},
        auth_runtime_config=_cloudflare_auth_config(),
        cloudflare_jwks_fetcher=_jwks_fetcher,
        cloudflare_auth_now=NOW,
    )
    html = body.decode("utf-8")

    assert status == 401
    assert "Cloudflare Access sign-in required" in html
    assert "Cf-Access-Jwt-Assertion" not in html
    assert_no_secret_output(html)


def test_cloudflare_access_ignores_cookies_query_tokens_and_email_headers() -> None:
    status, _content_type, body = route_response(
        f"/feedback?{urlencode({'token': RAW_ASSERTION_MARKER})}",
        method="POST",
        request_body=_valid_form_bytes(),
        request_headers={
            "Cookie": f"CF_Authorization={RAW_ASSERTION_MARKER}",
            "Cf-Access-Authenticated-User-Email": "tester@example.invalid",
        },
        auth_runtime_config=_cloudflare_auth_config(),
        cloudflare_jwks_fetcher=_jwks_fetcher,
        cloudflare_auth_now=NOW,
    )
    html = body.decode("utf-8")

    assert status == 401
    assert RAW_ASSERTION_MARKER not in html
    assert "tester@example.invalid" not in html
    assert_no_secret_output(html)


@pytest.mark.parametrize(
    ("token_kwargs", "raw_token", "expected_message"),
    [
        ({}, "not-a-jwt", "not accepted"),
        (
            {"email": "tester@example.invalid", "expires_delta": timedelta(seconds=-1)},
            "",
            "expired",
        ),
        ({"email": "tester@example.invalid", "audience": "wrong-audience"}, "", "audience"),
        (
            {"email": "tester@example.invalid", "issuer": "https://wrong.example.invalid"},
            "",
            "issuer",
        ),
        ({"email": ""}, "", "missing a required claim"),
        ({"email": "tester@blocked.invalid"}, "", "email is not allowed"),
    ],
)
def test_cloudflare_access_invalid_assertions_are_blocked(
    token_kwargs: dict[str, Any],
    raw_token: str,
    expected_message: str,
) -> None:
    token = raw_token or _token(**token_kwargs)
    with pytest.raises(CloudflareAccessAuthError, match=expected_message):
        authenticate_cloudflare_access_token(
            token,
            _cloudflare_auth_config().cloudflare_access,
            scope=LOCAL_REVIEWER_UI_SCOPE,
            now=NOW,
            jwks_fetcher=_jwks_fetcher,
        )


def test_cloudflare_access_local_dev_actor_remains_disabled_in_production() -> None:
    with pytest.raises(HostedAuthConfigError, match="LOCAL_DEV_AUTH"):
        load_hosted_auth_runtime_config(
            environ={
                AUTH_MODE_ENV: "production",
                AUTH_PROVIDER_CLASS_ENV: CLOUDFLARE_ACCESS_PROVIDER_CLASS,
                LOCAL_DEV_AUTH_ENV: "enabled",
            }
        )


def test_cloudflare_access_status_summary_is_safe() -> None:
    config = _cloudflare_auth_config(allowed_domains="example.invalid,other.invalid")

    status, _content_type, body = route_response(
        "/auth/status",
        auth_runtime_config=config,
    )
    payload = json.loads(body.decode("utf-8"))
    serialized = json.dumps(payload, sort_keys=True)

    assert status == 200
    assert payload["auth"]["provider_class"] == "cloudflare-access"
    assert payload["auth"]["cloudflare_access"] == {
        "team_domain_configured": True,
        "aud_configured": True,
        "allowed_email_domain_count": 2,
        "allowed_exact_email_count": 1,
        "jwks_cache_seconds": 0,
        "assertion_header": "Cf-Access-Jwt-Assertion",
    }
    for forbidden in (
        TEAM_DOMAIN,
        AUDIENCE,
        "allowed@example.invalid",
        "example.invalid",
        RAW_ASSERTION_MARKER,
    ):
        assert forbidden not in serialized


def _github_config() -> GitHubFeedbackConfig:
    credential = "github-" + "token-" + "not-rendered"
    return GitHubFeedbackConfig(
        repo="example/repo",
        token=credential,
        default_labels=("pilot",),
    )


def _cloudflare_auth_config(
    *,
    allowed_domains: str = "example.invalid",
    allowed_emails: str = "allowed@example.invalid",
) -> Any:
    return load_hosted_auth_runtime_config(
        environ={
            AUTH_MODE_ENV: "production",
            AUTH_PROVIDER_CLASS_ENV: CLOUDFLARE_ACCESS_PROVIDER_CLASS,
            CLOUDFLARE_ACCESS_TEAM_DOMAIN_ENV: TEAM_DOMAIN,
            CLOUDFLARE_ACCESS_AUD_ENV: AUDIENCE,
            CLOUDFLARE_ACCESS_ALLOWED_EMAIL_DOMAINS_ENV: allowed_domains,
            CLOUDFLARE_ACCESS_ALLOWED_EMAILS_ENV: allowed_emails,
            "CCLD_CLOUDFLARE_ACCESS_JWKS_CACHE_SECONDS": "0",
        }
    )


def _token(
    *,
    email: str,
    audience: str = AUDIENCE,
    issuer: str = f"https://{TEAM_DOMAIN}",
    expires_delta: timedelta = timedelta(minutes=5),
) -> str:
    claims: dict[str, object] = {
        "iss": issuer,
        "aud": audience,
        "exp": int((NOW + expires_delta).timestamp()),
        "nbf": int((NOW - timedelta(minutes=1)).timestamp()),
        "email": email,
        "raw_marker": RAW_ASSERTION_MARKER,
    }
    if not email:
        claims.pop("email")
    header = {"alg": "RS256", "typ": "JWT", "kid": KID}
    signing_input = (
        f"{_b64url_json(header)}.{_b64url_json(claims)}".encode("ascii")
    )
    signature = PRIVATE_KEY.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{signing_input.decode('ascii')}.{_b64url(signature)}"


def _valid_form_bytes() -> bytes:
    return urlencode(
        {
            "feedback_type": "Bug/problem",
            "description": "The feedback path worked after Cloudflare Access sign-in.",
            "page_path": "/feedback",
        }
    ).encode("utf-8")


def _jwks_fetcher(url: str) -> Mapping[str, Any]:
    assert url == f"https://{TEAM_DOMAIN}/cdn-cgi/access/certs"
    return {
        "keys": [
            {
                "kty": "RSA",
                "kid": KID,
                "use": "sig",
                "alg": "RS256",
                "n": _b64url_uint(PUBLIC_NUMBERS.n),
                "e": _b64url_uint(PUBLIC_NUMBERS.e),
            }
        ]
    }


def _b64url_json(value: Mapping[str, object]) -> str:
    return _b64url(json.dumps(value, separators=(",", ":"), sort_keys=True).encode())


def _b64url_uint(value: int) -> str:
    return _b64url(value.to_bytes((value.bit_length() + 7) // 8, byteorder="big"))


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def assert_no_secret_output(markup: str) -> None:
    lowered = markup.casefold()
    for marker in (
        RAW_ASSERTION_MARKER,
        "authorization",
        "cookie",
        "provider_subject",
        "provider_issuer",
        "github-token-not-rendered",
    ):
        assert marker not in lowered

