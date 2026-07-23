from __future__ import annotations

import argparse
import csv
import gc
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.engine import Connection, Engine, RowMapping
from sqlalchemy.exc import SQLAlchemyError

from ccld_complaints.connectors.base import SourceDocument
from ccld_complaints.connectors.ccld.facility_reports import (
    BASE_URL,
    CcldFacilityReportsConnector,
)
from ccld_complaints.extraction.dates import days_between, parse_date_or_none
from ccld_complaints.hosted_app.ccld_hosted_artifact_builder import (
    build_ccld_hosted_seeded_corpus_artifact,
)
from ccld_complaints.hosted_app.facility_reference_preload import (
    SOURCE_CSV_OVERFLOW_PROVENANCE_KEY,
    FacilityReferenceRecord,
    hosted_facility_reference_metadata,
    hosted_facility_reference_records,
    load_facility_reference_preload,
    parse_facility_reference_csv,
)
from ccld_complaints.hosted_app.persistence import (
    HostedDatabaseConfigError,
    load_hosted_database_config,
)
from ccld_complaints.hosted_app.seeded_import import (
    SeededCorpusArtifact,
    hosted_seeded_import_metadata,
    hosted_source_derived_records,
    import_seeded_corpus_artifact,
    parse_seeded_corpus_artifact,
)
from ccld_complaints.source_to_screen_audit import (
    redact_sensitive_text,
    sanitize_payload,
)
from ccld_complaints.storage.sqlite import (
    initialize_database,
    write_normalized_records,
)
from ccld_complaints.utils.hash import sha256_bytes

EvidenceMode = Literal["local", "runtime"]

SCHEMA_VERSION = 1
GOVERNED_COMPLAINT_FIXTURE = Path("tests/fixtures/ccld/raw/157806098_inx3.html")
GOVERNED_STRUCTURED_COMPLAINT_FIXTURE = Path(
    "tests/fixtures/ccld/raw/900000001_inx1_issue574_structured_fields.html"
)
GOVERNED_FACILITY_FIXTURES = (
    Path("tests/fixtures/public_source_facilities/ccld_program_facilities_tiny.csv"),
    Path("tests/fixtures/public_source_facilities/chhs_facility_master_tiny.csv"),
)
FIXTURE_RETRIEVED_AT = "2026-06-10T00:00:00+00:00"
FIXTURE_ACCESSED_AT = "2026-06-10T00:00:00+00:00"
FIXTURE_FACILITY_NUMBER = "157806098"
FIXTURE_REPORT_INDEX = 3
COMPOSITE_SOURCE_HEADER = (
    "Complaint Info- Date, #Sub Aleg, # Inc Aleg, # Uns Aleg, # TypeA, # TypeB ..."
)
SYNTHETIC_FACILITY_IDS = ("900000001", "900000002")

OUTPUT_FILES = (
    "manifest.json",
    "allocation-results.csv",
    "import-results.csv",
    "null-semantics-results.csv",
    "migration-results.csv",
    "gap-status.csv",
    "summary.md",
)

ALLOCATION_FIELDNAMES = (
    "field_id",
    "source_element",
    "allocation_decision",
    "canonical_destination",
    "canonical_type",
    "null_blank_behavior",
    "normalization_rule",
    "order_dedup_rule",
    "traceability_relationship",
    "import_initialization_owner",
    "existing_data_refresh",
    "contract_status",
    "assertion_status",
)
IMPORT_FIELDNAMES = (
    "field_id",
    "evidence_scope",
    "adapter",
    "eligible_count",
    "populated_count",
    "null_count",
    "blank_count",
    "unavailable_count",
    "verified_zero_count",
    "ordering_status",
    "idempotence_status",
    "reconciliation_status",
    "inspection_status",
    "assertion_status",
    "evidence_reference",
)
NULL_FIELDNAMES = (
    "field_id",
    "source_blank_count",
    "source_unavailable_count",
    "normalized_null_count",
    "verified_zero_count",
    "empty_string_default_count",
    "zero_default_count",
    "source_state_preserved",
    "assertion_status",
    "evidence_reference",
)
MIGRATION_FIELDNAMES = (
    "check_id",
    "layer",
    "change_kind",
    "expected_behavior",
    "existing_row_count_before",
    "existing_row_count_after",
    "existing_rows_readable",
    "nullable_or_default_status",
    "destructive_rewrite_performed",
    "assertion_status",
    "evidence_reference",
)
GAP_FIELDNAMES = (
    "field_id",
    "prior_gap_status",
    "allocation_decision",
    "canonical_storage_status",
    "importer_initializer_status",
    "regression_status",
    "runtime_population_status",
    "existing_data_status",
    "assertion_status",
)


@dataclass(frozen=True)
class AllocationSpec:
    field_id: str
    source_element: str
    allocation_decision: str
    canonical_destination: str
    canonical_type: str
    null_blank_behavior: str
    normalization_rule: str
    order_dedup_rule: str
    traceability_relationship: str
    import_initialization_owner: str
    existing_data_refresh: str


@dataclass(frozen=True)
class FieldMetric:
    eligible_count: int
    populated_count: int
    null_count: int
    blank_count: int
    unavailable_count: int
    verified_zero_count: int = 0
    empty_string_default_count: int = 0
    zero_default_count: int = 0


ALLOCATION_SPECS = (
    AllocationSpec(
        field_id="complaint.agency_name",
        source_element="complaint-report AGENCY heading value",
        allocation_decision="existing_canonical",
        canonical_destination="complaint.agency_name",
        canonical_type="string or null",
        null_blank_behavior="blank, unavailable, and omitted input remain null",
        normalization_rule="preserve deterministic extractor normalization",
        order_dedup_rule="not applicable",
        traceability_relationship="complaint links to source_document and field extraction audit",
        import_initialization_owner=(
            "CCLD report normalization, SQLite writer, hosted artifact builder, "
            "and hosted seeded-corpus importer"
        ),
        existing_data_refresh="bounded preserved-artifact replay or validated reimport",
    ),
    AllocationSpec(
        field_id="complaint.deficiency_texts",
        source_element="ordered explicit complaint-report DEFICIENCIES entries",
        allocation_decision="existing_canonical",
        canonical_destination="complaint.deficiency_texts",
        canonical_type="ordered JSON string array or null",
        null_blank_behavior="missing or empty input remains null",
        normalization_rule="preserve deterministic extractor text",
        order_dedup_rule="preserve source order without sorting or deduplication",
        traceability_relationship=(
            "complaint links to source_document and ordered deficiency extraction audits"
        ),
        import_initialization_owner=(
            "CCLD report normalization, SQLite writer, hosted artifact builder, "
            "and hosted seeded-corpus importer"
        ),
        existing_data_refresh="bounded preserved-artifact replay or validated reimport",
    ),
    AllocationSpec(
        field_id="complaint.investigation_findings_narrative",
        source_element="bounded complaint-report INVESTIGATION FINDINGS narrative",
        allocation_decision="existing_canonical",
        canonical_destination="complaint.investigation_findings_narrative",
        canonical_type="string or null",
        null_blank_behavior="blank, unavailable, and omitted input remain null",
        normalization_rule="preserve deterministic bounded narrative",
        order_dedup_rule="not applicable",
        traceability_relationship="complaint links to source_document and field extraction audit",
        import_initialization_owner=(
            "CCLD report normalization, SQLite writer, hosted artifact builder, "
            "and hosted seeded-corpus importer"
        ),
        existing_data_refresh="bounded preserved-artifact replay or validated reimport",
    ),
    AllocationSpec(
        field_id="complaint.complaint_report_contact",
        source_element="historical complaint-report TELEPHONE value",
        allocation_decision="existing_canonical",
        canonical_destination="complaint.complaint_report_contact",
        canonical_type="string or null",
        null_blank_behavior="blank, placeholder, unavailable, and omitted input remain null",
        normalization_rule="preserve deterministic non-placeholder source text",
        order_dedup_rule="not applicable",
        traceability_relationship="complaint links to source_document and field extraction audit",
        import_initialization_owner=(
            "CCLD report normalization, SQLite writer, hosted artifact builder, "
            "and hosted seeded-corpus importer"
        ),
        existing_data_refresh="bounded preserved-artifact replay or validated reimport",
    ),
    AllocationSpec(
        field_id="complaint.days_received_to_first_activity",
        source_element=(
            "COMPLAINT RECEIVED and the deterministic earliest investigation-"
            "activity narrative date"
        ),
        allocation_decision="existing_canonical",
        canonical_destination="complaint.days_received_to_first_activity",
        canonical_type="integer or null",
        null_blank_behavior=(
            "null unless both source dates are present and valid; zero only when "
            "the dates are the same day"
        ),
        normalization_rule=(
            "calendar-day difference from complaint received date to first "
            "investigation activity date"
        ),
        order_dedup_rule="not applicable",
        traceability_relationship=("complaint links to source_document and field extraction audit"),
        import_initialization_owner=(
            "CCLD report normalization, SQLite writer, hosted artifact builder, "
            "and hosted seeded-corpus importer"
        ),
        existing_data_refresh="regenerate and reimport existing hosted records",
    ),
    AllocationSpec(
        field_id="facility.capacity",
        source_element=(
            "complaint-report FACILITY CAPACITY; facility-reference Facility Capacity or CAPACITY"
        ),
        allocation_decision="existing_canonical",
        canonical_destination="facility.capacity",
        canonical_type="integer or null",
        null_blank_behavior="blank, unavailable, and nonnumeric input remain null",
        normalization_rule="trim separators and parse a base-10 integer",
        order_dedup_rule="not applicable",
        traceability_relationship=(
            "report source_document traceability or facility-reference resource metadata"
        ),
        import_initialization_owner=(
            "CCLD report normalization and imports; facility-reference preload"
        ),
        existing_data_refresh=(
            "regenerate and reimport report rows; rerun facility-reference preload"
        ),
    ),
    AllocationSpec(
        field_id="facility.county",
        source_element="County Name or COUNTY",
        allocation_decision="existing_canonical",
        canonical_destination="facility.county",
        canonical_type="string or null",
        null_blank_behavior="blank and unavailable input remain null",
        normalization_rule="trim surrounding and repeated whitespace",
        order_dedup_rule="not applicable",
        traceability_relationship="facility-reference resource and original row",
        import_initialization_owner="facility-reference parser and preload",
        existing_data_refresh="rerun facility-reference preload",
    ),
    AllocationSpec(
        field_id="facility.facility_type",
        source_element="Facility Type or FAC_TYPE_DESC",
        allocation_decision="existing_canonical",
        canonical_destination="facility.facility_type",
        canonical_type="string or null",
        null_blank_behavior="blank and unavailable input remain null",
        normalization_rule="trim surrounding and repeated whitespace",
        order_dedup_rule="not applicable",
        traceability_relationship="facility-reference resource and original row",
        import_initialization_owner="facility-reference parser and preload",
        existing_data_refresh="rerun facility-reference preload",
    ),
    AllocationSpec(
        field_id="facility.regional_office",
        source_element="CCLD regional-office label, Regional Office, or FAC_DO_DESC",
        allocation_decision="existing_canonical",
        canonical_destination="facility.regional_office",
        canonical_type="string or null",
        null_blank_behavior="blank and unavailable input remain null",
        normalization_rule="trim surrounding and repeated whitespace",
        order_dedup_rule="not applicable",
        traceability_relationship=(
            "report source_document traceability or facility-reference resource metadata"
        ),
        import_initialization_owner=(
            "CCLD report normalization and imports; facility-reference preload"
        ),
        existing_data_refresh=(
            "regenerate and reimport report rows; rerun facility-reference preload"
        ),
    ),
    AllocationSpec(
        field_id="facility.status",
        source_element="Facility Status or STATUS",
        allocation_decision="existing_canonical",
        canonical_destination="facility.status",
        canonical_type="string or null",
        null_blank_behavior="blank and unavailable input remain null",
        normalization_rule="trim surrounding and repeated whitespace",
        order_dedup_rule="not applicable",
        traceability_relationship="facility-reference resource and original row",
        import_initialization_owner="facility-reference parser and preload",
        existing_data_refresh="rerun facility-reference preload",
    ),
    AllocationSpec(
        field_id="ccld_program_facility.all_visit_dates",
        source_element="All Visit Dates",
        allocation_decision="typed_source_reference",
        canonical_destination="hosted_facility_reference_records.all_visit_dates",
        canonical_type="JSON array of ISO dates or null",
        null_blank_behavior="blank and unavailable input remain null",
        normalization_rule="parse supported source dates to ISO date strings",
        order_dedup_rule="ascending chronological order with duplicates removed",
        traceability_relationship="facility-reference resource and original row",
        import_initialization_owner="facility-reference parser and preload",
        existing_data_refresh="rerun facility-reference preload",
    ),
    AllocationSpec(
        field_id=(
            "ccld_program_facility.complaint_info_date_sub_aleg_inc_aleg_uns_aleg_typea_typeb"
        ),
        source_element=COMPOSITE_SOURCE_HEADER,
        allocation_decision="retained_raw_only",
        canonical_destination="hosted_facility_reference_records.original_row_json",
        canonical_type="retained source string only",
        null_blank_behavior=(
            "header absence remains unavailable and a present blank remains blank "
            "in retained source data"
        ),
        normalization_rule=(
            "preserve the declared cell and any CSV overflow provenance; do not "
            "flatten the composite source concept into one semantic value"
        ),
        order_dedup_rule="not applicable",
        traceability_relationship=(
            "facility-reference resource, original row, and source CSV overflow "
            "provenance where present"
        ),
        import_initialization_owner="facility-reference preload original-row retention",
        existing_data_refresh="rerun facility-reference preload",
    ),
    AllocationSpec(
        field_id="ccld_program_facility.inspection_visit_dates",
        source_element="Inspection Visit Dates",
        allocation_decision="typed_source_reference",
        canonical_destination=("hosted_facility_reference_records.inspection_visit_dates"),
        canonical_type="JSON array of ISO dates or null",
        null_blank_behavior="blank and unavailable input remain null",
        normalization_rule="parse supported source dates to ISO date strings",
        order_dedup_rule="ascending chronological order with duplicates removed",
        traceability_relationship="facility-reference resource and original row",
        import_initialization_owner="facility-reference parser and preload",
        existing_data_refresh="rerun facility-reference preload",
    ),
    AllocationSpec(
        field_id="ccld_program_facility.other_visit_dates",
        source_element="Other Visit Dates",
        allocation_decision="typed_source_reference",
        canonical_destination="hosted_facility_reference_records.other_visit_dates",
        canonical_type="JSON array of ISO dates or null",
        null_blank_behavior="blank and unavailable input remain null",
        normalization_rule="parse supported source dates to ISO date strings",
        order_dedup_rule="ascending chronological order with duplicates removed",
        traceability_relationship="facility-reference resource and original row",
        import_initialization_owner="facility-reference parser and preload",
        existing_data_refresh="rerun facility-reference preload",
    ),
    AllocationSpec(
        field_id="chhs_facility_master.client_served",
        source_element="CLIENT_SERVED",
        allocation_decision="typed_source_reference",
        canonical_destination="hosted_facility_reference_records.client_served",
        canonical_type="string or null",
        null_blank_behavior="blank and unavailable input remain null",
        normalization_rule="trim surrounding and repeated whitespace",
        order_dedup_rule="not applicable",
        traceability_relationship="facility-reference resource and original row",
        import_initialization_owner="facility-reference parser and preload",
        existing_data_refresh="rerun facility-reference preload",
    ),
    AllocationSpec(
        field_id="facility_reference.closed_date",
        source_element="Closed Date or CLOSED_DATE",
        allocation_decision="typed_source_reference",
        canonical_destination="hosted_facility_reference_records.closed_date",
        canonical_type="ISO date string or null",
        null_blank_behavior="blank, unavailable, and invalid input remain null",
        normalization_rule=(
            "parse supported source dates to an ISO date without inferring closure"
        ),
        order_dedup_rule="not applicable",
        traceability_relationship="facility-reference resource and original row",
        import_initialization_owner="facility-reference parser and preload",
        existing_data_refresh="rerun facility-reference preload",
    ),
)

