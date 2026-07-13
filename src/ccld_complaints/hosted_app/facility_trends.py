from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta

COMPLETE_PERIOD = "Complete period"
INCOMPLETE_CURRENT_PERIOD = "Incomplete current period"
ZERO_QUALIFYING_RECORDS = "Zero qualifying records"
COVERAGE_UNAVAILABLE = "Coverage unavailable"
DATE_UNAVAILABLE = "Date unavailable"

NO_ANOMALY_CUE = "No anomaly cue"
INCREASED_ACTIVITY = "Increased activity"
NEW_ACTIVITY = "New activity"
DECREASED_ACTIVITY = "Decreased activity"


@dataclass(frozen=True)
class FacilityTrendComplaint:
    stable_complaint_id: str
    source_record_key: str
    complaint_control_number: str
    facility_number: str
    facility_name: str
    facility_type: str
    geography: str
    complaint_date: date | None
    finding: str
    substantiated: bool
    serious_topics: tuple[str, ...]
    detail_href: str
    source_available: bool = True


@dataclass(frozen=True)
class FacilityTrendFilters:
    start_date: date | None = None
    end_date: date | None = None
    date_dimension: str = "complaint_received_date"
    facility: str = ""
    facility_type: str = ""
    geography: str = ""
    finding: str = ""
    serious_topic: str = ""
    time_grain: str = "month"
    period_count: int = 12


@dataclass(frozen=True)
class FacilityTrendPeriod:
    period_start: date
    period_end: date
    complaint_count: int
    substantiated_count: int
    serious_topic_count: int
    coverage_state: str
    comparable: bool
    anomaly_cue: str = NO_ANOMALY_CUE
    preceding_complaint_count: int | None = None
    complaints: tuple[FacilityTrendComplaint, ...] = ()


@dataclass(frozen=True)
class FacilityTrendResult:
    periods: tuple[FacilityTrendPeriod, ...]
    date_unavailable_complaints: tuple[FacilityTrendComplaint, ...]
    qualifying_complaint_count: int
    dated_qualifying_complaint_count: int


def build_facility_trend(
    complaints: list[FacilityTrendComplaint],
    filters: FacilityTrendFilters,
    *,
    today: date,
) -> FacilityTrendResult:
    base_complaints = [
        complaint
        for complaint in complaints
        if _base_filter_matches(complaint, filters)
    ]
    qualifying = [
        complaint
        for complaint in base_complaints
        if _qualifying_filter_matches(complaint, filters)
    ]
    date_unavailable = tuple(
        sorted(
            (complaint for complaint in qualifying if complaint.complaint_date is None),
            key=_complaint_sort_key,
        )
    )
    natural_periods = _periods_for_filters(filters, today=today)
    displayed_range_start = max(
        natural_periods[0][0],
        filters.start_date or natural_periods[0][0],
    )
    displayed_range_end = min(
        natural_periods[-1][1],
        filters.end_date or natural_periods[-1][1],
    )
    dated_qualifying = [
        complaint
        for complaint in qualifying
        if complaint.complaint_date is not None
        and displayed_range_start <= complaint.complaint_date <= displayed_range_end
    ]
    dated_base = [
        complaint
        for complaint in base_complaints
        if complaint.complaint_date is not None
    ]
    coverage_start, coverage_end = _coverage_period_bounds(
        dated_base,
        filters.time_grain,
    )
    periods: list[FacilityTrendPeriod] = []
    for natural_start, natural_end in natural_periods:
        displayed_start = max(
            natural_start,
            filters.start_date or natural_start,
        )
        displayed_end = min(
            natural_end,
            filters.end_date or natural_end,
        )
        period_complaints = tuple(
            sorted(
                (
                    complaint
                    for complaint in dated_qualifying
                    if complaint.complaint_date is not None
                    and displayed_start <= complaint.complaint_date <= displayed_end
                ),
                key=_complaint_sort_key,
            )
        )
        is_current = natural_start <= today <= natural_end
        coverage_available = (
            coverage_start is not None
            and coverage_end is not None
            and coverage_start <= natural_start <= coverage_end
        )
        is_full_period = (
            displayed_start == natural_start and displayed_end == natural_end
        )
        comparable = bool(
            not is_current
            and natural_end < today
            and coverage_available
            and is_full_period
        )
        if is_current:
            coverage_state = INCOMPLETE_CURRENT_PERIOD
        elif not coverage_available:
            coverage_state = COVERAGE_UNAVAILABLE
        elif not period_complaints:
            coverage_state = ZERO_QUALIFYING_RECORDS
        else:
            coverage_state = COMPLETE_PERIOD
        periods.append(
            FacilityTrendPeriod(
                period_start=displayed_start,
                period_end=displayed_end,
                complaint_count=len(period_complaints),
                substantiated_count=sum(
                    complaint.substantiated for complaint in period_complaints
                ),
                serious_topic_count=sum(
                    bool(complaint.serious_topics) for complaint in period_complaints
                ),
                coverage_state=coverage_state,
                comparable=comparable,
                complaints=period_complaints,
            )
        )
    periods = _apply_anomaly_rules(periods)
    return FacilityTrendResult(
        periods=tuple(periods),
        date_unavailable_complaints=date_unavailable,
        qualifying_complaint_count=len(dated_qualifying) + len(date_unavailable),
        dated_qualifying_complaint_count=len(dated_qualifying),
    )


