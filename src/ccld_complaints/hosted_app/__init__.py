"""Local hosted tester MVP scaffold package."""

from __future__ import annotations

from typing import Any

__all__ = ["APP_NAME", "health_response", "render_app_shell"]


def __getattr__(name: str) -> Any:
    """Preserve package exports without eagerly importing the full hosted app."""

    if name not in __all__:
        raise AttributeError(name)
    from ccld_complaints.hosted_app import app

    return getattr(app, name)
