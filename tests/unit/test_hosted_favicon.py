from __future__ import annotations

from pathlib import Path

import pytest

from ccld_complaints.hosted_app.app import route_response
from ccld_complaints.hosted_app.auth import (
    HostedAuthRuntimeConfig,
    load_hosted_auth_runtime_config,
)

ROOT = Path(__file__).resolve().parents[2]
FAVICON_FILE = ROOT / "src" / "ccld_complaints" / "hosted_app" / "static" / "favicon.ico"
FAVICON_LINK = '<link rel="icon" href="/favicon.ico" sizes="any" type="image/x-icon">'


@pytest.fixture
def local_dev_auth_config() -> HostedAuthRuntimeConfig:
    return load_hosted_auth_runtime_config(
        environ={
            "CCLD_HOSTED_TESTER_AUTH_MODE": "local-dev",
            "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH": "enabled",
        }
    )


def test_favicon_route_serves_canonical_icon() -> None:
    status, content_type, body = route_response("/favicon.ico")

    assert status == 200
    assert content_type == "image/x-icon"
    assert body == FAVICON_FILE.read_bytes()


@pytest.mark.parametrize(
    "path",
    (
        "/",
        "/reviewer",
        "/auth/login",
        "/source-records",
    ),
)
def test_server_rendered_pages_use_one_shared_canonical_favicon_reference(
    path: str,
    local_dev_auth_config: HostedAuthRuntimeConfig,
) -> None:
    status, content_type, body = route_response(
        path,
        auth_runtime_config=local_dev_auth_config,
        page_data_mode="fixture-demo",
    )

    assert status == 200
    assert content_type == "text/html; charset=utf-8"
    assert body.decode("utf-8").count(FAVICON_LINK) == 1
