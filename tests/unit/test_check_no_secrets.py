from __future__ import annotations

import importlib.util
from collections.abc import Callable
from pathlib import Path
from typing import cast


def load_should_skip_path() -> Callable[[Path], bool]:
    script_path = Path(__file__).parents[2] / "scripts" / "check_no_secrets.py"
    spec = importlib.util.spec_from_file_location("check_no_secrets", script_path)
    if spec is None or spec.loader is None:
        raise AssertionError("Could not load check_no_secrets.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(Callable[[Path], bool], module.should_skip_path)


def test_should_skip_virtual_environment_directories() -> None:
    should_skip_path = load_should_skip_path()

    assert should_skip_path(Path(".venv/Lib/site-packages/example.py")) is True
    assert should_skip_path(Path(".venv313/Lib/site-packages/example.py")) is True
    assert should_skip_path(Path("src/ccld_complaints/hosted_app/local_check.py")) is False