from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import validate as jsonschema_validate


def validate_schema(record: dict[str, Any], schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema_validate(instance=record, schema=schema)
