from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from ccld_complaints.local_sample import populate_sample_database
from ccld_complaints.utils.hash import sha256_bytes

SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def test_source_document_hashes_are_present_sha256_hex(tmp_path: Path) -> None:
    db_path = tmp_path / "ccld.sqlite"

    populate_sample_database(db_path)

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT document_id, raw_sha256
            FROM source_documents
            ORDER BY document_id
            """
        ).fetchall()

    assert rows
    for document_id, raw_sha256 in rows:
        assert isinstance(raw_sha256, str), document_id
        assert SHA256_HEX_PATTERN.fullmatch(raw_sha256), document_id


def test_source_document_hashes_match_preserved_raw_files(tmp_path: Path) -> None:
    db_path = tmp_path / "ccld.sqlite"

    populate_sample_database(db_path)

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT document_id, raw_path, raw_sha256
            FROM source_documents
            WHERE raw_path IS NOT NULL
            ORDER BY document_id
            """
        ).fetchall()

    assert rows
    for document_id, raw_path, raw_sha256 in rows:
        assert Path(raw_path).exists(), document_id
        assert sha256_bytes(Path(raw_path).read_bytes()) == raw_sha256, document_id