FIELD_IDS = tuple(spec.field_id for spec in ALLOCATION_SPECS)
CANONICAL_FIELD_IDS = tuple(
    spec.field_id for spec in ALLOCATION_SPECS if spec.allocation_decision == "existing_canonical"
)
DATE_COLLECTION_FIELD_IDS = (
    "ccld_program_facility.all_visit_dates",
    "ccld_program_facility.inspection_visit_dates",
    "ccld_program_facility.other_visit_dates",
)
FACILITY_CANONICAL_FIELD_KEYS: Mapping[str, str] = {
    "facility.capacity": "capacity",
    "facility.county": "county",
    "facility.facility_type": "facility_type",
    "facility.regional_office": "regional_office",
    "facility.status": "status",
}
CANONICAL_ALLOCATION_MIGRATION_REVISION = "20260714_0007"
CANONICAL_ALLOCATION_MIGRATION_COLUMNS = (
    "all_visit_dates",
    "inspection_visit_dates",
    "other_visit_dates",
    "client_served",
)
COMPLAINT_OBSERVATION_MIGRATION_REVISION = "20260723_0013"
COMPLAINT_OBSERVATION_MIGRATION_COLUMNS = (
    "agency_name",
    "deficiency_texts",
    "investigation_findings_narrative",
    "complaint_report_contact",
)
COMPLAINT_OBSERVATION_FIELD_KEYS: Mapping[str, str] = {
    "complaint.agency_name": "agency_name",
    "complaint.deficiency_texts": "deficiency_texts",
    "complaint.investigation_findings_narrative": "investigation_findings_narrative",
    "complaint.complaint_report_contact": "complaint_report_contact",
}

_FACILITY_FIELD_CONFIG: Mapping[str, tuple[str | None, tuple[str, ...]]] = {
    "facility.capacity": ("capacity", ("Facility Capacity", "CAPACITY")),
    "facility.county": ("county", ("County Name", "COUNTY")),
    "facility.facility_type": (
        "facility_type",
        ("Facility Type", "FAC_TYPE_DESC"),
    ),
    "facility.regional_office": (
        "regional_office",
        ("Regional Office", "FAC_DO_DESC"),
    ),
    "facility.status": ("status", ("Facility Status", "STATUS")),
    "ccld_program_facility.all_visit_dates": (
        "all_visit_dates",
        ("All Visit Dates",),
    ),
    ("ccld_program_facility.complaint_info_date_sub_aleg_inc_aleg_uns_aleg_typea_typeb"): (
        None,
        (COMPOSITE_SOURCE_HEADER,),
    ),
    "ccld_program_facility.inspection_visit_dates": (
        "inspection_visit_dates",
        ("Inspection Visit Dates",),
    ),
    "ccld_program_facility.other_visit_dates": (
        "other_visit_dates",
        ("Other Visit Dates",),
    ),
    "chhs_facility_master.client_served": (
        "client_served",
        ("CLIENT_SERVED",),
    ),
    "facility_reference.closed_date": (
        "closed_date",
        ("Closed Date", "CLOSED_DATE"),
    ),
}

_RUNTIME_SOURCE_FIELDS = (
    ("complaint.agency_name", "complaint", "agency_name"),
    ("complaint.deficiency_texts", "complaint", "deficiency_texts"),
    (
        "complaint.investigation_findings_narrative",
        "complaint",
        "investigation_findings_narrative",
    ),
    (
        "complaint.complaint_report_contact",
        "complaint",
        "complaint_report_contact",
    ),
    ("complaint.days_received_to_first_activity", "complaint", "days_received_to_first_activity"),
    ("facility.capacity", "facility", "capacity"),
    ("facility.county", "facility", "county"),
    ("facility.facility_type", "facility", "facility_type"),
    ("facility.regional_office", "facility", "regional_office"),
    ("facility.status", "facility", "status"),
)
_RUNTIME_REFERENCE_COLUMNS: Mapping[str, str] = {
    "facility.capacity": "capacity",
    "facility.county": "county",
    "facility.facility_type": "facility_type",
    "facility.regional_office": "regional_office",
    "facility.status": "status",
    "ccld_program_facility.all_visit_dates": "all_visit_dates",
    "ccld_program_facility.inspection_visit_dates": "inspection_visit_dates",
    "ccld_program_facility.other_visit_dates": "other_visit_dates",
    "chhs_facility_master.client_served": "client_served",
    "facility_reference.closed_date": "closed_date",
}
_COMPOSITE_FIELD_ID = (
    "ccld_program_facility.complaint_info_date_sub_aleg_inc_aleg_uns_aleg_typea_typeb"
)


class EvidenceExecutionError(RuntimeError):
    """A controlled, aggregate-safe evidence execution failure."""


