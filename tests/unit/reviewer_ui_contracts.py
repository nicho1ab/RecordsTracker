"""Outcome-based reusable reviewer UI contract assertions."""
# ruff: noqa: E501

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

SUPPORTED_ACTION_KINDS = frozenset({"get", "external", "mutation"})
PROHIBITED_INFORMATION_TIER_TERMS = frozenset(
    {"validated-load", "pipeline command", "sqlite", "connection string", "operator mutation"}
)
NO_ANNOUNCEMENT_HELP_TYPES = frozenset({"static-inline-definition"})
KNOWN_INFORMATION_TIER_EXCEPTION_TERMS = MappingProxyType(
    {"RT-RC-002-sqlite": frozenset({"sqlite"})}
)
KNOWN_DUPLICATION_EXCEPTION_IDS = frozenset({"RT-RC-006-distinct-purpose"})


@dataclass(frozen=True)
class InformationTierException:
    """A narrowly governed exception to one protected information-tier term."""

    exception_id: str
    reason: str
    allowed_terms: frozenset[str]


@dataclass(frozen=True)
class DuplicationException:
    """A narrowly governed duplicate-representation exception."""

    exception_id: str
    reason: str
    representation_id: str
    duplicate_of_id: str
    section_id: str


class ReviewerContractError(AssertionError):
    """A durable reviewer-facing outcome was not preserved."""


def _required_text(value: object, description: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewerContractError(f"{description} is required")
    return value


def _validated_information_exception(exception: InformationTierException) -> frozenset[str]:
    exception_id = _required_text(exception.exception_id, "information-tier exception ID")
    _required_text(exception.reason, "information-tier exception reason")
    governed_terms = KNOWN_INFORMATION_TIER_EXCEPTION_TERMS.get(exception_id)
    if governed_terms is None:
        raise ReviewerContractError("information-tier exception ID is not governed")
    if exception.allowed_terms != governed_terms:
        raise ReviewerContractError("information-tier exception does not match its governed terms")
    return exception.allowed_terms


def _validated_duplication_exception(exception: DuplicationException) -> None:
    if exception.exception_id not in KNOWN_DUPLICATION_EXCEPTION_IDS:
        raise ReviewerContractError("duplication exception ID is not governed")
    _required_text(exception.reason, "duplication exception reason")
    _required_text(exception.representation_id, "duplication exception representation ID")
    _required_text(exception.duplicate_of_id, "duplication exception duplicate-of ID")
    _required_text(exception.section_id, "duplication exception section ID")


def assert_destinations(actions: Iterable[Mapping[str, object]], get: Callable[[str], int]) -> None:
    for action in actions:
        kind = action.get("kind")
        if not isinstance(kind, str) or kind not in SUPPORTED_ACTION_KINDS:
            raise ReviewerContractError("action kind is missing or unsupported")
        state = action.get("state", "available")
        if state == "unavailable":
            _required_text(action.get("unavailable_reason"), "unavailable action reason")
            if action.get("destination") or action.get("mutation_path") or action.get("usable") is True:
                raise ReviewerContractError("unavailable action exposes a usable destination or mutation path")
            if kind == "external" and not action.get("provenance"):
                raise ReviewerContractError("unavailable external action lacks governed provenance")
            continue
        if kind == "external":
            if not action.get("provenance"):
                raise ReviewerContractError("external action lacks governed provenance")
            continue
        if kind == "mutation":
            if action.get("success") is not True or action.get("failure") is not True:
                raise ReviewerContractError("mutation lacks success and failure contract")
            continue
        status = get(str(action.get("destination")))
        if 300 <= status < 400 and action.get("redirect_allowed"):
            continue
        if status < 200 or status >= 400:
            raise ReviewerContractError("internal action destination is unusable")


def assert_information_tier(text: str, *, exception: InformationTierException | None = None) -> None:
    allowed_terms = frozenset() if exception is None else _validated_information_exception(exception)
    lowered = text.casefold()
    for phrase in PROHIBITED_INFORMATION_TIER_TERMS:
        if phrase in lowered and phrase not in allowed_terms:
            raise ReviewerContractError(f"reviewer information tier exposes {phrase}")


def assert_help_surface(surfaces: Sequence[Mapping[str, object]], *, escape_supported: bool) -> None:
    active = [surface for surface in surfaces if surface.get("active")]
    if len(active) > 1 or (active and not active[0].get("focus")):
        raise ReviewerContractError("help surface collision or accessibility state")
    if not active:
        return
    surface = active[0]
    announcement_mode = surface.get("announcement_mode", "required")
    announcements = surface.get("announcements")
    if isinstance(announcements, bool) or not isinstance(announcements, int):
        raise ReviewerContractError("help announcement evidence is missing or malformed")
    if announcement_mode == "required" and announcements != 1:
        raise ReviewerContractError("help surface requires exactly one announcement")
    if announcement_mode == "not-required":
        if surface.get("help_type") not in NO_ANNOUNCEMENT_HELP_TYPES or announcements != 0:
            raise ReviewerContractError("help no-announcement mode is not governed")
    elif announcement_mode != "required":
        raise ReviewerContractError("help announcement mode is unsupported")
    if escape_supported and not surface.get("escape_dismisses"):
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
    seen: dict[tuple[object, ...], str] = {}
    for representation in representations:
        raw_rows = representation.get("rows", ())
        rows: tuple[object, ...] = tuple(raw_rows) if isinstance(raw_rows, Iterable) else ()
        representation_id = str(representation.get("representation_id", ""))
        if rows in seen:
            exception = representation.get("duplication_exception")
            if not isinstance(exception, DuplicationException):
                raise ReviewerContractError("result set duplicated without governed exception")
            _validated_duplication_exception(exception)
            if (
                exception.representation_id != representation_id
                or exception.duplicate_of_id != seen[rows]
                or exception.section_id != representation.get("section_id")
            ):
                raise ReviewerContractError("duplication exception does not match the duplicated representation")
        else:
            if not representation_id:
                raise ReviewerContractError("representation ID is required")
            seen[rows] = representation_id
    if any(section.get("empty") and not section.get("consolidated") for section in sections):
        raise ReviewerContractError("empty decision section was rendered")
