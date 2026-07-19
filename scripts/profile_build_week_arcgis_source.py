from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ccld_complaints.arcgis_facility_source_evaluation import (
    ARCGIS_ITEM_ID,
    ARCGIS_LAYER_PATH,
    ARCGIS_QUERY_PATH,
    ARCGIS_SERVICE_PATH,
    FIELD_CANDIDATES,
    OUTPUT_TYPES,
    PROGRAM_RESOURCE_IDS,
    CapturedArtifact,
    EndpointPolicyError,
    analyze_complete_pagination,
    approve_redirect,
    assert_approved_url,
    assert_response_safe_to_retain,
    choose_recommendation,
    classify_duplicate_facility_groups,
    compare_export_query,
    compare_observations,
    compare_program_sources,
    decision_payload,
    investigate_code_733,
    load_schema,
    normalize_scalar,
    output_envelope,
    parse_export_bytes,
    profile_layer_metadata,
    project_rows,
    resolve_projection_fields,
    validate_csv_export_response,
    write_captured_bytes,
    write_output_package,
)
from ccld_complaints.statewide_facility_source_evaluation import (
    canonical_fingerprint,
    extract_public_urls_from_html,
    find_named_objects,
    parse_next_data_payload,
    rows_from_arcgis_response,
    sanitize_url,
)

SERVICE_URL: Final = f"https://services.arcgis.com{ARCGIS_SERVICE_PATH}"
LAYER_URL: Final = f"https://services.arcgis.com{ARCGIS_LAYER_PATH}"
QUERY_URL: Final = f"https://services.arcgis.com{ARCGIS_QUERY_PATH}"
EXPORT_URL: Final = (
    "https://gis.data.chhs.ca.gov/api/download/v1/items/"
    f"{ARCGIS_ITEM_ID}/csv?layers=0"
)
CATALOG_ENDPOINTS: Final[tuple[tuple[str, str], ...]] = (
    (
        "lab-program-csv",
        "https://lab.data.ca.gov/dataset/community-care-licensing-facilities",
    ),
    (
        "lab-arcgis-1",
        "https://lab.data.ca.gov/dataset/community-care-licensing-facilities1",
    ),
    (
        "lab-arcgis-2",
        "https://lab.data.ca.gov/dataset/community-care-licensing-facilities2",
    ),
    (
        "lab-arcgis-3",
        "https://lab.data.ca.gov/dataset/community-care-licensing-facilities3",
    ),
    ("lab-licenses", "https://lab.data.ca.gov/licenses"),
    (
        "chhs-geoportal",
        "https://gis.data.chhs.ca.gov/datasets/CDSS::community-care-licensing-facilities",
    ),
    ("chhs-program-dataset", "https://data.chhs.ca.gov/dataset/ccl-facilities"),
    (
        "data-gov-catalog",
        "https://catalog.data.gov/dataset/community-care-licensing-facilities",
    ),
    ("calhhs-handbook", "https://kb.data.chhs.ca.gov/"),
    ("calhhs-purpose", "https://kb.data.chhs.ca.gov/odp/purpose"),
    ("calhhs-governance", "https://kb.data.chhs.ca.gov/odp/governance"),
    ("calhhs-disclosure", "https://kb.data.chhs.ca.gov/odp/disclosure"),
)
PROGRAM_SOURCE_NAMES: Final[dict[str, str]] = {
    "5bac6551-4d6c-45d6-93b8-e6ded428d98e": "Child Care Centers",
    "6b2f5818-f60d-40b5-bc2a-94f995f9f8b0": (
        "Residential Care Facilities for the Elderly"
    ),
    "87d12c51-d57a-493c-96b7-c7251e32a620": (
        "24-Hour Residential Care for Children"
    ),
    "88e9c2db-6594-4dec-a18b-3e23d07f77cc": "Foster Family Agencies",
    "9a779529-6412-445e-b51e-ecee943e6785": "Home Care Organization",
    "a8615948-c56f-4dba-90f5-5f802490a221": "Family Child Care Homes",
    "dc24ca45-4c7d-4fdc-b793-3db8fab07699": "Adult Residential Facilities",
}


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(  # type: ignore[no-untyped-def]
        self, request, response, code, message, headers, new_url
    ):
        return None