def run_evidence(
    *,
    mode: EvidenceMode,
    output_dir: Path,
    repo_root: Path | None = None,
    environ: Mapping[str, str] | None = None,
    runtime_connection: Connection | None = None,
) -> Mapping[str, Any]:
    """Exercise allocation paths and write deterministic aggregate-only evidence."""

    if mode not in {"local", "runtime"}:
        raise ValueError("Evidence mode must be local or runtime.")
    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    capability = _local_capability(root)

    runtime_source_rows: list[dict[str, object]] = []
    runtime_reference_rows: list[dict[str, object]] = []
    runtime_source_status = "not inspected in local mode"
    runtime_reference_status = "not inspected in local mode"
    runtime_source_record_count: int | None = None
    runtime_reference_record_count: int | None = None

    if mode == "runtime":
        if runtime_connection is not None:
            runtime = _runtime_population(runtime_connection)
        else:
            runtime = _configured_runtime_population(
                environ if environ is not None else os.environ,
                root,
            )
        runtime_source_rows = cast(list[dict[str, object]], runtime["hosted_source_derived"])
        runtime_reference_rows = cast(list[dict[str, object]], runtime["facility_reference"])
        runtime_source_status = str(runtime["hosted_source_derived_status"])
        runtime_reference_status = str(runtime["facility_reference_status"])
        runtime_source_record_count = cast(
            int | None, runtime["hosted_source_derived_record_count"]
        )
        runtime_reference_record_count = cast(
            int | None, runtime["facility_reference_record_count"]
        )

    allocation_rows = cast(list[dict[str, object]], capability["allocation_rows"])
    implementation_import_rows = cast(list[dict[str, object]], capability["import_rows"])
    null_rows = cast(list[dict[str, object]], capability["null_rows"])
    migration_rows = cast(list[dict[str, object]], capability["migration_rows"])
    assertions = dict(cast(Mapping[str, bool], capability["assertions"]))
    runtime_import_rows = [
        _runtime_import_row(row) for row in runtime_source_rows + runtime_reference_rows
    ]
    import_rows = implementation_import_rows + runtime_import_rows

    runtime_population = {
        "status": (
            "not inspected in local mode"
            if mode == "local"
            else "inspected through separate aggregate adapters"
        ),
        "hosted_source_derived": {
            "status": runtime_source_status,
            "record_count": runtime_source_record_count,
            "field_count": len(runtime_source_rows),
            "fields": runtime_source_rows,
        },
        "facility_reference": {
            "status": runtime_reference_status,
            "record_count": runtime_reference_record_count,
            "field_count": len(runtime_reference_rows),
            "fields": runtime_reference_rows,
        },
    }
    assertions["runtime_population_reported_separately"] = mode == "local" or (
        runtime_source_status.startswith("inspected")
        and runtime_reference_status.startswith("inspected")
        and bool(runtime_source_rows)
        and bool(runtime_reference_rows)
    )
    assertions["existing_data_refresh_requirement_stated"] = True

    gap_rows = _gap_rows(
        allocation_rows,
        implementation_import_rows,
        mode=mode,
        runtime_source_rows=runtime_source_rows,
        runtime_reference_rows=runtime_reference_rows,
    )
    existing_data_refresh = {
        "required": True,
        "postgresql_source_derived": (
            "Existing hosted source-derived rows require regeneration and reimport "
            "before newly allocated canonical values appear."
        ),
        "facility_reference": (
            "Existing facility-reference rows require the preload to be rerun before "
            "new typed source-reference values appear."
        ),
        "safe_command_available": False,
        "safe_command_status": (
            "No safe automated existing-data refresh command is currently available."
        ),
    }

    aggregate_payloads = (
        allocation_rows,
        import_rows,
        null_rows,
        migration_rows,
        gap_rows,
        runtime_population,
        existing_data_refresh,
    )
    assertions["no_synthetic_facility_ids_emitted"] = _synthetic_facility_ids_absent(
        aggregate_payloads
    )
    assertions["safe_aggregate_output"] = _aggregate_safe(
        aggregate_payloads,
        cast(tuple[str, ...], capability["source_values"]),
        root,
    )

    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "allocation_registry": {
            "field_count": len(ALLOCATION_SPECS),
            "field_ids": list(FIELD_IDS),
        },
        "implementation_capability": {
            "status": "inspected through governed local adapters",
            "connector_sqlite_artifact_hosted_import": "exercised",
            "facility_fixture_temporary_hosted_import": (
                "exercised with exact canonical-value comparison"
            ),
            "facility_reference_parser_preload": "exercised",
            "field_count": len(implementation_import_rows),
        },
        "runtime_population": runtime_population,
        "existing_data_refresh": existing_data_refresh,
        "assertions": assertions,
        "counts": {
            "allocation_fields": len(ALLOCATION_SPECS),
            "allocation_results": len(allocation_rows),
            "implementation_import_results": len(implementation_import_rows),
            "runtime_import_results": len(runtime_import_rows),
            "null_semantics_results": len(null_rows),
            "migration_results": len(migration_rows),
            "gap_results": len(gap_rows),
            "assertions_passed": sum(bool(value) for value in assertions.values()),
            "assertions_total": len(assertions),
        },
        "generated_files": list(OUTPUT_FILES),
    }

    effective_output = output_dir if output_dir.is_absolute() else root / output_dir
    _write_outputs(
        effective_output,
        manifest=manifest,
        allocation_rows=allocation_rows,
        import_rows=import_rows,
        null_rows=null_rows,
        migration_rows=migration_rows,
        gap_rows=gap_rows,
    )
    return manifest


def _local_capability(repo_root: Path) -> dict[str, object]:
    contract_path = repo_root / "DATA_CONTRACT.md"
    complaint_fixture = repo_root / GOVERNED_COMPLAINT_FIXTURE
    structured_complaint_fixture = repo_root / GOVERNED_STRUCTURED_COMPLAINT_FIXTURE
    facility_fixtures = tuple(
        repo_root / relative_path for relative_path in GOVERNED_FACILITY_FIXTURES
    )
    if not contract_path.is_file():
        raise EvidenceExecutionError("The governed data contract is unavailable.")
    if not complaint_fixture.is_file():
        raise EvidenceExecutionError("The governed complaint fixture is unavailable.")
    if not structured_complaint_fixture.is_file():
        raise EvidenceExecutionError("The governed structured complaint fixture is unavailable.")
    if not all(path.is_file() for path in facility_fixtures):
        raise EvidenceExecutionError("A governed facility-reference fixture is unavailable.")

    contract_text = contract_path.read_text(encoding="utf-8-sig")
    allocation_rows = [
        _allocation_row(spec, documented=spec.field_id in contract_text)
        for spec in ALLOCATION_SPECS
    ]

    parse_results = tuple(
        parse_facility_reference_csv(
            path,
            source_accessed_at=FIXTURE_ACCESSED_AT,
        )
        for path in facility_fixtures
    )
    records = tuple(record for result in parse_results for record in result.records)
    if not records:
        raise EvidenceExecutionError(
            "The governed facility-reference fixtures produced no records."
        )
    facility_metrics = _facility_metrics(records)
    date_collections_ordered = _date_collections_ordered(records)
    composite_retained = _composite_retained_without_flattening(records)
    canonical_fixture_record = _governed_canonical_fixture_record(parse_results[0].records)
    canonical_fixture_artifact = _canonical_fixture_seeded_artifact(
        canonical_fixture_record,
        facility_fixtures[0],
    )
    migration_exercise = _exercise_canonical_allocation_migration(repo_root)
    complaint_migration_exercise = _exercise_complaint_observation_migration(
        repo_root
    )

    with tempfile.TemporaryDirectory(prefix="canonical-allocation-evidence-") as scratch:
        db_path = Path(scratch) / "canonical-allocation.sqlite3"
        normalized, connector_source_values = _normalized_complaint_record(
            repo_root,
            complaint_fixture,
            relative_path=GOVERNED_COMPLAINT_FIXTURE,
            facility_number=FIXTURE_FACILITY_NUMBER,
            report_index=FIXTURE_REPORT_INDEX,
        )
        structured_normalized, structured_source_values = _normalized_complaint_record(
            repo_root,
            structured_complaint_fixture,
            relative_path=GOVERNED_STRUCTURED_COMPLAINT_FIXTURE,
            facility_number=SYNTHETIC_FACILITY_IDS[0],
            report_index=1,
        )
        write_normalized_records(db_path, [normalized, structured_normalized])
        sqlite_counts_before = _sqlite_record_counts(db_path)
        write_normalized_records(db_path, [normalized, structured_normalized])
        initialize_database(db_path)
        sqlite_counts_after = _sqlite_record_counts(db_path)
        reconciliation_ok = _sqlite_delay_reconciles(db_path)

        build_result = build_ccld_hosted_seeded_corpus_artifact(
            db_path,
            facility_number=FIXTURE_FACILITY_NUMBER,
            import_batch_id="canonical-allocation-local",
            imported_at=FIXTURE_RETRIEVED_AT,
            source_artifact_identity="governed-local-capability",
            schema_dir=repo_root / "schemas",
        )
        artifact = parse_seeded_corpus_artifact(build_result.artifact)
        structured_build_result = build_ccld_hosted_seeded_corpus_artifact(
            db_path,
            facility_number=SYNTHETIC_FACILITY_IDS[0],
            import_batch_id="canonical-allocation-structured-local",
            imported_at=FIXTURE_RETRIEVED_AT,
            source_artifact_identity="governed-structured-local-capability",
            schema_dir=repo_root / "schemas",
        )
        structured_artifact = parse_seeded_corpus_artifact(
            structured_build_result.artifact
        )
        hosted_engine = create_engine("sqlite+pysqlite:///:memory:")
        try:
            hosted_seeded_import_metadata.create_all(hosted_engine)
            with hosted_engine.begin() as connection:
                first_import = import_seeded_corpus_artifact(connection, artifact)
                first_structured_import = import_seeded_corpus_artifact(
                    connection, structured_artifact
                )
                first_canonical_fixture_import = import_seeded_corpus_artifact(
                    connection,
                    canonical_fixture_artifact,
                )
                hosted_count_before = connection.execute(
                    select(func.count()).select_from(hosted_source_derived_records)
                ).scalar_one()
                second_import = import_seeded_corpus_artifact(connection, artifact)
                second_structured_import = import_seeded_corpus_artifact(
                    connection, structured_artifact
                )
                second_canonical_fixture_import = import_seeded_corpus_artifact(
                    connection,
                    canonical_fixture_artifact,
                )
                hosted_count_after = connection.execute(
                    select(func.count()).select_from(hosted_source_derived_records)
                ).scalar_one()
                hosted_source_rows, _status, _record_count = _runtime_source_population(connection)
                canonical_import_matches = _canonical_hosted_import_matches(
                    connection,
                    canonical_fixture_record=canonical_fixture_record,
                    complaint_delay=cast(
                        int | None,
                        cast(Mapping[str, object], normalized["complaint"])[
                            "days_received_to_first_activity"
                        ],
                    ),
                    structured_complaint=cast(
                        Mapping[str, object], structured_normalized["complaint"]
                    ),
                )
        finally:
            hosted_engine.dispose()
        gc.collect()

    reference_engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        hosted_facility_reference_metadata.create_all(reference_engine)
        with reference_engine.begin() as connection:
            first_preloads = tuple(
                load_facility_reference_preload(
                    path,
                    connection=connection,
                    apply_changes=True,
                    source_accessed_at=FIXTURE_ACCESSED_AT,
                )
                for path in facility_fixtures
            )
            reference_count_before = connection.execute(
                select(func.count()).select_from(hosted_facility_reference_records)
            ).scalar_one()
            second_preloads = tuple(
                load_facility_reference_preload(
                    path,
                    connection=connection,
                    apply_changes=True,
                    source_accessed_at=FIXTURE_ACCESSED_AT,
                )
                for path in facility_fixtures
            )
            reference_count_after = connection.execute(
                select(func.count()).select_from(hosted_facility_reference_records)
            ).scalar_one()
    finally:
        reference_engine.dispose()

    complaint = cast(Mapping[str, object], normalized["complaint"])
    complaint_delay = cast(int | None, complaint["days_received_to_first_activity"])
    complaint_metric = FieldMetric(
        eligible_count=1,
        populated_count=int(complaint_delay is not None),
        null_count=int(complaint_delay is None),
        blank_count=0,
        unavailable_count=0,
        verified_zero_count=int(complaint_delay == 0),
    )
    structured_complaint = cast(
        Mapping[str, object], structured_normalized["complaint"]
    )
    structured_metrics = {
        field_id: FieldMetric(
            eligible_count=1,
            populated_count=int(structured_complaint.get(field_key) is not None),
            null_count=int(structured_complaint.get(field_key) is None),
            blank_count=0,
            unavailable_count=0,
        )
        for field_id, field_key in COMPLAINT_OBSERVATION_FIELD_KEYS.items()
    }
    metrics = {
        **structured_metrics,
        "complaint.days_received_to_first_activity": complaint_metric,
        **facility_metrics,
    }
    source_rows_by_field = {str(row["field_id"]): row for row in hosted_source_rows}
    sqlite_idempotent = sqlite_counts_before == sqlite_counts_after
    hosted_idempotent = (
        hosted_count_before == hosted_count_after
        and first_import.imported_record_count == second_import.imported_record_count
        and first_structured_import.imported_record_count
        == second_structured_import.imported_record_count
        and first_canonical_fixture_import.imported_record_count
        == second_canonical_fixture_import.imported_record_count
    )
    preload_idempotent = (
        reference_count_before == reference_count_after
        and sum(result.inserted_row_count for result in second_preloads) == 0
        and sum(result.updated_row_count for result in second_preloads) == 0
        and sum(result.unchanged_row_count for result in second_preloads) == reference_count_after
        and sum(result.inserted_row_count for result in first_preloads) == reference_count_before
    )
    import_rows = _implementation_import_rows(
        metrics,
        source_rows_by_field=source_rows_by_field,
        canonical_import_matches=canonical_import_matches,
        date_collections_ordered=date_collections_ordered,
        reconciliation_ok=reconciliation_ok,
        idempotence_ok=sqlite_idempotent and hosted_idempotent and preload_idempotent,
    )
    null_rows = _null_rows(metrics)
    migration_rows = _migration_rows(
        sqlite_counts_before=sqlite_counts_before,
        sqlite_counts_after=sqlite_counts_after,
        hosted_count_before=hosted_count_before,
        hosted_count_after=hosted_count_after,
        migration_exercise=migration_exercise,
        complaint_migration_exercise=complaint_migration_exercise,
    )
    documented = all(row["contract_status"] == "DOCUMENTED" for row in allocation_rows)
    import_by_field = {str(row["field_id"]): row for row in import_rows}
    canonical_coverage = all(
        import_by_field[field_id]["assertion_status"] == "PASS" for field_id in CANONICAL_FIELD_IDS
    )
    canonical_populated = all(
        metrics[field_id].populated_count > 0 and canonical_import_matches.get(field_id, False)
        for field_id in CANONICAL_FIELD_IDS
    )
    null_default_safe = (
        any(metric.blank_count > 0 for metric in metrics.values())
        and any(metric.unavailable_count > 0 for metric in metrics.values())
        and all(metric.empty_string_default_count == 0 for metric in metrics.values())
        and all(metric.zero_default_count == 0 for metric in metrics.values())
    )
    migration_safe = all(row["assertion_status"] == "PASS" for row in migration_rows)

    assertions = {
        "all_governed_fields_documented": documented,
        "canonical_allocations_have_importer_or_initializer_coverage": canonical_coverage,
        "governed_values_populate_canonical_destinations": canonical_populated,
        "blank_and_unavailable_not_defaulted": null_default_safe,
        "days_received_to_first_activity_reconciles": reconciliation_ok,
        "date_collections_ordered_and_deduplicated": date_collections_ordered,
        "composite_source_not_misrepresented": composite_retained,
        "migration_additive_and_existing_rows_readable": migration_safe,
        "reimport_or_initialization_idempotent": (
            sqlite_idempotent and hosted_idempotent and preload_idempotent
        ),
        "no_synthetic_facility_ids_emitted": False,
        "runtime_population_reported_separately": True,
        "existing_data_refresh_requirement_stated": True,
        "safe_aggregate_output": False,
    }
    source_values = (
        connector_source_values
        + structured_source_values
        + _long_facility_source_values(records)
    )
    return {
        "allocation_rows": allocation_rows,
        "import_rows": import_rows,
        "null_rows": null_rows,
        "migration_rows": migration_rows,
        "assertions": assertions,
        "source_values": source_values,
    }


