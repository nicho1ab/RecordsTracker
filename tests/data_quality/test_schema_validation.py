from pathlib import Path

from ccld_complaints.quality.validate import validate_schema


def test_complaint_schema_accepts_minimal_record() -> None:
    record = {
        "complaint_id": "complaint-1",
        "facility_id": "facility-1",
        "document_id": "document-1",
        "complaint_control_number": None,
        "complaint_received_date": None,
        "first_investigation_activity_date": None,
        "visit_date": None,
        "report_date": None,
        "date_signed": None,
        "finding": "Unknown",
        "days_received_to_first_activity": None,
        "days_received_to_visit": None,
        "days_received_to_report": None,
        "days_report_to_signed": None,
        "review_delay_over_30_days": False,
        "review_delay_over_60_days": False,
        "review_delay_over_90_days": False,
        "review_delay_over_120_days": False,
        "missing_first_activity_date": False,
        "report_date_used_as_proxy": False,
        "extraction_confidence": None,
    }
    validate_schema(record, Path("schemas/complaint.schema.json"))


def test_facility_schema_accepts_governed_canonical_allocations() -> None:
    record = {
        "facility_id": "ccld-facility-157806098",
        "source_id": "ccld",
        "external_facility_number": "157806098",
        "facility_name": "Governed Fixture Facility",
        "facility_type": "Children's Center",
        "licensee_name": None,
        "county": "Kern",
        "status": "Licensed",
        "capacity": 0,
        "regional_office": "CCLD Regional Office",
    }

    validate_schema(record, Path("schemas/facility.schema.json"))


def test_complaint_schema_accepts_governed_first_activity_interval() -> None:
    record = {
        "complaint_id": "complaint-1",
        "facility_id": "facility-1",
        "document_id": "document-1",
        "complaint_control_number": "32-CR-20220407124448",
        "complaint_received_date": "2022-04-07",
        "first_investigation_activity_date": "2022-04-14",
        "visit_date": None,
        "report_date": None,
        "date_signed": None,
        "finding": "Unknown",
        "days_received_to_first_activity": 7,
        "days_received_to_visit": None,
        "days_received_to_report": None,
        "days_report_to_signed": None,
        "review_delay_over_30_days": False,
        "review_delay_over_60_days": False,
        "review_delay_over_90_days": False,
        "review_delay_over_120_days": False,
        "missing_first_activity_date": False,
        "report_date_used_as_proxy": False,
        "extraction_confidence": 1.0,
    }

    validate_schema(record, Path("schemas/complaint.schema.json"))
