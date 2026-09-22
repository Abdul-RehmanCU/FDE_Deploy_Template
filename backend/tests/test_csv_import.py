from app.models import RowOutcome
from app.services.csv_import import (
    CsvValidationError,
    build_report,
    inspect_csv,
    preview_csv,
    validate_mapping,
    validate_rows,
)

MAPPING = {
    "email": "Email",
    "first_name": "First",
    "last_name": "Last",
    "company": "Company",
    "country_code": "Country",
    "external_id": "External",
}


def test_bom_normalization_duplicates_and_existing_contacts() -> None:
    content = (
        "\ufeffEmail,First,Last,Company,Country,External\r\n"
        " A.User@example.com , Ada , User ,=1+1,ca,+10\r\n"
        "a.user@EXAMPLE.com,Second,Copy,,CA,11\r\n"
        "existing@example.com,Ex,Isting,,us,12\r\n"
        "bad-address,Bad,Email,,Canada,13\r\n"
    ).encode()
    inspection = inspect_csv(content, 10_000)
    rows = validate_rows(
        content,
        header=inspection.header,
        mapping=MAPPING,
        existing_emails={"existing@example.com"},
    )
    assert [row.outcome for row in rows] == [
        RowOutcome.ACCEPTED,
        RowOutcome.FILE_DUPLICATE,
        RowOutcome.EXISTING_CONTACT,
        RowOutcome.INVALID,
    ]
    assert rows[0].clean_data == {
        "email": "a.user@example.com",
        "first_name": "Ada",
        "last_name": "User",
        "company": "=1+1",
        "country_code": "CA",
        "external_id": "+10",
    }
    report = build_report([rows[0]]).decode("utf-8-sig")
    assert "'=1+1" in report
    assert "'+10" in report


def test_invalid_rows_do_not_reserve_email_for_deduplication() -> None:
    content = (
        b"Email,First,Last,Company,Country,External\n"
        b"same@example.com,,Missing,,,\n"
        b"same@example.com,Valid,Person,,,\n"
    )
    rows = validate_rows(
        content,
        header=inspect_csv(content, 10).header,
        mapping=MAPPING,
        existing_emails=set(),
    )
    assert rows[0].outcome == RowOutcome.INVALID
    assert rows[1].outcome == RowOutcome.ACCEPTED


def test_inspection_rejects_encoding_headers_shape_and_bound() -> None:
    cases = [
        (b"\xff\xfe", "invalid_encoding"),
        (b"A,A\n1,2\n", "duplicate_header"),
        (b"A,B\n1\n", "malformed_row"),
    ]
    for content, code in cases:
        try:
            inspect_csv(content, 10)
        except CsvValidationError as exc:
            assert exc.code == code
        else:
            raise AssertionError(f"Expected {code}")
    try:
        inspect_csv(b"A\n1\n2\n", 1)
    except CsvValidationError as exc:
        assert exc.code == "too_many_rows"
    else:
        raise AssertionError("Expected row limit failure")


def test_mapping_requires_unique_known_columns() -> None:
    assert validate_mapping(MAPPING, list(MAPPING.values()))["email"] == 0
    for mapping, code in [
        ({"email": "Email"}, "missing_mapping"),
        ({**MAPPING, "unknown": "Other"}, "unknown_field"),
        ({**MAPPING, "last_name": "First"}, "duplicate_mapping"),
    ]:
        try:
            validate_mapping(mapping, [*MAPPING.values(), "Other"])
        except CsvValidationError as exc:
            assert exc.code == code
        else:
            raise AssertionError(f"Expected {code}")


def test_oversized_field_returns_actionable_field_error() -> None:
    oversized = "x" * 256
    content = (
        "Email,First,Last,Company,Country,External\n"
        f"long@example.com,First,Last,{oversized},CA,E-1\n"
    ).encode()
    inspection = inspect_csv(content, 10)
    rows = validate_rows(
        content,
        header=inspection.header,
        mapping=MAPPING,
        existing_emails=set(),
    )
    assert rows[0].outcome == RowOutcome.INVALID
    assert rows[0].errors == [
        {"code": "too_long", "field": "company", "message": "Maximum length is 255"}
    ]


def test_preview_is_bounded() -> None:
    content = b"A,B\n1,2\n3,4\n5,6\n"
    header, rows, truncated = preview_csv(content, limit=2)
    assert header == ["A", "B"]
    assert rows == [["1", "2"], ["3", "4"]]
    assert truncated is True