def _allocation_row(
    spec: AllocationSpec,
    *,
    documented: bool,
) -> dict[str, object]:
    return {
        "field_id": spec.field_id,
        "source_element": spec.source_element,
        "allocation_decision": spec.allocation_decision,
        "canonical_destination": spec.canonical_destination,
        "canonical_type": spec.canonical_type,
        "null_blank_behavior": spec.null_blank_behavior,
        "normalization_rule": spec.normalization_rule,
        "order_dedup_rule": spec.order_dedup_rule,
        "traceability_relationship": spec.traceability_relationship,
        "import_initialization_owner": spec.import_initialization_owner,
        "existing_data_refresh": spec.existing_data_refresh,
        "contract_status": "DOCUMENTED" if documented else "MISSING",
        "assertion_status": "PASS" if documented else "FAIL",
    }


def _normalized_complaint_record(
    repo_root: Path,
    fixture_path: Path,
    *,
    relative_path: Path,
    facility_number: str,
    report_index: int,
) -> tuple[dict[str, object], tuple[str, ...]]:
    content = fixture_path.read_bytes()
    source_url = f"{BASE_URL}?facNum={facility_number}&inx={report_index}"
    document = SourceDocument(
        source_url=source_url,
        raw_path=fixture_path,
        raw_sha256=sha256_bytes(content),
        retrieved_at=FIXTURE_RETRIEVED_AT,
        content_type="text/html",
    )
    connector = CcldFacilityReportsConnector(schema_dir=repo_root / "schemas")
    extracted = connector.extract(document)
    normalized = dict(connector.normalize(extracted))
    source_document = dict(cast(Mapping[str, object], normalized["source_document"]))
    source_document["raw_path"] = relative_path.as_posix()
    normalized["source_document"] = source_document
    connector.validate(normalized)
    audits = cast(Sequence[Mapping[str, object]], normalized["extraction_audit"])
    source_values = tuple(
        str(row["source_text"])
        for row in audits
        if isinstance(row.get("source_text"), str) and len(str(row["source_text"]).strip()) >= 12
    )
    return normalized, source_values


def _governed_canonical_fixture_record(
    records: Sequence[FacilityReferenceRecord],
) -> FacilityReferenceRecord:
    for record in records:
        values = (
            record.capacity,
            record.county,
            record.facility_type,
            record.regional_office,
            record.status,
        )
        if all(
            value is not None and (not isinstance(value, str) or bool(value.strip()))
            for value in values
        ):
            return record
    raise EvidenceExecutionError(
        "The governed CCLD program-facility fixture has no complete canonical import case."
    )


def _canonical_fixture_seeded_artifact(
    record: FacilityReferenceRecord,
    fixture_path: Path,
) -> SeededCorpusArtifact:
    """Adapt one governed CSV row to the generic importer only in memory."""

    raw_sha256 = sha256_bytes(fixture_path.read_bytes())
    facility_id = f"ccld:facility:{record.facility_number}"
    document_id = f"ccld:facility-reference:{raw_sha256[:16]}"
    return SeededCorpusArtifact(
        import_batch_id="canonical-allocation-facility-fixture-local",
        imported_at=FIXTURE_ACCESSED_AT,
        source_artifact_identity=("governed-ccld-program-facility-fixture-in-memory"),
        source_pipeline_version="canonical-allocation-evidence-v1",
        validation_status="validated",
        raw_hash_validation_status="validated",
        record_counts={
            "facility": 1,
            "source_document": 1,
            "complaint": 0,
            "allegation": 0,
            "event": 0,
            "extraction_audit": 0,
        },
        warnings=(
            "Temporary local importer exercise derived from the governed CCLD "
            "program-facility fixture; aggregate evidence only.",
        ),
        errors=(),
        records=(
            {
                "facility": {
                    "facility_id": facility_id,
                    "source_id": "ccld_program_facility",
                    "external_facility_number": record.facility_number,
                    "facility_name": record.facility_name,
                    "facility_type": record.facility_type,
                    "licensee_name": record.licensee_name,
                    "county": record.county,
                    "status": record.status,
                    "capacity": record.capacity,
                    "regional_office": record.regional_office,
                },
                "source_document": {
                    "document_id": document_id,
                    "source_id": "ccld_program_facility",
                    "facility_id": facility_id,
                    "source_url": record.source_dataset_url,
                    "retrieved_at": record.source_accessed_at,
                    "raw_sha256": raw_sha256,
                    "connector_name": "canonical_allocation_fixture_adapter",
                    "connector_version": "1",
                    "raw_path": GOVERNED_FACILITY_FIXTURES[0].as_posix(),
                    "document_type": "facility_reference_csv",
                },
            },
        ),
    )


def _canonical_hosted_import_matches(
    connection: Connection,
    *,
    canonical_fixture_record: FacilityReferenceRecord,
    complaint_delay: int | None,
    structured_complaint: Mapping[str, object],
) -> dict[str, bool]:
    facility_values = connection.execute(
        select(hosted_source_derived_records.c.original_values).where(
            hosted_source_derived_records.c.entity_type == "facility",
            hosted_source_derived_records.c.connector_name
            == "canonical_allocation_fixture_adapter",
        )
    ).scalars()
    facility_rows = tuple(
        cast(Mapping[str, object], value) for value in facility_values if isinstance(value, Mapping)
    )
    expected_facility_values: Mapping[str, object | None] = {
        "capacity": canonical_fixture_record.capacity,
        "county": canonical_fixture_record.county,
        "facility_type": canonical_fixture_record.facility_type,
        "regional_office": canonical_fixture_record.regional_office,
        "status": canonical_fixture_record.status,
    }
    matches = {
        field_id: any(
            _same_canonical_value(row.get(key), expected_facility_values[key])
            for row in facility_rows
        )
        for field_id, key in FACILITY_CANONICAL_FIELD_KEYS.items()
    }

    complaint_values = tuple(
        connection.execute(
            select(hosted_source_derived_records.c.original_values).where(
                hosted_source_derived_records.c.entity_type == "complaint",
                hosted_source_derived_records.c.connector_name
                == "ccld_facility_reports",
            )
        ).scalars()
    )
    matches["complaint.days_received_to_first_activity"] = any(
        isinstance(value, Mapping)
        and _same_canonical_value(
            value.get("days_received_to_first_activity"),
            complaint_delay,
        )
        for value in complaint_values
    )
    for field_id, field_key in COMPLAINT_OBSERVATION_FIELD_KEYS.items():
        expected_value = structured_complaint.get(field_key)
        matches[field_id] = any(
            isinstance(value, Mapping)
            and _same_canonical_value(value.get(field_key), expected_value)
            for value in complaint_values
        )
    return matches


