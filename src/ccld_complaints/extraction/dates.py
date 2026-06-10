from __future__ import annotations

from datetime import date

from dateutil import parser


def parse_source_date(value: str | None) -> date | None:
    if value is None:
        return None

    cleaned = value.strip()
    if cleaned == "":
        return None

    return parser.parse(cleaned).date()


def parse_date_or_none(value: str | None) -> date | None:
    return parse_source_date(value)


def days_between(start_date: date | None, end_date: date | None) -> int | None:
    if start_date is None or end_date is None:
        return None

    return (end_date - start_date).days
