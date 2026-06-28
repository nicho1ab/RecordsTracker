# ruff: noqa: E501

from __future__ import annotations

import html
from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class FacilityCaseBriefRecord:
    source_record_key: str
    detail_href: str
    complaint_control_number: str
    finding: str
    complaint_received_date: str
    visit_date: str
    report_date: str
    date_signed: str
    facility_number: str
    facility_name: str
    has_source_traceability: bool
    reviewer_status: str | None
    reviewer_status_label: str | None
    reviewer_note_count: int
    delay_thresholds: tuple[int, ...]
    missing_first_activity_date: bool
    missing_visit_date: bool
    missing_report_date: bool
    missing_signed_date: bool
    report_date_used_as_proxy: bool
    order_index: int = 0


@dataclass(frozen=True)
class FacilityCaseBrief:
    facility_number: str
    facility_name: str
    date_range: str
    mode_label: str
    mode_badge_class: str
    records: tuple[FacilityCaseBriefRecord, ...]
    record_count_label: str = "Complaint records visible/imported"
    full_queue_href: str = "/reviewer"
    packet_preview_href: str | None = None
    packet_draft_href: str | None = None


def render_facility_case_brief(brief: FacilityCaseBrief) -> str:
    if not brief.records:
        return ""
    priority = select_priority_record(brief.records)
    flag_counts = review_flag_counts(brief.records)
    findings = finding_counts(brief.records)
    source_traceability_count = sum(1 for record in brief.records if record.has_source_traceability)
    reviewer_state_count = sum(
        1
        for record in brief.records
        if record.reviewer_note_count > 0 or record.reviewer_status is not None
    )
    flag_count = sum(1 for record in brief.records if has_review_flag(record))
    facility_label = brief.facility_name if brief.facility_name and brief.facility_name != "unknown" else "Facility"
    metric_cards = _metric_cards(
        (
            (brief.record_count_label, len(brief.records), True),
            ("Records with review flags", flag_count, True),
            ("Original source links saved", source_traceability_count, True),
            ("Reviewer-created notes/statuses", reviewer_state_count, True),
        )
    )
    flag_cards = _metric_cards(
        (
            ("Possible delay indicators", flag_counts["delay_any"], True),
            ("Over 30 days", flag_counts["delay_30"], flag_counts["delay_30"] > 0),
            ("Over 60 days", flag_counts["delay_60"], flag_counts["delay_60"] > 0),
            ("Over 90 days", flag_counts["delay_90"], flag_counts["delay_90"] > 0),
            ("Over 120 days", flag_counts["delay_120"], flag_counts["delay_120"] > 0),
            ("Missing first activity date", flag_counts["missing_first_activity"], flag_counts["missing_first_activity"] > 0),
            ("Missing local key dates", flag_counts["missing_key_date"], flag_counts["missing_key_date"] > 0),
            ("Needs source check", flag_counts["needs_source_check"], flag_counts["needs_source_check"] > 0),
            ("Proxy date cues", flag_counts["proxy_date"], flag_counts["proxy_date"] > 0),
        )
    )
    finding_items = "\n".join(
        f"            <li><span class=\"badge badge-muted\">{_escape(label)}: {count}</span></li>"
        for label, count in findings.items()
    )
    priority_reasons = "\n".join(
        f"                <li>{_escape(reason)}</li>" for reason in priority_reason_labels(priority)
    )
    priority_label = display_record_label(priority)
    packet_preview_action = (
        f'          <a class="button button-secondary" href="{_escape(brief.packet_preview_href)}">Open local/test packet preview</a>'
        if brief.packet_preview_href
        else ""
    )
    packet_draft_action = (
        f'          <a class="button button-secondary" href="{_escape(brief.packet_draft_href)}">Open local/test preparation draft for browser copy or print</a>'
        if brief.packet_draft_href
        else ""
    )
    return f"""<section class="hero-card facility-case-brief" aria-labelledby="facility-case-brief-heading">
      <div class="case-brief-header">
        <div>
          <p class="launch-kicker">Facility case brief</p>
          <h2 id="facility-case-brief-heading">{_escape(facility_label)}</h2>
          <p class="helper-text">Facility/license number: {_escape(brief.facility_number or 'unknown')}{_date_range_fragment(brief.date_range)}</p>
        </div>
      </div>
      <div class="metric-strip" aria-label="Facility review summary">
{metric_cards}
      </div>
      <section class="quiet-section" aria-labelledby="case-brief-flags-heading">
        <h3 id="case-brief-flags-heading">Review flags</h3>
        <div class="metric-strip" aria-label="Review flag summary">
{flag_cards}
        </div>
      </section>
      <section class="quiet-section" aria-labelledby="case-brief-findings-heading">
        <h3 id="case-brief-findings-heading">Findings represented</h3>
        <ul class="flag-list" aria-label="Source-derived findings represented">
{finding_items}
        </ul>
        <p class="helper-text">Findings are source-derived categories, not legal conclusions.</p>
      </section>
      <section class="summary-card" aria-labelledby="priority-record-heading">
        <h3 id="priority-record-heading">Suggested first record for review</h3>
        <p><strong>{_escape(priority_label)}</strong></p>
        <p>Why open this first:</p>
        <ul>
{priority_reasons}
        </ul>
        <div class="form-actions">
          <a class="button" href="{_escape(priority.detail_href)}">Open priority record</a>
          <a class="button button-secondary" href="{_escape(brief.full_queue_href)}">Open full queue</a>
{packet_preview_action}
    {packet_draft_action}
        </div>
      </section>
      <p class="helper-text">Use this summary to decide what to review first. Review flags are screening aids, not legal conclusions.</p>
    </section>"""