def _same_canonical_value(actual: object, expected: object) -> bool:
    if isinstance(actual, bool) != isinstance(expected, bool):
        return False
    return type(actual) is type(expected) and actual == expected


def _sqlite_record_counts(db_path: Path) -> dict[str, int]:
    tables = (
        "facilities",
        "source_documents",
        "complaints",
        "allegations",
        "events",
        "extraction_audit",
    )
    connection = sqlite3.connect(db_path)
    try:
        return {
            table_name: int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])
            for table_name in tables
        }
    finally:
        connection.close()


def _sqlite_delay_reconciles(db_path: Path) -> bool:
    connection = sqlite3.connect(db_path)
    try:
        row = connection.execute(
            """
            SELECT complaint_received_date,
                   first_investigation_activity_date,
                   days_received_to_first_activity
            FROM complaints
            """
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return False
    received = parse_date_or_none(cast(str | None, row[0]))
    first_activity = parse_date_or_none(cast(str | None, row[1]))
    expected = days_between(received, first_activity)
    actual = cast(int | None, row[2])
    return expected is not None and actual == expected


def _source_state(
    record: FacilityReferenceRecord,
    headers: Sequence[str],
) -> str:
    original = record.original_row_json
    for header in headers:
        if header not in original:
            continue
        value = original[header]
        if value is None or not str(value).strip():
            return "blank"
        return "populated"
    return "unavailable"


def _facility_metrics(
    records: Sequence[FacilityReferenceRecord],
) -> dict[str, FieldMetric]:
    metrics: dict[str, FieldMetric] = {}
    for field_id in _FACILITY_FIELD_CONFIG:
        attribute, headers = _FACILITY_FIELD_CONFIG[field_id]
        states = tuple(_source_state(record, headers) for record in records)
        values: tuple[object | None, ...]
        if attribute is None:
            values = tuple(
                record.original_row_json.get(headers[0]) if states[index] != "unavailable" else None
                for index, record in enumerate(records)
            )
        else:
            values = tuple(getattr(record, attribute) for record in records)
        eligible_count = sum(state != "unavailable" for state in states)
        populated_count = sum(
            state == "populated" and value is not None and str(value).strip() != ""
            for state, value in zip(states, values, strict=True)
        )
        null_count = sum(
            state != "unavailable" and value is None
            for state, value in zip(states, values, strict=True)
        )
        blank_count = states.count("blank")
        unavailable_count = states.count("unavailable")
        verified_zero_count = sum(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and value == 0
            and state == "populated"
            for state, value in zip(states, values, strict=True)
        )
        empty_default_count = (
            0
            if attribute is None
            else sum(
                state in {"blank", "unavailable"} and value == ""
                for state, value in zip(states, values, strict=True)
            )
        )
        zero_default_count = sum(
            state in {"blank", "unavailable"}
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
            and value == 0
            for state, value in zip(states, values, strict=True)
        )
        metrics[field_id] = FieldMetric(
            eligible_count=eligible_count,
            populated_count=populated_count,
            null_count=null_count,
            blank_count=blank_count,
            unavailable_count=unavailable_count,
            verified_zero_count=verified_zero_count,
            empty_string_default_count=empty_default_count,
            zero_default_count=zero_default_count,
        )
    return metrics


def _date_collections_ordered(
    records: Sequence[FacilityReferenceRecord],
) -> bool:
    attributes = (
        "all_visit_dates",
        "inspection_visit_dates",
        "other_visit_dates",
    )
    populated = 0
    for record in records:
        for attribute in attributes:
            value = cast(tuple[str, ...] | None, getattr(record, attribute))
            if value is None:
                continue
            populated += 1
            if value != tuple(sorted(set(value))):
                return False
    return populated > 0


def _composite_retained_without_flattening(
    records: Sequence[FacilityReferenceRecord],
) -> bool:
    retained = any(COMPOSITE_SOURCE_HEADER in record.original_row_json for record in records)
    overflow_shapes_valid = all(
        isinstance(
            record.original_row_json[SOURCE_CSV_OVERFLOW_PROVENANCE_KEY],
            list,
        )
        for record in records
        if SOURCE_CSV_OVERFLOW_PROVENANCE_KEY in record.original_row_json
    )
    columns = set(hosted_facility_reference_records.c.keys())
    misleading_column = "complaint_info_date_sub_aleg_inc_aleg_uns_aleg_typea_typeb"
    return (
        retained
        and overflow_shapes_valid
        and misleading_column not in columns
        and not any(hasattr(record, misleading_column) for record in records)
    )


def _long_facility_source_values(
    records: Sequence[FacilityReferenceRecord],
) -> tuple[str, ...]:
    values: list[str] = []
    for record in records:
        for value in record.original_row_json.values():
            if isinstance(value, str) and len(value.strip()) >= 16:
                values.append(value.strip())
    return tuple(values)


def _implementation_import_rows(
    metrics: Mapping[str, FieldMetric],
    *,
    source_rows_by_field: Mapping[str, Mapping[str, object]],
    canonical_import_matches: Mapping[str, bool],
    date_collections_ordered: bool,
    reconciliation_ok: bool,
    idempotence_ok: bool,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for spec in ALLOCATION_SPECS:
        metric = metrics[spec.field_id]
        hosted_row = source_rows_by_field.get(spec.field_id)
        hosted_required = spec.field_id in CANONICAL_FIELD_IDS
        hosted_populated_value = (
            hosted_row.get("populated_count") if hosted_row is not None else None
        )
        hosted_populated = hosted_populated_value if isinstance(hosted_populated_value, int) else 0
        governed_source_case_covered = metric.eligible_count > 0 and (
            metric.populated_count > 0 or metric.blank_count > 0 or metric.null_count > 0
        )
        coverage_ok = governed_source_case_covered and (
            not hosted_required
            or (hosted_populated > 0 and canonical_import_matches.get(spec.field_id, False))
        )
        ordering_status = (
            "PASS"
            if spec.field_id not in DATE_COLLECTION_FIELD_IDS or date_collections_ordered
            else "FAIL"
        )
        reconciliation_status = (
            "PASS"
            if spec.field_id != "complaint.days_received_to_first_activity" or reconciliation_ok
            else "FAIL"
        )
        assertion_ok = (
            coverage_ok
            and ordering_status == "PASS"
            and reconciliation_status == "PASS"
            and idempotence_ok
        )
        rows.append(
            {
                "field_id": spec.field_id,
                "evidence_scope": "implementation_capability",
                "adapter": _implementation_adapter(spec.field_id),
                "eligible_count": metric.eligible_count,
                "populated_count": metric.populated_count,
                "null_count": metric.null_count,
                "blank_count": metric.blank_count,
                "unavailable_count": metric.unavailable_count,
                "verified_zero_count": metric.verified_zero_count,
                "ordering_status": ordering_status,
                "idempotence_status": "PASS" if idempotence_ok else "FAIL",
                "reconciliation_status": reconciliation_status,
                "inspection_status": "inspected governed local adapters",
                "assertion_status": "PASS" if assertion_ok else "FAIL",
                "evidence_reference": _implementation_evidence_reference(spec.field_id),
            }
        )
    return rows


def _implementation_adapter(field_id: str) -> str:
    if field_id == "complaint.days_received_to_first_activity" or field_id in (
        COMPLAINT_OBSERVATION_FIELD_KEYS
    ):
        return "connector -> SQLite -> artifact builder -> hosted import"
    if field_id in FACILITY_CANONICAL_FIELD_KEYS:
        return (
            "CCLD program-facility fixture adapter -> temporary seeded artifact "
            "-> hosted canonical import"
        )
    return "facility-reference parser -> preload"


def _implementation_evidence_reference(field_id: str) -> str:
    if field_id == "complaint.days_received_to_first_activity" or field_id in (
        COMPLAINT_OBSERVATION_FIELD_KEYS
    ):
        return (
            "governed complaint fixture; SQLite complaint; hosted source-derived "
            "complaint aggregate"
        )
    if field_id in FACILITY_CANONICAL_FIELD_KEYS:
        return (
            "governed CCLD program-facility fixture; temporary in-memory hosted "
            "canonical import; exact source-to-canonical comparison; aggregate-only "
            "output"
        )
    return "governed facility fixtures; hosted facility-reference aggregate"


def _null_rows(
    metrics: Mapping[str, FieldMetric],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for spec in ALLOCATION_SPECS:
        metric = metrics[spec.field_id]
        preserved = metric.empty_string_default_count == 0 and metric.zero_default_count == 0
        rows.append(
            {
                "field_id": spec.field_id,
                "source_blank_count": metric.blank_count,
                "source_unavailable_count": metric.unavailable_count,
                "normalized_null_count": metric.null_count,
                "verified_zero_count": metric.verified_zero_count,
                "empty_string_default_count": metric.empty_string_default_count,
                "zero_default_count": metric.zero_default_count,
                "source_state_preserved": "true" if preserved else "false",
                "assertion_status": "PASS" if preserved else "FAIL",
                "evidence_reference": (
                    "governed fixture source-state and typed allocation aggregates"
                ),
            }
        )
    return rows


def _exercise_canonical_allocation_migration(
    repo_root: Path,
) -> dict[str, object]:
    migration_path = repo_root / "migrations" / "versions" / "20260714_0007_canonical_allocation.py"
    if not migration_path.is_file():
        raise EvidenceExecutionError("The governed canonical-allocation migration is unavailable.")
    spec = importlib.util.spec_from_file_location(
        "canonical_allocation_evidence_migration",
        migration_path,
    )
    if spec is None or spec.loader is None:
        raise EvidenceExecutionError(
            "The governed canonical-allocation migration could not be loaded."
        )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    upgrade = getattr(migration, "upgrade", None)
    revision_ok = getattr(
        migration, "revision", None
    ) == CANONICAL_ALLOCATION_MIGRATION_REVISION and callable(upgrade)
    if not revision_ok:
        raise EvidenceExecutionError(
            "The governed canonical-allocation migration revision is invalid."
        )

    table_name = hosted_facility_reference_records.name
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    f"""
                    CREATE TABLE {table_name} (
                        source_resource_id VARCHAR(128) NOT NULL,
                        facility_number VARCHAR(32) NOT NULL,
                        facility_name TEXT NOT NULL,
                        closed_date VARCHAR(10),
                        PRIMARY KEY (source_resource_id, facility_number)
                    )
                    """
                )
            )
            connection.execute(
                text(
                    f"""
                    INSERT INTO {table_name} (
                        source_resource_id,
                        facility_number,
                        facility_name,
                        closed_date
                    ) VALUES (
                        'pre-migration-resource',
                        'existing-row',
                        'Existing row',
                        '2026-01-02'
                    )
                    """
                )
            )
            before_count = int(
                connection.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one()
            )
            columns_before = {
                str(column["name"]) for column in sa_inspect(connection).get_columns(table_name)
            }

            migration_runtime = cast(Any, migration)
            migration_runtime.op = Operations(MigrationContext.configure(connection))
            cast(Any, upgrade)()

            columns_after_detail = {
                str(column["name"]): column
                for column in sa_inspect(connection).get_columns(table_name)
            }
            after_count = int(
                connection.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one()
            )
            row = (
                connection.execute(
                    text(
                        f"""
                    SELECT
                        source_resource_id,
                        facility_number,
                        facility_name,
                        closed_date,
                        all_visit_dates,
                        inspection_visit_dates,
                        other_visit_dates,
                        client_served
                    FROM {table_name}
                    """
                    )
                )
                .mappings()
                .one()
            )
    finally:
        engine.dispose()

    columns_added = all(
        column not in columns_before and column in columns_after_detail
        for column in CANONICAL_ALLOCATION_MIGRATION_COLUMNS
    )
    columns_nullable = all(
        bool(columns_after_detail[column]["nullable"])
        for column in CANONICAL_ALLOCATION_MIGRATION_COLUMNS
        if column in columns_after_detail
    ) and all(column in columns_after_detail for column in CANONICAL_ALLOCATION_MIGRATION_COLUMNS)
    existing_values_preserved = (
        row["source_resource_id"] == "pre-migration-resource"
        and row["facility_number"] == "existing-row"
        and row["facility_name"] == "Existing row"
        and row["closed_date"] == "2026-01-02"
    )
    new_values_are_null = all(
        row[column] is None for column in CANONICAL_ALLOCATION_MIGRATION_COLUMNS
    )
    existing_rows_readable = (
        before_count == after_count == 1 and existing_values_preserved and new_values_are_null
    )
    return {
        "revision_ok": revision_ok,
        "columns_added": columns_added,
        "columns_nullable": columns_nullable,
        "existing_row_count_before": before_count,
        "existing_row_count_after": after_count,
        "existing_rows_readable": existing_rows_readable,
        "new_values_are_null": new_values_are_null,
    }


def _exercise_complaint_observation_migration(
    repo_root: Path,
) -> dict[str, object]:
    migration_path = (
        repo_root
        / "migrations"
        / "versions"
        / "20260723_0013_complaint_report_canonical_observations.py"
    )
    if not migration_path.is_file():
        raise EvidenceExecutionError(
            "The governed complaint-observation migration is unavailable."
        )
    spec = importlib.util.spec_from_file_location(
        "complaint_observation_evidence_migration",
        migration_path,
    )
    if spec is None or spec.loader is None:
        raise EvidenceExecutionError(
            "The governed complaint-observation migration could not be loaded."
        )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    upgrade = getattr(migration, "upgrade", None)
    downgrade = getattr(migration, "downgrade", None)
    revision_ok = (
        getattr(migration, "revision", None)
        == COMPLAINT_OBSERVATION_MIGRATION_REVISION
        and callable(upgrade)
        and callable(downgrade)
    )
    if not revision_ok:
        raise EvidenceExecutionError(
            "The governed complaint-observation migration revision is invalid."
        )

    table_name = hosted_source_derived_records.name
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    f"""
                    CREATE TABLE {table_name} (
                        stable_identity VARCHAR(255) PRIMARY KEY,
                        entity_type VARCHAR(32) NOT NULL,
                        original_values JSON NOT NULL
                    )
                    """
                )
            )
            connection.execute(
                text(
                    f"""
                    INSERT INTO {table_name} (
                        stable_identity,
                        entity_type,
                        original_values
                    ) VALUES (
                        'existing-complaint',
                        'complaint',
                        '{{}}'
                    )
                    """
                )
            )
            before_count = _table_count(connection, table_name)
            columns_before = {
                str(column["name"])
                for column in sa_inspect(connection).get_columns(table_name)
            }
            migration_runtime = cast(Any, migration)
            migration_runtime.op = Operations(MigrationContext.configure(connection))
            cast(Any, upgrade)()
            columns_after_detail = {
                str(column["name"]): column
                for column in sa_inspect(connection).get_columns(table_name)
            }
            after_count = _table_count(connection, table_name)
            row = connection.execute(
                text(
                    f"""
                    SELECT stable_identity, agency_name, deficiency_texts,
                           investigation_findings_narrative,
                           complaint_report_contact
                    FROM {table_name}
                    """
                )
            ).mappings().one()
            cast(Any, downgrade)()
            columns_after_downgrade = {
                str(column["name"])
                for column in sa_inspect(connection).get_columns(table_name)
            }
            downgraded_count = _table_count(connection, table_name)
            cast(Any, upgrade)()
            columns_after_reupgrade = {
                str(column["name"])
                for column in sa_inspect(connection).get_columns(table_name)
            }
            reupgraded_count = _table_count(connection, table_name)
    finally:
        engine.dispose()

    columns_added = all(
        column not in columns_before and column in columns_after_detail
        for column in COMPLAINT_OBSERVATION_MIGRATION_COLUMNS
    )
    columns_nullable = all(
        column in columns_after_detail
        and bool(columns_after_detail[column]["nullable"])
        for column in COMPLAINT_OBSERVATION_MIGRATION_COLUMNS
    )
    new_values_are_null = all(
        row[column] is None for column in COMPLAINT_OBSERVATION_MIGRATION_COLUMNS
    )
    existing_rows_readable = (
        before_count
        == after_count
        == downgraded_count
        == reupgraded_count
        == 1
        and row["stable_identity"] == "existing-complaint"
    )
    return {
        "revision_ok": revision_ok,
        "columns_added": columns_added,
        "columns_nullable": columns_nullable,
        "existing_row_count_before": before_count,
        "existing_row_count_after": after_count,
        "existing_rows_readable": existing_rows_readable,
        "new_values_are_null": new_values_are_null,
        "downgrade_removed_columns": all(
            column not in columns_after_downgrade
            for column in COMPLAINT_OBSERVATION_MIGRATION_COLUMNS
        ),
        "reupgrade_restored_columns": all(
            column in columns_after_reupgrade
            for column in COMPLAINT_OBSERVATION_MIGRATION_COLUMNS
        ),
    }


