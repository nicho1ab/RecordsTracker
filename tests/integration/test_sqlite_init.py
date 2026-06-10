from pathlib import Path

from ccld_complaints.storage.sqlite import initialize_database


def test_initialize_database(tmp_path: Path) -> None:
    db = tmp_path / "test.sqlite"
    initialize_database(db)
    assert db.exists()
