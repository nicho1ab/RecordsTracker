from __future__ import annotations

from pathlib import Path

from ccld_complaints.storage.sqlite import initialize_database


def main() -> None:
    initialize_database(Path("data/processed/ccld.sqlite"))
    print("Initialized data/processed/ccld.sqlite")


if __name__ == "__main__":
    main()
