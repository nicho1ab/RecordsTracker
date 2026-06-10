from ccld_complaints.extraction.dates import days_between, parse_source_date


def test_parse_source_date() -> None:
    assert str(parse_source_date("04/07/2022")) == "2022-04-07"


def test_days_between() -> None:
    start = parse_source_date("04/07/2022")
    end = parse_source_date("08/24/2022")
    assert days_between(start, end) == 139
