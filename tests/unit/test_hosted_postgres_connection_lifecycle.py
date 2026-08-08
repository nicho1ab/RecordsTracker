from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlencode

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, event, func, select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.pool import QueuePool

from ccld_complaints.hosted_app import app as hosted_app
from ccld_complaints.hosted_app.reviewer_created_state import (
    hosted_reviewer_created_state,
)
from ccld_complaints.hosted_app.reviewer_ui import (
    REVIEWER_UI_PREFIX,
    REVIEWER_UI_UPDATE_PATH,
)
from ccld_complaints.hosted_app.seeded_import import (
    hosted_seeded_import_metadata,
    import_seeded_corpus_artifact,
    load_seeded_corpus_artifact,
)

FIXTURE = Path("tests/fixtures/hosted_seeded_corpus/validated_seeded_corpus.json")
SOURCE_RECORD_KEY = "complaint:ccld:complaint:32-CR-20220407124448"


def test_default_postgres_engine_is_created_once_under_concurrent_access(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine = _seeded_engine(tmp_path)
    create_count = 0
    count_lock = threading.Lock()

    def create_once(_database_url: str) -> Engine:
        nonlocal create_count
        with count_lock:
            create_count += 1
        time.sleep(0.02)
        return engine

    monkeypatch.setattr(hosted_app, "_DEFAULT_POSTGRES_ENGINE", None)
    monkeypatch.setattr(
        hosted_app,
        "load_hosted_database_config",
        lambda: SimpleNamespace(database_url="postgresql://example.invalid/records"),
    )
    monkeypatch.setattr(hosted_app, "create_engine", create_once)

    try:
        with ThreadPoolExecutor(max_workers=12) as executor:
            resolved = tuple(
                executor.map(
                    lambda _index: hosted_app._default_postgres_engine(),
                    range(24),
                )
            )

        assert create_count == 1
        assert all(item is engine for item in resolved)
    finally:
        hosted_app._dispose_default_postgres_engine()


def test_repeated_health_checks_reuse_engine_and_release_connections(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine = _seeded_engine(tmp_path)
    checkouts, checkins = _pool_event_counts(engine)
    monkeypatch.setattr(hosted_app, "_DEFAULT_POSTGRES_ENGINE", engine)
    monkeypatch.setattr(
        hosted_app,
        "create_engine",
        lambda _database_url: pytest.fail("health checks must reuse the process engine"),
    )

    for _ in range(25):
        assert hosted_app.health_response()["source_data_loaded"] is True
        assert engine.pool.checkedout() == 0

    assert checkouts[0] == 25
    assert checkins[0] == 25
    engine.dispose()


def test_repeated_successful_hosted_routes_release_request_connections(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine = _seeded_engine(tmp_path)
    checkouts, checkins = _pool_event_counts(engine)
    monkeypatch.setattr(hosted_app, "_DEFAULT_POSTGRES_ENGINE", engine)

    for _ in range(25):
        status, _content_type, _body = hosted_app.route_response(
            REVIEWER_UI_PREFIX,
            page_data_mode="postgres",
        )
        assert status == 200
        assert engine.pool.checkedout() == 0

    assert checkouts[0] == 25
    assert checkins[0] == 25
    engine.dispose()


def test_failed_hosted_route_rolls_back_before_connection_release(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine = _seeded_engine(tmp_path)
    marker_metadata = MetaData()
    markers = Table(
        "connection_lifecycle_markers",
        marker_metadata,
        Column("marker_id", Integer, primary_key=True),
    )
    marker_metadata.create_all(engine)
    captured_connections: list[Connection] = []
    monkeypatch.setattr(hosted_app, "_DEFAULT_POSTGRES_ENGINE", engine)

    def failing_route(
        _path: str,
        context: Any,
        **_kwargs: Any,
    ) -> tuple[int, str, bytes]:
        connection = context.workflow_shell_context.source_derived_api_context.connection
        captured_connections.append(connection)
        connection.execute(markers.insert().values(marker_id=1))
        raise RuntimeError("forced route failure")

    monkeypatch.setattr(hosted_app, "route_reviewer_ui_response", failing_route)

    with pytest.raises(RuntimeError, match="forced route failure"):
        hosted_app.route_response(REVIEWER_UI_PREFIX, page_data_mode="postgres")

    assert len(captured_connections) == 1
    assert captured_connections[0].closed is True
    assert engine.pool.checkedout() == 0
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(markers)) == 0
    engine.dispose()


def test_post_authorization_early_return_does_not_leave_idle_transaction(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine = _seeded_engine(tmp_path)
    rollback_count = [0]
    event.listen(
        engine,
        "rollback",
        lambda _connection: rollback_count.__setitem__(0, rollback_count[0] + 1),
    )
    monkeypatch.setattr(hosted_app, "_DEFAULT_POSTGRES_ENGINE", engine)

    status, _content_type, _body = hosted_app.route_response(
        REVIEWER_UI_UPDATE_PATH,
        method="POST",
        request_body=urlencode({"source_record_key": SOURCE_RECORD_KEY}).encode("utf-8"),
        page_data_mode="postgres",
    )

    assert status == 403
    assert rollback_count[0] == 1
    assert engine.pool.checkedout() == 0
    engine.dispose()


def _seeded_engine(tmp_path: Path) -> Engine:
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'hosted-connection-lifecycle.sqlite'}",
        poolclass=QueuePool,
        pool_size=2,
        max_overflow=0,
    )
    hosted_seeded_import_metadata.create_all(engine)
    hosted_reviewer_created_state.metadata.create_all(engine)
    with engine.begin() as connection:
        import_seeded_corpus_artifact(
            connection,
            load_seeded_corpus_artifact(FIXTURE),
        )
    return engine


def _pool_event_counts(engine: Engine) -> tuple[list[int], list[int]]:
    checkouts = [0]
    checkins = [0]
    event.listen(
        engine,
        "checkout",
        lambda *_args: checkouts.__setitem__(0, checkouts[0] + 1),
    )
    event.listen(
        engine,
        "checkin",
        lambda *_args: checkins.__setitem__(0, checkins[0] + 1),
    )
    return checkouts, checkins