def render_record_flag_reason_section(record: FacilityCaseBriefRecord) -> str:
    reasons = priority_reason_labels(record)
    if not reasons:
        reasons = ("No review flags are visible from loaded source-derived fields.",)
    items = "\n".join(f"        <li>{_escape(reason)}</li>" for reason in reasons)
    return f"""<section class="summary-card" aria-labelledby="record-flag-reasons-heading">
      <h2 id="record-flag-reasons-heading">Why this record is flagged</h2>
      <p>These source-derived and reviewer-created cues explain why this complaint may need attorney review. They are screening aids, not legal conclusions.</p>
      <ul>
{items}
      </ul>
    </section>"""


def select_priority_record(records: tuple[FacilityCaseBriefRecord, ...]) -> FacilityCaseBriefRecord:
    return sorted(records, key=_priority_sort_key)[0]


def priority_reason_labels(record: FacilityCaseBriefRecord) -> tuple[str, ...]:
    reasons: list[str] = []
    if record.reviewer_status is None:
        reasons.append("No reviewer-created status recorded yet.")
    strongest_delay = max(record.delay_thresholds) if record.delay_thresholds else 0
    if strongest_delay:
        reasons.append(f"Possible delay indicator: over {strongest_delay} days")
    if record.missing_first_activity_date:
        reasons.append("Needs source check: first activity date missing locally")
    missing_dates = []
    if record.missing_visit_date:
        missing_dates.append("visit date")
    if record.missing_report_date:
        missing_dates.append("report date")
    if record.missing_signed_date:
        missing_dates.append("signed date")
    if missing_dates:
        reasons.append("Needs source check: " + ", ".join(missing_dates) + " not available locally")
    if record.report_date_used_as_proxy:
        reasons.append("Review flag: report date used as proxy")
    if record.has_source_traceability:
        reasons.append("Original CCLD source link saved")
    if record.finding and record.finding != "unknown":
        reasons.append(f"Finding value: {record.finding}")
    if record.reviewer_status_label:
        reasons.append(f"Reviewer status: {record.reviewer_status_label}")
    return tuple(reasons[:6])


def review_flag_counts(records: tuple[FacilityCaseBriefRecord, ...]) -> dict[str, int]:
    return {
        "delay_any": sum(1 for record in records if record.delay_thresholds),
        "delay_30": sum(1 for record in records if 30 in record.delay_thresholds),
        "delay_60": sum(1 for record in records if 60 in record.delay_thresholds),
        "delay_90": sum(1 for record in records if 90 in record.delay_thresholds),
        "delay_120": sum(1 for record in records if 120 in record.delay_thresholds),
        "missing_first_activity": sum(1 for record in records if record.missing_first_activity_date),
        "missing_key_date": sum(
            1
            for record in records
            if record.missing_visit_date or record.missing_report_date or record.missing_signed_date
        ),
        "needs_source_check": sum(1 for record in records if needs_source_check(record)),
        "proxy_date": sum(1 for record in records if record.report_date_used_as_proxy),
    }


def finding_counts(records: tuple[FacilityCaseBriefRecord, ...]) -> dict[str, int]:
    counts = Counter(record.finding if record.finding else "unknown" for record in records)
    return dict(sorted(counts.items(), key=lambda item: (item[0] == "unknown", item[0])))


def has_review_flag(record: FacilityCaseBriefRecord) -> bool:
    return bool(
        record.delay_thresholds
        or record.missing_first_activity_date
        or record.missing_visit_date
        or record.missing_report_date
        or record.missing_signed_date
        or record.report_date_used_as_proxy
    )


def needs_source_check(record: FacilityCaseBriefRecord) -> bool:
    return bool(
        record.missing_first_activity_date
        or record.missing_visit_date
        or record.missing_report_date
        or record.missing_signed_date
        or record.report_date_used_as_proxy
    )


def display_record_label(record: FacilityCaseBriefRecord) -> str:
    return record.complaint_control_number or record.source_record_key or "Complaint record"


def _priority_sort_key(record: FacilityCaseBriefRecord) -> tuple[int, int, int, int, int, int, str, int]:
    no_state_rank = 0 if record.reviewer_status is None and record.reviewer_note_count == 0 else 1
    no_status_rank = 0 if record.reviewer_status is None else 1
    strongest_delay = max(record.delay_thresholds) if record.delay_thresholds else 0
    missing_rank = 1 if needs_source_check(record) else 0
    traceability_rank = 1 if record.has_source_traceability else 0
    finding_rank = 1 if record.finding and record.finding != "unknown" else 0
    date_value = record.complaint_received_date or record.report_date or record.visit_date or record.date_signed or ""
    return (
        no_state_rank,
        no_status_rank,
        -strongest_delay,
        -missing_rank,
        -traceability_rank,
        -finding_rank,
        _reverse_date_key(date_value),
        record.order_index,
    )


def _reverse_date_key(value: str) -> str:
    if not value:
        return "9999-99-99"
    # ISO dates sort ascending; invert digits for descending while keeping stable strings.
    return "".join(str(9 - int(ch)) if ch.isdigit() else ch for ch in value)


def _metric_cards(metrics: tuple[tuple[str, int, bool], ...]) -> str:
    cards = []
    for label, count, show in metrics:
        if not show:
            continue
        cards.append(
            f"        <div class=\"metric-card\"><strong>{count}</strong><span>{_escape(label)}</span></div>"
        )
    return "\n".join(cards)


def _date_range_fragment(date_range: str) -> str:
    if not date_range or date_range == "not provided":
        return ""
    return f"; requested date range: {_escape(date_range)}"


def _escape(value: object) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)