def _migration_rows(
    *,
    sqlite_counts_before: Mapping[str, int],
    sqlite_counts_after: Mapping[str, int],
    hosted_count_before: int,
    hosted_count_after: int,
    migration_exercise: Mapping[str, object],
    complaint_migration_exercise: Mapping[str, object],
) -> list[dict[str, object]]:
    sqlite_safe = (
        dict(sqlite_counts_before) == dict(sqlite_counts_after)
        and sqlite_counts_after.get("complaints", 0) > 0
    )
    hosted_safe = hosted_count_before == hosted_count_after and hosted_count_after > 0
    reference_safe = all(
        bool(migration_exercise[key])
        for key in (
            "revision_ok",
            "columns_added",
            "columns_nullable",
            "existing_rows_readable",
            "new_values_are_null",
        )
    )
    complaint_observation_safe = all(
        bool(complaint_migration_exercise[key])
        for key in (
            "revision_ok",
            "columns_added",
            "columns_nullable",
            "existing_rows_readable",
            "new_values_are_null",
            "downgrade_removed_columns",
            "reupgrade_restored_columns",
        )
    )
    return [
        {
            "check_id": "sqlite_existing_canonical_shape",
            "layer": "SQLite canonical storage",
            "change_kind": "existing columns; idempotent initialization",
            "expected_behavior": "existing rows remain readable without rewrite",
            "existing_row_count_before": sqlite_counts_before.get("complaints", 0),
            "existing_row_count_after": sqlite_counts_after.get("complaints", 0),
            "existing_rows_readable": "true" if sqlite_safe else "false",
            "nullable_or_default_status": "existing governed definitions retained",
            "destructive_rewrite_performed": "false",
            "assertion_status": "PASS" if sqlite_safe else "FAIL",
            "evidence_reference": "SQLite initializer and complaint aggregate",
        },
        {
            "check_id": "hosted_source_derived_json_shape",
            "layer": "hosted source-derived import",
            "change_kind": "existing JSON allocation; idempotent upsert",
            "expected_behavior": "existing rows remain readable without rewrite",
            "existing_row_count_before": hosted_count_before,
            "existing_row_count_after": hosted_count_after,
            "existing_rows_readable": "true" if hosted_safe else "false",
            "nullable_or_default_status": "source-derived nulls retained in JSON",
            "destructive_rewrite_performed": "false",
            "assertion_status": "PASS" if hosted_safe else "FAIL",
            "evidence_reference": "hosted seeded-corpus import aggregate",
        },
        {
            "check_id": "facility_reference_alembic_20260714_0007",
            "layer": "hosted facility-reference preload",
            "change_kind": "additive nullable typed columns",
            "expected_behavior": "existing rows remain readable without rewrite",
            "existing_row_count_before": migration_exercise["existing_row_count_before"],
            "existing_row_count_after": migration_exercise["existing_row_count_after"],
            "existing_rows_readable": "true" if reference_safe else "false",
            "nullable_or_default_status": (
                "Alembic 20260714_0007 added four nullable columns; existing-row "
                "values read as SQL null"
            ),
            "destructive_rewrite_performed": "false",
            "assertion_status": "PASS" if reference_safe else "FAIL",
            "evidence_reference": (
                "executed Alembic revision 20260714_0007 against an existing-row "
                "pre-migration SQLite schema"
            ),
        },
        {
            "check_id": "complaint_observations_alembic_20260723_0013",
            "layer": "hosted source-derived canonical complaint observations",
            "change_kind": "additive nullable columns",
            "expected_behavior": (
                "upgrade, downgrade, and re-upgrade preserve existing rows"
            ),
            "existing_row_count_before": complaint_migration_exercise[
                "existing_row_count_before"
            ],
            "existing_row_count_after": complaint_migration_exercise[
                "existing_row_count_after"
            ],
            "existing_rows_readable": (
                "true" if complaint_observation_safe else "false"
            ),
            "nullable_or_default_status": (
                "Alembic 20260723_0013 adds four nullable columns; existing-row "
                "values read as SQL null"
            ),
            "destructive_rewrite_performed": "false",
            "assertion_status": "PASS" if complaint_observation_safe else "FAIL",
            "evidence_reference": (
                "executed Alembic revision 20260723_0013 upgrade, downgrade, "
                "and re-upgrade against an existing-row SQLite schema"
            ),
        },
    ]


def _configured_runtime_population(
    environ: Mapping[str, str],
    repo_root: Path,
) -> dict[str, object]:
    engine: Engine | None = None
    try:
        database_config = load_hosted_database_config(
            environ,
            repo_root,
            require_url=True,
        )
        engine = create_engine(cast(str, database_config.database_url))
        if engine.dialect.name != "postgresql":
            raise EvidenceExecutionError(
                "Runtime evidence requires a configured PostgreSQL database."
            )
        with engine.connect() as connection:
            return _runtime_population(connection)
    except HostedDatabaseConfigError as exc:
        raise EvidenceExecutionError(
            "Runtime evidence requires a configured PostgreSQL database."
        ) from exc
    except SQLAlchemyError as exc:
        raise EvidenceExecutionError(
            "The configured runtime database could not be inspected safely."
        ) from exc
    finally:
        if engine is not None:
            engine.dispose()