def _apply_anomaly_rules(
    periods: list[FacilityTrendPeriod],
) -> list[FacilityTrendPeriod]:
    result: list[FacilityTrendPeriod] = []
    for index, current in enumerate(periods):
        previous = periods[index - 1] if index else None
        preceding_count = previous.complaint_count if previous is not None else None
        cue = NO_ANOMALY_CUE
        if previous is not None and current.comparable and previous.comparable:
            if current.complaint_count >= 3 and previous.complaint_count == 0:
                cue = NEW_ACTIVITY
            elif (
                current.complaint_count >= 3
                and current.complaint_count >= 2 * previous.complaint_count
            ):
                cue = INCREASED_ACTIVITY
            elif (
                previous.complaint_count >= 3
                and current.complaint_count * 2 <= previous.complaint_count
            ):
                cue = DECREASED_ACTIVITY
        result.append(
            replace(
                current,
                anomaly_cue=cue,
                preceding_complaint_count=preceding_count,
            )
        )
    return result


def _base_filter_matches(
    complaint: FacilityTrendComplaint,
    filters: FacilityTrendFilters,
) -> bool:
    if filters.facility and not _contains_filter(
        filters.facility,
        (
            complaint.facility_name,
            complaint.facility_number,
            complaint.stable_complaint_id,
            complaint.complaint_control_number,
        ),
    ):
        return False
    if filters.facility_type and not _contains_filter(
        filters.facility_type,
        (complaint.facility_type,),
    ):
        return False
    return not filters.geography or _contains_filter(
        filters.geography,
        (complaint.geography,),
    )


def _qualifying_filter_matches(
    complaint: FacilityTrendComplaint,
    filters: FacilityTrendFilters,
) -> bool:
    if filters.finding and _normalized_text(filters.finding) != _normalized_text(
        complaint.finding
    ):
        return False
    return not filters.serious_topic or _contains_filter(
        filters.serious_topic,
        complaint.serious_topics,
    )


def _contains_filter(filter_value: str, values: tuple[str, ...]) -> bool:
    needle = _normalized_text(filter_value)
    return any(needle in _normalized_text(value) for value in values)


def _normalized_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _coverage_period_bounds(
    complaints: list[FacilityTrendComplaint],
    grain: str,
) -> tuple[date | None, date | None]:
    dates = [complaint.complaint_date for complaint in complaints]
    valid_dates = [value for value in dates if value is not None]
    if not valid_dates:
        return None, None
    return _period_start(min(valid_dates), grain), _period_start(max(valid_dates), grain)


def _periods_for_filters(
    filters: FacilityTrendFilters,
    *,
    today: date,
) -> list[tuple[date, date]]:
    grain = "quarter" if filters.time_grain == "quarter" else "month"
    period_count = max(1, min(filters.period_count, 24))
    if filters.end_date is not None:
        final_start = _period_start(filters.end_date, grain)
    elif filters.start_date is not None:
        final_start = _shift_period(
            _period_start(filters.start_date, grain),
            grain,
            period_count - 1,
        )
    else:
        final_start = _period_start(today, grain)
    first_start = (
        _period_start(filters.start_date, grain)
        if filters.start_date is not None
        else _shift_period(final_start, grain, -(period_count - 1))
    )
    starts: list[date] = []
    current = first_start
    while current <= final_start and len(starts) < period_count:
        starts.append(current)
        current = _shift_period(current, grain, 1)
    return [(start, _period_end(start, grain)) for start in starts]


def _period_start(value: date, grain: str) -> date:
    if grain == "quarter":
        quarter_month = ((value.month - 1) // 3) * 3 + 1
        return date(value.year, quarter_month, 1)
    return date(value.year, value.month, 1)


def _period_end(start: date, grain: str) -> date:
    return _shift_period(start, grain, 1) - timedelta(days=1)


def _shift_period(start: date, grain: str, count: int) -> date:
    month_delta = count * (3 if grain == "quarter" else 1)
    month_index = start.year * 12 + start.month - 1 + month_delta
    return date(month_index // 12, month_index % 12 + 1, 1)


def _complaint_sort_key(complaint: FacilityTrendComplaint) -> tuple[str, str]:
    return complaint.stable_complaint_id, complaint.source_record_key
