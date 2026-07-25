"""Outcome-based reusable reviewer UI contract assertions."""
# ruff: noqa: E501

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence


class ReviewerContractError(AssertionError):
    """A durable reviewer-facing outcome was not preserved."""


def assert_destinations(actions: Iterable[Mapping[str, object]], get: Callable[[str], int]) -> None:
    for action in actions:
        state = action.get("state", "available")
        if state == "unavailable":
            continue
        if action.get("kind") == "external":
            if not action.get("provenance"):
                raise ReviewerContractError("external action lacks governed provenance")
            continue
        if action.get("kind") == "mutation":
            if action.get("success") is not True or action.get("failure") is not True:
                raise ReviewerContractError("mutation lacks success and failure contract")
            continue
        status = get(str(action.get("destination")))
        if 300 <= status < 400 and action.get("redirect_allowed"):
            continue
        if status < 200 or status >= 400:
            raise ReviewerContractError("internal action destination is unusable")


def assert_information_tier(text: str, *, authorized: Sequence[str] = ()) -> None:
    forbidden = ("validated-load", "pipeline command", "sqlite", "connection string", "operator mutation")
    lowered = text.casefold()
    for phrase in forbidden:
        if phrase in lowered and phrase not in {value.casefold() for value in authorized}:
            raise ReviewerContractError(f"reviewer information tier exposes {phrase}")


def assert_help_surface(surfaces: Sequence[Mapping[str, object]], *, escape_supported: bool) -> None:
    active = [surface for surface in surfaces if surface.get("active")]
    if len(active) > 1 or (active and not active[0].get("focus")) or (active and active[0].get("announcements", 1) != 1):
        raise ReviewerContractError("help surface collision or accessibility state")
    if active and escape_supported and not active[0].get("escape_dismisses"):
        raise ReviewerContractError("dismissible help surface lacks Escape behavior")


def assert_facility_identity(records: Iterable[Mapping[str, object]]) -> None:
    current: dict[str, str] = {}
    for record in records:
        if record.get("explanation") in {"unavailable", "historical", "conflict"}:
            continue
        facility_id, name = str(record["facility_id"]), str(record["name"])
        if not name.strip():
            raise ReviewerContractError("current facility identity is blank")
        if facility_id in current and current[facility_id] != name:
            raise ReviewerContractError("conflicting current facility identity")
        current[facility_id] = name


def assert_continuity(before: Mapping[str, object], after: Mapping[str, object]) -> None:
    for key in ("selection", "focus", "context"):
        if before.get(key) != after.get(key):
            raise ReviewerContractError(f"continuity lost for {key}")


def assert_actions(actions: Sequence[Mapping[str, object]]) -> None:
    ordered = sorted(actions, key=lambda action: int(str(action["order"])))
    if list(actions) != ordered or any(not action.get("visible") or not action.get("keyboard") for action in actions):
        raise ReviewerContractError("action visibility, order, or keyboard contract failed")
    for left, right in zip(ordered, ordered[1:], strict=False):
        tolerance = float(str(left.get("overlap_tolerance", 0)))
        if float(str(left["right"])) > float(str(right["left"])) + tolerance:
            raise ReviewerContractError("actions overlap")


def assert_result_structure(representations: Sequence[Mapping[str, object]], sections: Sequence[Mapping[str, object]]) -> None:
    seen: set[tuple[object, ...]] = set()
    for representation in representations:
        raw_rows = representation.get("rows", ())
        rows: tuple[object, ...] = tuple(raw_rows) if isinstance(raw_rows, Iterable) else ()
        if rows in seen and not (representation.get("distinct_purpose") or representation.get("registry_exception")):
            raise ReviewerContractError("result set duplicated without distinct purpose")
        seen.add(rows)
    if any(section.get("empty") and not section.get("consolidated") for section in sections):
        raise ReviewerContractError("empty decision section was rendered")