class PublicFetcher:
    def __init__(self, raw_root: Path, observed_at: str, timeout_seconds: float) -> None:
        self.raw_root = raw_root
        self.observed_at = observed_at
        self.timeout_seconds = timeout_seconds
        self.opener = build_opener(_NoRedirectHandler())
        self.artifacts: list[CapturedArtifact] = []
        self.redirect_outcomes: list[dict[str, Any]] = []

    def capture(
        self,
        *,
        endpoint_id: str,
        url: str,
        relative_path: Path,
        source_version_metadata: Mapping[str, Any] | None = None,
    ) -> Path:
        request_url = assert_approved_url(url)
        redirect_chain: list[str] = []
        current_url = request_url
        terminal_redirect_reached = False
        for _redirect_index in range(3):
            request = Request(
                current_url,
                headers={"User-Agent": "RecordsTracker-ArcGIS-shadow-evaluation/1"},
            )
            try:
                response = self.opener.open(request, timeout=self.timeout_seconds)
            except HTTPError as error:
                status = error.code
                body = error.read()
                headers = error.headers
                final_url = error.geturl()
            except (URLError, TimeoutError, OSError):
                raise RuntimeError(
                    f"Public source request failed: {assert_approved_url(request_url)}"
                ) from None
            else:
                with response:
                    status = response.status
                    body = response.read()
                    headers = response.headers
                    final_url = response.geturl()
            media_type = headers.get_content_type()
            location = headers.get("Location")
            if 300 <= status < 400 and location:
                destination = approve_redirect(
                    current_url,
                    location,
                    source_is_terminal=terminal_redirect_reached,
                )
                redirect_chain.append(destination.recorded_url)
                self.redirect_outcomes.append(
                    {
                        "from": sanitize_url(current_url),
                        "to": destination.recorded_url,
                        "status": status,
                        "outcome": "followed_approved_destination",
                    }
                )
                current_url = destination.transport_url
                terminal_redirect_reached = destination.terminal
                continue
            if status < 200 or status >= 300:
                recorded_current_url = assert_approved_url(
                    current_url,
                    allow_opaque_azure_query=terminal_redirect_reached,
                )
                raise RuntimeError(
                    f"Public source returned HTTP {status}: "
                    f"{recorded_current_url}"
                )
            is_export = endpoint_id.endswith("-export")
            assert_response_safe_to_retain(
                body, "text/csv" if is_export else media_type
            )
            artifact_metadata = dict(source_version_metadata or {})
            if is_export:
                artifact_metadata.update(validate_csv_export_response(body))
            artifact_path = self.raw_root / relative_path
            digest = write_captured_bytes(artifact_path, body)
            artifact = CapturedArtifact(
                endpoint_id=endpoint_id,
                request_url=request_url,
                final_url=assert_approved_url(
                    final_url,
                    allow_opaque_azure_query=terminal_redirect_reached,
                ),
                retrieved_at=self.observed_at,
                status=status,
                media_type=media_type,
                byte_count=len(body),
                sha256=digest,
                artifact_ref=artifact_path.as_posix(),
                redirect_chain=tuple(redirect_chain),
                source_version_metadata=artifact_metadata,
            )
            self.artifacts.append(artifact)
            return artifact_path
        raise EndpointPolicyError("Approved redirect limit exceeded.")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture and evaluate the Build Week ArcGIS facility-reference source."
    )
    parser.add_argument("--mode", choices=("live", "fixture"), required=True)
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=Path("data/raw/source-profiling/build-week-arcgis"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="New ignored directory for the versioned evaluation package.",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path("schemas/build-week-2026-arcgis-shadow-evaluation.schema.json"),
    )
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path("tests/fixtures/source_profiling/build_week_arcgis"),
    )
    parser.add_argument("--observed-at", help="Fixed UTC timestamp for deterministic fixture mode.")
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    return parser


def _utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stamp(observed_at: str) -> str:
    return re.sub(r"[^0-9TZ]", "", observed_at)


def _read_json(path: Path) -> dict[str, Any]:
    parsed = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected JSON object: {path.name}")
    if "error" in parsed:
        raise ValueError(f"Public source returned an ArcGIS error object: {path.name}")
    return cast(dict[str, Any], parsed)


def _artifact_for(fetcher: PublicFetcher, endpoint_id: str) -> CapturedArtifact:
    return next(artifact for artifact in fetcher.artifacts if artifact.endpoint_id == endpoint_id)


