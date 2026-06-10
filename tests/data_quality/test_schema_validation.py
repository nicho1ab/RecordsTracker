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
        "days_received_to_report": None,
        "extraction_confidence": None,
    }
    validate_schema(record, Path("schemas/complaint.schema.json"))
