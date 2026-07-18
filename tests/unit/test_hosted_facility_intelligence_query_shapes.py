from __future__ import annotations

import re
from typing import Any, cast

from sqlalchemy import create_mock_engine, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection

from ccld_complaints.hosted_app import source_derived_reads as reads


class _EmptyResult:
    def first(self) -> None:
        return None

    def scalars(self) -> _EmptyResult:
        return self

    def __iter__(self) -> Any:
        return iter(())


def test_postgresql_filter_option_queries_compile_with_grouped_ordering() -> None:
    captured: list[Any] = []

    def capture(statement: Any, *_args: Any, **_kwargs: Any) -> _EmptyResult:
        captured.append(statement)
        return _EmptyResult()

    connection = cast(
        Connection,
        create_mock_engine("postgresql+psycopg://", capture),
    )

    reads._facility_intelligence_filter_options(
        connection,
        import_batch_id="normal-ci-postgres-compilation",
        import_batch_ids=None,
        import_batch_query=None,
    )

    compiled = [_postgresql_sql(statement) for statement in captured]
    grouped_ordered = [
        statement
        for statement in compiled
        if " group by " in statement and " order by lower(" in statement
    ]
    assert len(grouped_ordered) == 3
    assert any("facility_type" in statement for statement in grouped_ordered)
    assert any("county" in statement for statement in grouped_ordered)
    assert any("finding" in statement for statement in grouped_ordered)
    assert not any(
        re.search(r"select distinct\b.*\border by lower\(", statement)
        for statement in compiled
    )


def test_postgresql_count_hydration_page_and_review_queries_are_bounded() -> None:
    connection = cast(
        Connection,
        create_mock_engine("postgresql+psycopg://", lambda *_args, **_kwargs: None),
    )
    filters = reads.FacilityIntelligenceReadFilters(sort="facility_name")
    count_facts = reads._facility_intelligence_complaint_facts(
        connection,
        filters=filters,
        import_batch_id="normal-ci-postgres-compilation",
        import_batch_ids=None,
        import_batch_query=None,
        apply_active_filters=True,
        cte_name="normal_ci_count_facts",
        include_priority_signals=False,
        projection="count",
    )
    count_sql = _postgresql_sql(select(count_facts))
    assert "normal_ci_count_facts_substantiated_matches" not in count_sql
    assert "strongest_delay_days" not in count_sql
    assert "source_available" in count_sql

    hydration_facts = reads._facility_intelligence_complaint_facts(
        connection,
        filters=filters,
        import_batch_id="normal-ci-postgres-compilation",
        import_batch_ids=None,
        import_batch_query=None,
        apply_active_filters=True,
        cte_name="normal_ci_hydration_references",
        include_priority_signals=False,
        projection="hydration",
        source_facility_ids=("ccld:facility:100001",),
        source_record_keys=("complaint:ccld:complaint:MISSING-1",),
    )
    hydration_sql = _postgresql_sql(select(hydration_facts))
    assert "normal_ci_hydration_references_substantiated_matches" not in hydration_sql
    assert "facility_id in ('ccld:facility:100001')" in hydration_sql
    assert "source_record_key in ('complaint:ccld:complaint:missing-1')" in hydration_sql

    full_facts = reads._facility_intelligence_complaint_facts(
        connection,
        filters=filters,
        import_batch_id="normal-ci-postgres-compilation",
        import_batch_ids=None,
        import_batch_query=None,
        apply_active_filters=True,
    )
    facilities = reads._facility_intelligence_facilities(full_facts, filters=filters)
    order_columns, descending = reads._facility_intelligence_order_spec(
        facilities,
        filters.sort,
    )
    order_clauses = reads._facility_intelligence_order_clauses(
        order_columns,
        descending,
    )
    page_statement = reads._facility_intelligence_bounded_limit(
        select(facilities).order_by(*order_clauses),
        reads.FACILITY_INTELLIGENCE_PAGE_SIZE,
        dialect_name="postgresql",
    )
    page_sql = _postgresql_sql(page_statement)
    assert " limit 25" in page_sql
    assert " offset " not in f" {page_sql} "

    review_next_statement = reads._facility_intelligence_bounded_limit(
        select(facilities.c.facility_identity).order_by(*order_clauses),
        1,
        dialect_name="postgresql",
    )
    review_next_sql = _postgresql_sql(review_next_statement)
    assert "select facility_intelligence_facilities.facility_identity" in review_next_sql
    assert " limit 1" in review_next_sql
    assert review_next_statement is not page_statement


def _postgresql_sql(statement: Any) -> str:
    return " ".join(
        str(
            statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        .casefold()
        .split()
    )