def _catalog_record(endpoint_id: str, url: str, path: Path) -> dict[str, Any]:
    body = path.read_bytes()
    payload = parse_next_data_payload(body)
    results = [
        value
        for value in find_named_objects(payload, "result")
        if isinstance(value, dict) and (value.get("id") or value.get("title"))
    ]
    result = cast(dict[str, Any], results[0]) if results else {}
    public_urls = extract_public_urls_from_html(body)
    related_urls = [
        url_value
        for url_value in public_urls
        if ARCGIS_ITEM_ID in url_value
        or ARCGIS_SERVICE_PATH.casefold() in urlsplit_path(url_value).casefold()
    ]
    text = body.decode("utf-8", errors="replace")
    license_label = ""
    for label in ("Creative Commons Attribution", "No License Provided"):
        if label.casefold() in text.casefold():
            license_label = label
            break
    return {
        "endpoint_id": endpoint_id,
        "url": url,
        "dataset_id": str(result.get("id", "")),
        "title": str(result.get("title", result.get("name", ""))),
        "created": str(result.get("metadata_created", result.get("created", ""))),
        "modified": str(result.get("metadata_modified", result.get("modified", ""))),
        "publisher": "California Department of Social Services"
        if "California Department of Social Services" in text
        else "",
        "license_label": license_label,
        "related_urls": sorted(related_urls),
        "content_sha256": _artifact_digest(path),
    }


def urlsplit_path(url: str) -> str:
    from urllib.parse import urlsplit

    return urlsplit(url).path


def _artifact_digest(path: Path) -> str:
    from ccld_complaints.utils.hash import sha256_bytes

    return sha256_bytes(path.read_bytes())


def _capture_catalogs(fetcher: PublicFetcher) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for endpoint_id, url in CATALOG_ENDPOINTS:
        path = fetcher.capture(
            endpoint_id=endpoint_id,
            url=url,
            relative_path=Path("reference") / f"{endpoint_id}.html",
        )
        records.append(_catalog_record(endpoint_id, url, path))
    return records


def _query_url(parameters: Mapping[str, Any]) -> str:
    return f"{QUERY_URL}?{urlencode(parameters, doseq=True)}"


def _capture_arcgis_observation(
    fetcher: PublicFetcher, observation_id: str
) -> dict[str, Any]:
    root = Path(observation_id)
    service_path = fetcher.capture(
        endpoint_id=f"{observation_id}-service",
        url=f"{SERVICE_URL}?f=pjson",
        relative_path=root / "service.json",
    )
    layer_path = fetcher.capture(
        endpoint_id=f"{observation_id}-layer",
        url=f"{LAYER_URL}?f=pjson",
        relative_path=root / "layer.json",
    )
    service = _read_json(service_path)
    layer = _read_json(layer_path)
    layer_profile = profile_layer_metadata(layer)
    item_id = str(layer_profile["service_item_id"] or service.get("serviceItemId", ""))
    if item_id != ARCGIS_ITEM_ID:
        raise ValueError("ArcGIS service item identity does not match the approved item.")
    if layer_profile["layer_id"] != 0:
        raise ValueError("ArcGIS source did not identify approved layer 0.")
    object_id_field = str(layer_profile["object_id_field"])
    maximum_record_count = int(layer_profile["max_record_count"])
    if not object_id_field or maximum_record_count <= 0:
        raise ValueError("ArcGIS layer lacks bounded pagination metadata.")
    raw_fields = cast(list[dict[str, Any]], layer_profile["fields"])
    field_names = [str(field["name"]) for field in raw_fields]
    field_mapping = resolve_projection_fields(field_names)
    facility_id_field = field_mapping["facility_number"]
    if facility_id_field is None:
        raise ValueError("ArcGIS layer has no governed Facility ID field candidate.")

    ids_path = fetcher.capture(
        endpoint_id=f"{observation_id}-ids",
        url=_query_url({"where": "1=1", "returnIdsOnly": "true", "f": "json"}),
        relative_path=root / "query" / "ids.json",
    )
    ids_payload = _read_json(ids_path)
    raw_ids = ids_payload.get("objectIds")
    if not isinstance(raw_ids, list):
        raise ValueError("ArcGIS ID query did not return an objectIds array.")
    object_ids = sorted(raw_ids, key=lambda value: int(value))

    pages: list[dict[str, Any]] = []
    page_paths: list[Path] = []
    page_size = maximum_record_count
    maximum_pages = math.ceil(len(object_ids) / page_size) + 2
    offset = 0
    for page_index in range(maximum_pages):
        page_path = fetcher.capture(
            endpoint_id=f"{observation_id}-page-{page_index:04d}",
            url=_query_url(
                {
                    "where": "1=1",
                    "outFields": "*",
                    "returnGeometry": "false",
                    "orderByFields": object_id_field,
                    "resultOffset": offset,
                    "resultRecordCount": page_size,
                    "f": "json",
                }
            ),
            relative_path=root / "query" / f"page-{page_index:04d}.json",
        )
        payload = _read_json(page_path)
        page_rows = rows_from_arcgis_response(payload)
        pages.append(payload)
        page_paths.append(page_path)
        if not page_rows:
            break
        offset += len(page_rows)
    else:
        raise ValueError("ArcGIS pagination exceeded its deterministic page bound.")

    pagination = analyze_complete_pagination(
        pages,
        object_id_field=object_id_field,
        facility_id_field=facility_id_field,
        expected_object_ids=object_ids,
        maximum_record_count=maximum_record_count,
    )
    if pagination["status"] != "pass":
        raise ValueError("ArcGIS pagination did not prove complete bounded retrieval.")
    query_rows = [row for page in pages for row in rows_from_arcgis_response(page)]

    export_path = fetcher.capture(
        endpoint_id=f"{observation_id}-export",
        url=EXPORT_URL,
        relative_path=root / "export" / "facility-reference-export.bin",
    )
    export_fields, export_rows, export_metadata = parse_export_bytes(export_path.read_bytes())
    export_mapping = resolve_projection_fields(export_fields)
    equivalence = compare_export_query(
        query_rows,
        export_rows,
        query_mapping=field_mapping,
        export_mapping=export_mapping,
    )
    projected_rows = project_rows(query_rows, field_mapping)
    raw_sha = canonical_fingerprint(
        [
            _artifact_for(fetcher, f"{observation_id}-layer").sha256,
            _artifact_for(fetcher, f"{observation_id}-ids").sha256,
            *[
                _artifact_for(fetcher, f"{observation_id}-page-{index:04d}").sha256
                for index in range(len(page_paths))
            ],
            _artifact_for(fetcher, f"{observation_id}-export").sha256,
        ]
    )
    return {
        "observation_id": observation_id,
        "service": service,
        "layer": layer,
        "layer_profile": layer_profile,
        "field_mapping": field_mapping,
        "object_ids": object_ids,
        "query_rows": query_rows,
        "projected_rows": projected_rows,
        "pagination": pagination,
        "export_fields": export_fields,
        "export_rows": export_rows,
        "export_metadata": export_metadata,
        "export_mapping": export_mapping,
        "equivalence": equivalence,
        "raw_sha256": raw_sha,
    }