def _runtime_population(connection: Connection) -> dict[str, object]:
    source_rows, source_status, source_count = _runtime_source_population(connection)
    reference_rows, reference_status, reference_count = _runtime_reference_population(connection)
    return {
        "hosted_source_derived": source_rows,
        "facility_reference": reference_rows,
        "hosted_source_derived_status": source_status,
        "facility_reference_status": reference_status,
        "hosted_source_derived_record_count": source_count,
        "facility_reference_record_count": reference_count,
    }


def _runtime_source_population(
    connection: Connection,
) -> tuple[list[dict[str, object]], str, int | None]:
    inspector = sa_inspect(connection)
    if "hosted_source_derived_records" not in inspector.get_table_names():
        return (
            _unavailable_population_rows(
                (field_id for field_id, _entity, _column in _RUNTIME_SOURCE_FIELDS),
                "hosted_source_derived_records",
                "table unavailable",
            ),
            "unavailable: hosted source-derived table not found",
            None,
        )
    column_names = {
        str(column["name"]) for column in inspector.get_columns("hosted_source_derived_records")
    }
    if not {"entity_type", "original_values"}.issubset(column_names):
        return (
            _unavailable_population_rows(
                (field_id for field_id, _entity, _column in _RUNTIME_SOURCE_FIELDS),
                "hosted_source_derived_records",
                "required columns unavailable",
            ),
            "unavailable: hosted source-derived columns not found",
            _table_count(connection, "hosted_source_derived_records"),
        )
    record_count = _table_count(connection, "hosted_source_derived_records")
    rows = [
        _json_population_row(
            connection,
            table_name="hosted_source_derived_records",
            json_column="original_values",
            field_id=field_id,
            json_key=json_key,
            adapter="hosted_source_derived_records",
            where_sql="entity_type = :entity_type",
            parameters={"entity_type": entity_type},
        )
        for field_id, entity_type, json_key in _RUNTIME_SOURCE_FIELDS
    ]
    return rows, "inspected aggregate-only", record_count


def _runtime_reference_population(
    connection: Connection,
) -> tuple[list[dict[str, object]], str, int | None]:
    table_name = "hosted_facility_reference_records"
    inspector = sa_inspect(connection)
    field_ids = tuple(_RUNTIME_REFERENCE_COLUMNS) + (_COMPOSITE_FIELD_ID,)
    if table_name not in inspector.get_table_names():
        return (
            _unavailable_population_rows(
                field_ids,
                table_name,
                "table unavailable",
            ),
            "unavailable: facility-reference table not found",
            None,
        )
    columns = {str(column["name"]) for column in inspector.get_columns(table_name)}
    record_count = _table_count(connection, table_name)
    rows: list[dict[str, object]] = []
    for field_id, column_name in _RUNTIME_REFERENCE_COLUMNS.items():
        if column_name not in columns:
            rows.append(
                _unavailable_population_row(
                    field_id,
                    table_name,
                    "column unavailable",
                    unavailable_count=record_count,
                )
            )
            continue
        if field_id in DATE_COLLECTION_FIELD_IDS:
            rows.append(
                _json_array_column_population_row(
                    connection,
                    table_name=table_name,
                    column_name=column_name,
                    field_id=field_id,
                )
            )
        else:
            rows.append(
                _scalar_column_population_row(
                    connection,
                    table_name=table_name,
                    column_name=column_name,
                    field_id=field_id,
                    numeric=field_id == "facility.capacity",
                )
            )
    if "original_row_json" not in columns:
        rows.append(
            _unavailable_population_row(
                _COMPOSITE_FIELD_ID,
                table_name,
                "original-row column unavailable",
                unavailable_count=record_count,
            )
        )
    else:
        rows.append(
            _json_population_row(
                connection,
                table_name=table_name,
                json_column="original_row_json",
                field_id=_COMPOSITE_FIELD_ID,
                json_key=COMPOSITE_SOURCE_HEADER,
                adapter=table_name,
                where_sql=None,
                parameters={},
            )
        )
    ordered_rows = sorted(rows, key=lambda row: FIELD_IDS.index(str(row["field_id"])))
    return ordered_rows, "inspected aggregate-only", record_count


def _table_count(connection: Connection, table_name: str) -> int:
    allowed = {
        "hosted_source_derived_records",
        "hosted_facility_reference_records",
    }
    if table_name not in allowed:
        raise ValueError("Unsupported aggregate evidence table.")
    return int(connection.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one())


def _json_population_row(
    connection: Connection,
    *,
    table_name: str,
    json_column: str,
    field_id: str,
    json_key: str,
    adapter: str,
    where_sql: str | None,
    parameters: Mapping[str, object],
) -> dict[str, object]:
    allowed_pairs = {
        ("hosted_source_derived_records", "original_values"),
        ("hosted_facility_reference_records", "original_row_json"),
    }
    if (table_name, json_column) not in allowed_pairs:
        raise ValueError("Unsupported aggregate JSON evidence column.")
    where_clause = f" WHERE {where_sql}" if where_sql is not None else ""
    query_parameters = {**dict(parameters), "json_key": json_key}
    if connection.dialect.name == "postgresql":
        statement = text(
            f"""
            SELECT
                COUNT(*) AS eligible_count,
                COUNT(*) FILTER (
                    WHERE jsonb_exists(CAST({json_column} AS jsonb), :json_key)
                      AND jsonb_typeof(
                            CAST({json_column} AS jsonb) -> :json_key
                          ) <> 'null'
                      AND BTRIM(
                            COALESCE(
                              jsonb_extract_path_text(
                                CAST({json_column} AS jsonb),
                                :json_key
                              ),
                              ''
                            )
                          ) <> ''
                ) AS populated_count,
                COUNT(*) FILTER (
                    WHERE jsonb_exists(CAST({json_column} AS jsonb), :json_key)
                      AND jsonb_typeof(
                            CAST({json_column} AS jsonb) -> :json_key
                          ) = 'null'
                ) AS null_count,
                COUNT(*) FILTER (
                    WHERE jsonb_exists(CAST({json_column} AS jsonb), :json_key)
                      AND jsonb_typeof(
                            CAST({json_column} AS jsonb) -> :json_key
                          ) = 'string'
                      AND BTRIM(
                            COALESCE(
                              jsonb_extract_path_text(
                                CAST({json_column} AS jsonb),
                                :json_key
                              ),
                              ''
                            )
                          ) = ''
                ) AS blank_count,
                COUNT(*) FILTER (
                    WHERE NOT jsonb_exists(
                      CAST({json_column} AS jsonb),
                      :json_key
                    )
                ) AS unavailable_count,
                COUNT(*) FILTER (
                    WHERE jsonb_typeof(
                            CAST({json_column} AS jsonb) -> :json_key
                          ) = 'number'
                      AND CAST(
                            jsonb_extract_path_text(
                              CAST({json_column} AS jsonb),
                              :json_key
                            ) AS numeric
                          ) = 0
                ) AS verified_zero_count
            FROM {table_name}{where_clause}
            """
        )
    else:
        query_parameters["json_path"] = f"$.{json.dumps(json_key)}"
        statement = text(
            f"""
            SELECT
                COUNT(*) AS eligible_count,
                SUM(
                  CASE
                    WHEN json_type({json_column}, :json_path) IS NOT NULL
                     AND json_type({json_column}, :json_path) <> 'null'
                     AND TRIM(
                           COALESCE(
                             CAST(json_extract({json_column}, :json_path) AS TEXT),
                             ''
                           )
                         ) <> ''
                    THEN 1 ELSE 0
                  END
                ) AS populated_count,
                SUM(
                  CASE WHEN json_type({json_column}, :json_path) = 'null'
                       THEN 1 ELSE 0 END
                ) AS null_count,
                SUM(
                  CASE
                    WHEN json_type({json_column}, :json_path) = 'text'
                     AND TRIM(
                           COALESCE(
                             CAST(json_extract({json_column}, :json_path) AS TEXT),
                             ''
                           )
                         ) = ''
                    THEN 1 ELSE 0
                  END
                ) AS blank_count,
                SUM(
                  CASE WHEN json_type({json_column}, :json_path) IS NULL
                       THEN 1 ELSE 0 END
                ) AS unavailable_count,
                SUM(
                  CASE
                    WHEN json_type({json_column}, :json_path) IN ('integer', 'real')
                     AND json_extract({json_column}, :json_path) = 0
                    THEN 1 ELSE 0
                  END
                ) AS verified_zero_count
            FROM {table_name}{where_clause}
            """
        )
    result = connection.execute(statement, query_parameters).mappings().one()
    return _population_row_from_result(field_id, adapter, result)


def _scalar_column_population_row(
    connection: Connection,
    *,
    table_name: str,
    column_name: str,
    field_id: str,
    numeric: bool,
) -> dict[str, object]:
    if table_name != "hosted_facility_reference_records":
        raise ValueError("Unsupported aggregate scalar evidence table.")
    if column_name not in set(_RUNTIME_REFERENCE_COLUMNS.values()):
        raise ValueError("Unsupported aggregate scalar evidence column.")
    verified_zero_sql = f"SUM(CASE WHEN {column_name} = 0 THEN 1 ELSE 0 END)" if numeric else "0"
    result = (
        connection.execute(
            text(
                f"""
            SELECT
                COUNT(*) AS eligible_count,
                SUM(
                  CASE
                    WHEN {column_name} IS NOT NULL
                     AND TRIM(CAST({column_name} AS TEXT)) <> ''
                    THEN 1 ELSE 0
                  END
                ) AS populated_count,
                SUM(
                  CASE WHEN {column_name} IS NULL THEN 1 ELSE 0 END
                ) AS null_count,
                SUM(
                  CASE
                    WHEN {column_name} IS NOT NULL
                     AND TRIM(CAST({column_name} AS TEXT)) = ''
                    THEN 1 ELSE 0
                  END
                ) AS blank_count,
                0 AS unavailable_count,
                {verified_zero_sql} AS verified_zero_count
            FROM {table_name}
            """
            )
        )
        .mappings()
        .one()
    )
    return _population_row_from_result(field_id, table_name, result)


