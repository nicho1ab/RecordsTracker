from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class SourceDocument:
    source_url: str
    raw_path: Path
    raw_sha256: str
    content_type: str | None = None


class SourceConnector(Protocol):
    connector_name: str
    connector_version: str

    def discover(self) -> list[str]: ...

    def fetch(self, source_url: str) -> bytes: ...

    def store_raw(self, source_url: str, content: bytes) -> SourceDocument: ...

    def extract(self, document: SourceDocument) -> dict[str, object]: ...

    def normalize(self, extracted: dict[str, object]) -> dict[str, object]: ...

    def validate(self, normalized: dict[str, object]) -> None: ...

    def emit(self, normalized: dict[str, object]) -> None: ...