def _capture_program_sources(
    fetcher: PublicFetcher,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    combined: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    page_size = 10_000
    for resource_id in PROGRAM_RESOURCE_IDS:
        rows: list[dict[str, Any]] = []
        page_counts: list[int] = []
        offset = 0
        total_reported: int | None = None
        for page_index in range(20):
            url = (
                "https://data.ca.gov/api/action/datastore_search?"
                + urlencode(
                    {
                        "resource_id": resource_id,
                        "limit": page_size,
                        "offset": offset,
                        "sort": "_id asc",
                    }
                )
            )
            page_path = fetcher.capture(
                endpoint_id=f"program-{resource_id}-page-{page_index:02d}",
                url=url,
                relative_path=Path("program-sources")
                / resource_id
                / f"page-{page_index:02d}.json",
            )
            payload = _read_json(page_path)
            result = payload.get("result")
            if not isinstance(result, Mapping) or not isinstance(result.get("records"), list):
                raise ValueError(f"Program datastore response is malformed: {resource_id}")
            total = result.get("total")
            if isinstance(total, int):
                total_reported = total
            page_rows = [
                dict(row) for row in cast(list[Any], result["records"]) if isinstance(row, Mapping)
            ]
            page_counts.append(len(page_rows))
            rows.extend(page_rows)
            if not page_rows:
                break
            offset += len(page_rows)
        else:
            raise ValueError(f"Program datastore pagination exceeded bound: {resource_id}")
        identifiers = [normalize_scalar(row.get("facility_number")) for row in rows]
        counts = Counter(value for value in identifiers if value)
        summaries.append(
            {
                "resource_id": resource_id,
                "source_name": PROGRAM_SOURCE_NAMES[resource_id],
                "row_count": len(rows),
                "reported_total": total_reported,
                "page_counts": page_counts,
                "terminal_page_observed": bool(page_counts) and page_counts[-1] == 0,
                "unique_facility_id_count": len(counts),
                "missing_facility_id_row_count": sum(not value for value in identifiers),
                "duplicate_facility_ids": sorted(
                    value for value, count in counts.items() if count > 1
                ),
                "status": (
                    "pass"
                    if total_reported == len(rows)
                    and bool(page_counts)
                    and page_counts[-1] == 0
                    else "fail"
                ),
            }
        )
        combined.extend(rows)
    return combined, summaries


def _source_identity(catalog_records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    arcgis_records = [
        record
        for record in catalog_records
        if record.get("endpoint_id") in {"lab-arcgis-1", "lab-arcgis-2", "lab-arcgis-3"}
    ]
    linked = [
        str(record.get("endpoint_id"))
        for record in arcgis_records
        if any(
            ARCGIS_ITEM_ID in str(url)
            for url in cast(list[Any], record.get("related_urls", []))
        )
    ]
    relationship_sets = {
        tuple(
            sorted(
                str(url)
                for url in cast(list[Any], record.get("related_urls", []))
                if ARCGIS_ITEM_ID in str(url) or LAYER_URL in str(url)
            )
        )
        for record in arcgis_records
    }
    duplicate_catalog_records = (
        len(arcgis_records) == 3
        and len(linked) == len(arcgis_records)
        and len(relationship_sets) == 1
    )
    return {
        "publisher": "California Department of Social Services",
        "program": "Community Care Licensing Division",
        "arcgis_item_id": ARCGIS_ITEM_ID,
        "service_url": SERVICE_URL,
        "service_name": "CDSS_CCL_Facilities",
        "layer_id": 0,
        "layer_url": LAYER_URL,
        "export_url": EXPORT_URL,
        "catalog_records_linking_item": sorted(linked),
        "catalog_succession_status": (
            "duplicate_records_same_arcgis_item"
            if duplicate_catalog_records
            else "unresolved_same_title_records"
        ),
        "catalog_relationship_conclusion": (
            "Three same-titled catalog records independently link the same item, layer, "
            "and export identities; they are duplicate catalog representations of one "
            "ArcGIS source candidate, not three distinct service candidates."
            if duplicate_catalog_records
            else "Same-titled catalog candidate relationships remain unresolved."
        ),
        "candidate_specific_system_of_record_status": "unconfirmed",
        "candidate_specific_maintainer_status": "unconfirmed",
    }


def _terms_summary(catalog_records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    labels = sorted(
        {
            str(record.get("license_label"))
            for record in catalog_records
            if record.get("license_label")
        }
    )
    return {
        "observed_license_labels": labels,
        "current_arcgis_catalog_label": "Creative Commons Attribution"
        if "Creative Commons Attribution" in labels
        else "unavailable",
        "legacy_program_catalog_label": "No License Provided"
        if "No License Provided" in labels
        else "unavailable",
        "license_version": "unconfirmed",
        "publisher_approved_attribution_text": "unconfirmed",
        "human_or_legal_confirmation_required": True,
        "minimum_conditional_attribution": [
            "California Department of Social Services",
            "Community Care Licensing Facilities",
            "exact catalog, item, service, layer, and snapshot identity",
            "access and source-version dates",
            "exact approved license version and link",
            "transformation notice",
        ],
    }


def _field_population(rows: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    return [
        {
            "field": field,
            "populated_count": sum(bool(row.get(field)) for row in rows),
            "missing_count": sum(not bool(row.get(field)) for row in rows),
        }
        for field in FIELD_CANDIDATES
    ]


def _build_payloads(
    *,
    observed_at: str,
    catalog_records: list[dict[str, Any]],
    fetcher: PublicFetcher,
    previous: Mapping[str, Any],
    current: Mapping[str, Any],
    program_rows: list[dict[str, Any]],
    program_summaries: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    source_identity = _source_identity(catalog_records)
    current_rows = cast(list[dict[str, Any]], current["query_rows"])
    current_projected = cast(list[dict[str, str]], current["projected_rows"])
    previous_projected = cast(list[dict[str, str]], previous["projected_rows"])
    layer_profile = cast(dict[str, Any], current["layer_profile"])
    field_mapping = cast(dict[str, str | None], current["field_mapping"])
    program_fields = list(program_rows[0]) if program_rows else []
    program_mapping = resolve_projection_fields(program_fields)
    program_comparison = compare_program_sources(
        current_rows,
        program_rows,
        arcgis_mapping=field_mapping,
        program_mapping=program_mapping,
    )
    content_comparison = compare_observations(
        previous_projected,
        current_projected,
        fields=tuple(FIELD_CANDIDATES),
        previous_raw_sha256=str(previous["raw_sha256"]),
        current_raw_sha256=str(current["raw_sha256"]),
        previous_schema_fingerprint=str(
            cast(Mapping[str, Any], previous["layer_profile"])["schema_fingerprint"]
        ),
        current_schema_fingerprint=str(layer_profile["schema_fingerprint"]),
        previous_domain_fingerprint=str(
            cast(Mapping[str, Any], previous["layer_profile"])["domain_fingerprint"]
        ),
        current_domain_fingerprint=str(layer_profile["domain_fingerprint"]),
    )
    duplicate_analysis = classify_duplicate_facility_groups(
        current_rows,
        facility_id_field=str(field_mapping["facility_number"]),
        object_id_field=str(layer_profile["object_id_field"]),
    )
    code_733 = investigate_code_733(
        current_rows,
        cast(list[dict[str, Any]], layer_profile["fields"]),
        additional_sources={"retained-program-datastores": program_rows},
    )
    terms = _terms_summary(catalog_records)
    program_count = int(program_comparison["program_unique_facility_id_count"])
    shared_count = int(program_comparison["shared_facility_id_count"])
    coverage_ratio = shared_count / program_count if program_count else 0.0
    pagination_pass = cast(Mapping[str, Any], current["pagination"])["status"] == "pass"
    equivalence_pass = cast(Mapping[str, Any], current["equivalence"])["status"] == "pass"
    pagination_findings = cast(Mapping[str, Any], current["pagination"])
    facility_id_integrity = pagination_findings["facility_id_status"] == "pass"
    integrity_failure = bool(pagination_findings["missing_facility_id_row_count"])
    gates = {
        "source_access": True,
        "source_identity": (
            source_identity["catalog_succession_status"]
            in {"resolved", "duplicate_records_same_arcgis_item"}
            and source_identity["arcgis_item_id"] == ARCGIS_ITEM_ID
        ),
        "complete_pagination": pagination_pass,
        "export_query_equivalence": equivalence_pass,
        "schema_and_domain_stability": (
            not bool(content_comparison["schema_changed"])
            and not bool(content_comparison["domain_changed"])
        ),
        "facility_id_integrity": facility_id_integrity,
        "facility_id_coverage_fit": coverage_ratio >= 0.99,
        "authority_confirmed": False,
        "terms_confirmed": False,
        "terms_prohibit_use": False,
        "critical_integrity_failure": integrity_failure,
        "rollback_suitable": True,
    }
    recommendation = choose_recommendation(gates)
    artifacts = [artifact.as_dict() for artifact in fetcher.artifacts]
    endpoint_inventory = [
        {
            "endpoint_id": artifact.endpoint_id,
            "url": sanitize_url(artifact.request_url),
            "status": artifact.status,
            "media_type": artifact.media_type,
        }
        for artifact in fetcher.artifacts
    ]
    source_inventory = output_envelope(
        "source-inventory",
        {
            "catalog_records": catalog_records,
            "source_identity": source_identity,
            "endpoint_inventory": endpoint_inventory,
            "redirect_outcomes": fetcher.redirect_outcomes,
            "terms_authority_attribution": terms,
        },
        observed_at=observed_at,
        status="warning",
        warnings=(
            (
                "Duplicate catalog records resolve to one ArcGIS item, but "
                "candidate-specific authority remains unconfirmed."
            ),
            "License version and publisher-approved attribution text require confirmation.",
        ),
    )
    snapshot_manifest = output_envelope(
        "snapshot-manifest",
        {
            "artifacts": artifacts,
            "retention_boundary": "ignored immutable source-profiling evidence",
        },
        observed_at=observed_at,
    )
    schema_profile = output_envelope(
        "schema-profile",
        {
            "layer": layer_profile,
            "field_mapping": field_mapping,
            "field_population": _field_population(current_projected),
            "code_733": code_733,
        },
        observed_at=observed_at,
        status="warning" if code_733["status"] == "unresolved" else "pass",
        warnings=("Raw value 733 has no verified descriptive mapping.",)
        if code_733["status"] == "unresolved"
        else (),
    )
    pagination_profile = output_envelope(
        "pagination-profile",
        {
            "pagination": current["pagination"],
            "duplicate_facility_group_analysis": duplicate_analysis,
            "object_id_batch_equivalence": {
                "status": "pass",
                "method": "returnIdsOnly set reconciled to ordered offset pagination",
                "expected_object_id_count": len(cast(list[Any], current["object_ids"])),
                "observed_object_id_count": cast(Mapping[str, Any], current["pagination"])[
                    "unique_object_id_count"
                ],
            },
        },
        observed_at=observed_at,
        status=(
            "fail"
            if not pagination_pass
            else "pass"
            if facility_id_integrity
            else "warning"
        ),
        warnings=(
            (
                "Complete object-ID retrieval passed, but duplicate or missing "
                "Facility IDs require a separate identity decision."
            ),
        )
        if pagination_pass and not facility_id_integrity
        else (),
    )
    export_equivalence = output_envelope(
        "export-query-equivalence",
        {
            "equivalence": current["equivalence"],
            "export_container": current["export_metadata"],
            "byte_comparison": (
                "Raw bytes are format-specific and are reported separately from semantic equality."
            ),
        },
        observed_at=observed_at,
        status="pass" if equivalence_pass else "fail",
    )
    program_output = output_envelope(
        "program-comparison",
        {
            "comparison": {
                **program_comparison,
                "shared_program_coverage_ratio": coverage_ratio,
            },
            "program_sources": program_summaries,
        },
        observed_at=observed_at,
        status="pass" if all(item["status"] == "pass" for item in program_summaries) else "fail",
    )
    content_change = output_envelope(
        "content-change",
        {
            "observations": [
                {
                    "observation_id": previous["observation_id"],
                    "combined_raw_sha256": previous["raw_sha256"],
                },
                {
                    "observation_id": current["observation_id"],
                    "combined_raw_sha256": current["raw_sha256"],
                },
            ],
            "comparison": content_comparison,
        },
        observed_at=observed_at,
    )
    decision = decision_payload(
        recommendation=recommendation,
        source_identity=source_identity,
        gates={
            **gates,
            "program_shared_coverage_ratio": coverage_ratio,
            "terms_authority_attribution": terms,
        },
        observed_at=observed_at,
    )
    checks = [
        {"check": "source_access", "status": "pass"},
        {"check": "complete_pagination", "status": "pass" if pagination_pass else "fail"},
        {
            "check": "facility_id_integrity",
            "status": "pass" if facility_id_integrity else "warning",
        },
        {
            "check": "export_query_equivalence",
            "status": "pass" if equivalence_pass else "fail",
        },
        {
            "check": "program_pagination",
            "status": (
                "pass"
                if all(item["status"] == "pass" for item in program_summaries)
                else "fail"
            ),
        },
        {
            "check": "schema_stability",
            "status": "pass" if not content_comparison["schema_changed"] else "fail",
        },
        {
            "check": "domain_stability",
            "status": "pass" if not content_comparison["domain_changed"] else "fail",
        },
        {
            "check": "code_733_mapping",
            "status": "warning" if code_733["status"] == "unresolved" else "pass",
        },
        {"check": "authority_confirmation", "status": "blocked"},
        {"check": "license_version_confirmation", "status": "blocked"},
    ]
    validation_summary = output_envelope(
        "validation-summary",
        {
            "checks": checks,
            "generated_outputs": sorted(f"{name}.json" for name in OUTPUT_TYPES),
            "privacy_scan": "pass",
            "recommendation": recommendation,
        },
        observed_at=observed_at,
        status="warning",
        warnings=(
            "Authority and exact license/attribution confirmation remain downstream gates.",
        ),
    )
    return {
        "source-inventory.json": source_inventory,
        "snapshot-manifest.json": snapshot_manifest,
        "schema-profile.json": schema_profile,
        "pagination-profile.json": pagination_profile,
        "export-query-equivalence.json": export_equivalence,
        "program-comparison.json": program_output,
        "content-change.json": content_change,
        "decision.json": decision,
        "validation-summary.json": validation_summary,
    }


def _fixture_payloads(fixture_dir: Path, observed_at: str) -> dict[str, dict[str, Any]]:
    service = _read_json(fixture_dir / "service.json")
    layer = _read_json(fixture_dir / "layer.json")
    ids = _read_json(fixture_dir / "ids.json")
    pages = [
        _read_json(fixture_dir / "page-0.json"),
        _read_json(fixture_dir / "page-1.json"),
        _read_json(fixture_dir / "page-terminal.json"),
    ]
    rows = [row for page in pages for row in rows_from_arcgis_response(page)]
    profile = profile_layer_metadata(layer)
    mapping = resolve_projection_fields(list(rows[0]))
    export_fields, export_rows, export_metadata = parse_export_bytes(
        (fixture_dir / "export.csv").read_bytes()
    )
    equivalence = compare_export_query(
        rows,
        export_rows,
        query_mapping=mapping,
        export_mapping=resolve_projection_fields(export_fields),
    )
    pagination = analyze_complete_pagination(
        pages,
        object_id_field="OBJECTID",
        facility_id_field="FAC_NBR",
        expected_object_ids=cast(list[Any], ids["objectIds"]),
        maximum_record_count=2,
    )
    program_fields, program_rows, _program_metadata = parse_export_bytes(
        (fixture_dir / "program-source.csv").read_bytes()
    )
    comparison = compare_program_sources(
        rows,
        program_rows,
        arcgis_mapping=mapping,
        program_mapping=resolve_projection_fields(program_fields),
    )
    code_733 = investigate_code_733(rows, cast(list[dict[str, Any]], profile["fields"]))
    source_identity = {
        "publisher": "California Department of Social Services",
        "arcgis_item_id": ARCGIS_ITEM_ID,
        "service_name": service["name"],
        "layer_id": 0,
        "catalog_succession_status": "unresolved_same_title_records",
    }
    gates = {
        "source_access": True,
        "complete_pagination": True,
        "source_identity": False,
        "export_query_equivalence": True,
        "schema_and_domain_stability": True,
        "facility_id_coverage_fit": False,
        "authority_confirmed": False,
        "terms_confirmed": False,
        "rollback_suitable": True,
    }
    projected = project_rows(rows, mapping)
    content = compare_observations(
        projected,
        projected,
        fields=tuple(FIELD_CANDIDATES),
        previous_raw_sha256="fixture",
        current_raw_sha256="fixture",
        previous_schema_fingerprint=str(profile["schema_fingerprint"]),
        current_schema_fingerprint=str(profile["schema_fingerprint"]),
        previous_domain_fingerprint=str(profile["domain_fingerprint"]),
        current_domain_fingerprint=str(profile["domain_fingerprint"]),
    )
    return {
        "source-inventory.json": output_envelope(
            "source-inventory",
            {
                "catalog_records": [],
                "source_identity": source_identity,
                "endpoint_inventory": [],
                "redirect_outcomes": [],
            },
            observed_at=observed_at,
        ),
        "snapshot-manifest.json": output_envelope(
            "snapshot-manifest",
            {"artifacts": [], "retention_boundary": "synthetic fixtures"},
            observed_at=observed_at,
        ),
        "schema-profile.json": output_envelope(
            "schema-profile",
            {"layer": profile, "field_mapping": mapping, "code_733": code_733},
            observed_at=observed_at,
            status="warning",
        ),
        "pagination-profile.json": output_envelope(
            "pagination-profile",
            {"pagination": pagination, "object_id_batch_equivalence": {"status": "pass"}},
            observed_at=observed_at,
        ),
        "export-query-equivalence.json": output_envelope(
            "export-query-equivalence",
            {"equivalence": equivalence, "export_container": export_metadata},
            observed_at=observed_at,
        ),
        "program-comparison.json": output_envelope(
            "program-comparison",
            {"comparison": comparison, "program_sources": ["synthetic"]},
            observed_at=observed_at,
        ),
        "content-change.json": output_envelope(
            "content-change",
            {"observations": ["fixture-a", "fixture-b"], "comparison": content},
            observed_at=observed_at,
        ),
        "decision.json": decision_payload(
            recommendation=choose_recommendation(gates),
            source_identity=source_identity,
            gates=gates,
            observed_at=observed_at,
        ),
        "validation-summary.json": output_envelope(
            "validation-summary",
            {"checks": [], "generated_outputs": [], "privacy_scan": "pass"},
            observed_at=observed_at,
        ),
    }


def main() -> int:
    args = _parser().parse_args()
    observed_at = args.observed_at or _utc_now()
    if args.mode == "fixture" and args.observed_at is None:
        raise SystemExit("Fixture mode requires --observed-at for deterministic output.")
    schema = load_schema(args.schema)
    if args.mode == "fixture":
        payloads = _fixture_payloads(args.fixture_dir, observed_at)
        deliverables = write_output_package(args.output_dir, payloads, schema)
        print(json.dumps({"deliverables": deliverables, "mode": "fixture"}, sort_keys=True))
        return 0

    retrieval_root = args.raw_root / _stamp(observed_at)
    fetcher = PublicFetcher(retrieval_root, observed_at, args.timeout_seconds)
    catalog_records = _capture_catalogs(fetcher)
    previous = _capture_arcgis_observation(fetcher, "observation-01")
    current = _capture_arcgis_observation(fetcher, "observation-02")
    program_rows, program_summaries = _capture_program_sources(fetcher)
    payloads = _build_payloads(
        observed_at=observed_at,
        catalog_records=catalog_records,
        fetcher=fetcher,
        previous=previous,
        current=current,
        program_rows=program_rows,
        program_summaries=program_summaries,
    )
    deliverables = write_output_package(args.output_dir, payloads, schema)
    decision = cast(Mapping[str, Any], payloads["decision.json"]["data"])
    print(
        json.dumps(
            {
                "artifact_count": len(fetcher.artifacts),
                "deliverables": deliverables,
                "mode": "live",
                "recommendation": decision["recommendation"],
                "raw_evidence_root": retrieval_root.as_posix(),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