def _json_array_column_population_row(
    connection: Connection,
    *,
    table_name: str,
    column_name: str,
    field_id: str,
) -> dict[str, object]:
    if table_name != "hosted_facility_reference_records":
        raise ValueError("Unsupported aggregate date-array evidence table.")
    if column_name not in {
        "all_visit_dates",
        "inspection_visit_dates",
        "other_visit_dates",
    }:
        raise ValueError("Unsupported aggregate date-array evidence column.")
    if connection.dialect.name == "postgresql":
        statement = text(
            f"""
            SELECT
                COUNT(*) AS eligible_count,
                COUNT(*) FILTER (
                    WHERE {column_name} IS NOT NULL
                      AND jsonb_typeof(CAST({column_name} AS jsonb)) = 'array'
                      AND jsonb_array_length(CAST({column_name} AS jsonb)) > 0
                ) AS populated_count,
                COUNT(*) FILTER (
                    WHERE {column_name} IS NULL
                ) AS null_count,
                COUNT(*) FILTER (
                    WHERE {column_name} IS NOT NULL
                      AND jsonb_typeof(CAST({column_name} AS jsonb)) = 'array'
                      AND jsonb_array_length(CAST({column_name} AS jsonb)) = 0
                ) AS blank_count,
                0 AS unavailable_count,
                0 AS verified_zero_count
            FROM {table_name}
            """
        )
    else:
        statement = text(
            f"""
            SELECT
                COUNT(*) AS eligible_count,
                SUM(
                  CASE
                    WHEN {column_name} IS NOT NULL
                     AND json_type({column_name}) = 'array'
                     AND json_array_length({column_name}) > 0
                    THEN 1 ELSE 0
                  END
                ) AS populated_count,
                SUM(
                  CASE WHEN {column_name} IS NULL THEN 1 ELSE 0 END
                ) AS null_count,
                SUM(
                  CASE
                    WHEN {column_name} IS NOT NULL
                     AND json_type({column_name}) = 'array'
                     AND json_array_length({column_name}) = 0
                    THEN 1 ELSE 0
                  END
                ) AS blank_count,
                0 AS unavailable_count,
                0 AS verified_zero_count
            FROM {table_name}
            """
        )
    result = connection.execute(statement).mappings().one()
    return _population_row_from_result(field_id, table_name, result)


def _population_row_from_result(
    field_id: str,
    adapter: str,
    result: RowMapping,
) -> dict[str, object]:
    return {
        "field_id": field_id,
        "adapter": adapter,
        "eligible_count": _aggregate_int(result.get("eligible_count")),
        "populated_count": _aggregate_int(result.get("populated_count")),
        "null_count": _aggregate_int(result.get("null_count")),
        "blank_count": _aggregate_int(result.get("blank_count")),
        "unavailable_count": _aggregate_int(result.get("unavailable_count")),
        "verified_zero_count": _aggregate_int(result.get("verified_zero_count")),
        "inspection_status": "inspected aggregate-only",
    }


def _aggregate_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        return int(value)
    return 0


def _unavailable_population_rows(
    field_ids: Iterable[str],
    adapter: str,
    reason: str,
) -> list[dict[str, object]]:
    return [_unavailable_population_row(field_id, adapter, reason) for field_id in tuple(field_ids)]


def _unavailable_population_row(
    field_id: str,
    adapter: str,
    reason: str,
    *,
    unavailable_count: int | None = None,
) -> dict[str, object]:
    return {
        "field_id": field_id,
        "adapter": adapter,
        "eligible_count": None,
        "populated_count": None,
        "null_count": None,
        "blank_count": None,
        "unavailable_count": unavailable_count,
        "verified_zero_count": None,
        "inspection_status": f"unavailable: {reason}",
    }


def _runtime_import_row(row: Mapping[str, object]) -> dict[str, object]:
    inspection_status = str(row["inspection_status"])
    inspected = inspection_status.startswith("inspected")
    return {
        "field_id": row["field_id"],
        "evidence_scope": "runtime_population",
        "adapter": row["adapter"],
        "eligible_count": row["eligible_count"],
        "populated_count": row["populated_count"],
        "null_count": row["null_count"],
        "blank_count": row["blank_count"],
        "unavailable_count": row["unavailable_count"],
        "verified_zero_count": row["verified_zero_count"],
        "ordering_status": "validated by local regression",
        "idempotence_status": "validated by local regression",
        "reconciliation_status": "validated by local regression",
        "inspection_status": inspection_status,
        "assertion_status": "PASS" if inspected else "UNAVAILABLE",
        "evidence_reference": "runtime aggregate query; no record values selected",
    }


def _gap_rows(
    allocation_rows: Sequence[Mapping[str, object]],
    import_rows: Sequence[Mapping[str, object]],
    *,
    mode: EvidenceMode,
    runtime_source_rows: Sequence[Mapping[str, object]],
    runtime_reference_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    allocation_by_field = {str(row["field_id"]): row for row in allocation_rows}
    import_by_field = {str(row["field_id"]): row for row in import_rows}
    runtime_fields = {
        str(row["field_id"])
        for row in tuple(runtime_source_rows) + tuple(runtime_reference_rows)
        if str(row["inspection_status"]).startswith("inspected")
    }
    rows: list[dict[str, object]] = []
    for spec in ALLOCATION_SPECS:
        allocation = allocation_by_field[spec.field_id]
        implementation = import_by_field[spec.field_id]
        assertion_ok = (
            allocation["assertion_status"] == "PASS"
            and implementation["assertion_status"] == "PASS"
        )
        if mode == "local":
            runtime_status = "NOT_INSPECTED_LOCAL_MODE"
        elif spec.field_id in runtime_fields:
            runtime_status = "INSPECTED_SEPARATELY"
        else:
            runtime_status = "UNAVAILABLE"
        rows.append(
            {
                "field_id": spec.field_id,
                "prior_gap_status": "ISSUE_447_GOVERNED_ALLOCATION_GAP",
                "allocation_decision": spec.allocation_decision,
                "canonical_storage_status": _storage_status(spec),
                "importer_initializer_status": implementation["assertion_status"],
                "regression_status": ("PASS" if assertion_ok else "FAIL"),
                "runtime_population_status": runtime_status,
                "existing_data_status": "REFRESH_REQUIRED",
                "assertion_status": "PASS" if assertion_ok else "FAIL",
            }
        )
    return rows


def _storage_status(spec: AllocationSpec) -> str:
    if spec.allocation_decision == "existing_canonical":
        return "ALLOCATED_EXISTING_CANONICAL"
    if spec.allocation_decision == "typed_source_reference":
        return "ALLOCATED_TYPED_SOURCE_REFERENCE"
    return "RETAINED_RAW_ONLY_WITHOUT_FLATTENING"


def _aggregate_safe(
    payloads: Sequence[object],
    source_values: Sequence[str],
    repo_root: Path,
) -> bool:
    serialized = json.dumps(payloads, ensure_ascii=True, sort_keys=True)
    lowered = serialized.casefold()
    blocked_fragments = (
        str(repo_root),
        str(repo_root).replace("\\", "/"),
        "c:\\users\\",
        "c:/users/",
        "/home/",
        "http://",
        "https://",
        "postgresql://",
        "postgresql+",
        "sqlite://",
    )
    if any(fragment.casefold() in lowered for fragment in blocked_fragments):
        return False
    if any(identifier in serialized for identifier in SYNTHETIC_FACILITY_IDS):
        return False
    for source_value in source_values:
        cleaned = source_value.strip()
        if cleaned and cleaned in serialized:
            return False
    return True


def _synthetic_facility_ids_absent(payloads: Sequence[object]) -> bool:
    serialized = json.dumps(payloads, ensure_ascii=True, sort_keys=True)
    return all(identifier not in serialized for identifier in SYNTHETIC_FACILITY_IDS)


def _write_outputs(
    output_dir: Path,
    *,
    manifest: Mapping[str, object],
    allocation_rows: Sequence[Mapping[str, object]],
    import_rows: Sequence[Mapping[str, object]],
    null_rows: Sequence[Mapping[str, object]],
    migration_rows: Sequence[Mapping[str, object]],
    gap_rows: Sequence[Mapping[str, object]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for file_name in OUTPUT_FILES:
        path = output_dir / file_name
        if path.exists() and path.is_file():
            path.unlink()
    _write_json(output_dir / "manifest.json", manifest)
    _write_csv(
        output_dir / "allocation-results.csv",
        allocation_rows,
        ALLOCATION_FIELDNAMES,
    )
    _write_csv(
        output_dir / "import-results.csv",
        import_rows,
        IMPORT_FIELDNAMES,
    )
    _write_csv(
        output_dir / "null-semantics-results.csv",
        null_rows,
        NULL_FIELDNAMES,
    )
    _write_csv(
        output_dir / "migration-results.csv",
        migration_rows,
        MIGRATION_FIELDNAMES,
    )
    _write_csv(
        output_dir / "gap-status.csv",
        gap_rows,
        GAP_FIELDNAMES,
    )
    summary = _summary_markdown(manifest)
    safe_summary = cast(str, sanitize_payload(summary))
    (output_dir / "summary.md").write_text(
        safe_summary,
        encoding="utf-8",
        newline="\n",
    )


def _write_json(path: Path, payload: object) -> None:
    safe_payload = sanitize_payload(payload)
    path.write_text(
        json.dumps(
            safe_payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, object]],
    fieldnames: Sequence[str],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=list(fieldnames),
            extrasaction="raise",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            safe_row = cast(
                Mapping[str, object],
                sanitize_payload(dict(row)),
            )
            writer.writerow(safe_row)


def _summary_markdown(manifest: Mapping[str, object]) -> str:
    counts = cast(Mapping[str, object], manifest["counts"])
    assertions = cast(Mapping[str, bool], manifest["assertions"])
    runtime = cast(Mapping[str, object], manifest["runtime_population"])
    source_runtime = cast(Mapping[str, object], runtime["hosted_source_derived"])
    reference_runtime = cast(Mapping[str, object], runtime["facility_reference"])
    refresh = cast(Mapping[str, object], manifest["existing_data_refresh"])
    status = "PASS" if all(bool(value) for value in assertions.values()) else "FAIL"
    return "\n".join(
        (
            "# Canonical allocation evidence",
            "",
            f"Overall assertion status: {status}.",
            "",
            (f"Governed allocation fields: {counts['allocation_fields']}."),
            (f"Assertions passed: {counts['assertions_passed']} of {counts['assertions_total']}."),
            "",
            "## Runtime population",
            "",
            (f"Hosted source-derived adapter: {source_runtime['status']}."),
            (f"Facility-reference adapter: {reference_runtime['status']}."),
            ("Implementation capability and runtime population are reported separately."),
            "",
            "## Existing data refresh",
            "",
            str(refresh["postgresql_source_derived"]),
            str(refresh["facility_reference"]),
            str(refresh["safe_command_status"]),
            "",
            "## Safety",
            "",
            (
                "Outputs contain structural allocation decisions and aggregate counts "
                "only. They exclude source bodies, record identifiers, connection "
                "strings, private locations, and raw filesystem paths."
            ),
            "",
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Verify governed issue 447 field allocations through local capability "
            "and optional runtime aggregate population adapters."
        )
    )
    parser.add_argument(
        "--mode",
        choices=("local", "runtime"),
        default="local",
        help="local capability evidence or runtime PostgreSQL aggregate evidence",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="directory for generated untracked evidence files",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = run_evidence(
            mode=cast(EvidenceMode, args.mode),
            output_dir=cast(Path, args.output_dir),
        )
    except (EvidenceExecutionError, ValueError) as exc:
        print(
            "canonical-allocation evidence failed: "
            + redact_sensitive_text(str(exc), redact_urls=True),
            file=sys.stderr,
        )
        return 2
    except OSError:
        print(
            "canonical-allocation evidence failed: inputs or outputs could not be accessed.",
            file=sys.stderr,
        )
        return 2
    assertions = cast(Mapping[str, bool], manifest["assertions"])
    passed = sum(bool(value) for value in assertions.values())
    total = len(assertions)
    print(f"canonical-allocation evidence complete: {passed} of {total} assertions passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
