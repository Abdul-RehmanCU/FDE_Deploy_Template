import csv
import io
import re
from collections.abc import Iterator
from dataclasses import dataclass

from email_validator import EmailNotValidError, validate_email

from app.models import RowOutcome

CANONICAL_FIELDS = (
    "email",
    "first_name",
    "last_name",
    "company",
    "country_code",
    "external_id",
)
REQUIRED_FIELDS = frozenset(("email", "first_name", "last_name"))
MAX_FIELD_LENGTHS = {
    "email": 320,
    "first_name": 120,
    "last_name": 120,
    "company": 255,
    "country_code": 2,
    "external_id": 255,
}
COUNTRY_CODE = re.compile(r"^[A-Z]{2}$")
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


class CsvValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class CsvInspection:
    header: list[str]
    total_rows: int


@dataclass(frozen=True)
class ValidatedRow:
    row_number: int
    outcome: RowOutcome
    normalized_email: str | None
    clean_data: dict[str, str | None] | None
    errors: list[dict[str, str]]


def _reader(content: bytes) -> Iterator[list[str]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvValidationError("invalid_encoding", "The file must be UTF-8 encoded") from exc
    if "\x00" in text:
        raise CsvValidationError("malformed_csv", "The CSV contains unsupported null bytes")
    return csv.reader(io.StringIO(text, newline=""), strict=True)


def inspect_csv(content: bytes, max_rows: int) -> CsvInspection:
    if not content:
        raise CsvValidationError("empty_file", "The CSV file is empty")
    try:
        reader = _reader(content)
        header = next(reader, None)
        if not header:
            raise CsvValidationError("missing_header", "The CSV must contain a header row")
        cleaned = [value.strip() for value in header]
        if any(not value for value in cleaned):
            raise CsvValidationError("empty_header", "CSV headers cannot be empty")
        folded = [value.casefold() for value in cleaned]
        if len(set(folded)) != len(folded):
            raise CsvValidationError("duplicate_header", "CSV headers must be unique")
        count = 0
        for row in reader:
            count += 1
            if count > max_rows:
                raise CsvValidationError(
                    "too_many_rows", f"CSV files may contain at most {max_rows} data rows"
                )
            if len(row) != len(cleaned):
                raise CsvValidationError(
                    "malformed_row", f"Row {count + 1} has the wrong number of columns"
                )
    except csv.Error as exc:
        raise CsvValidationError("malformed_csv", "The CSV structure is invalid") from exc
    return CsvInspection(header=cleaned, total_rows=count)


def validate_mapping(mapping: dict[str, str], header: list[str]) -> dict[str, int]:
    unknown = sorted(set(mapping) - set(CANONICAL_FIELDS))
    missing = sorted(REQUIRED_FIELDS - set(mapping))
    if unknown:
        raise CsvValidationError("unknown_field", f"Unknown mapped fields: {', '.join(unknown)}")
    if missing:
        raise CsvValidationError("missing_mapping", f"Required mappings are missing: {', '.join(missing)}")
    mapped_headers = list(mapping.values())
    if len(set(mapped_headers)) != len(mapped_headers):
        raise CsvValidationError("duplicate_mapping", "Each CSV column can be mapped only once")
    lookup = {value: index for index, value in enumerate(header)}
    absent = sorted(set(mapped_headers) - set(lookup))
    if absent:
        raise CsvValidationError("unknown_header", f"Mapped headers do not exist: {', '.join(absent)}")
    return {field: lookup[column] for field, column in mapping.items()}


def validate_rows(
    content: bytes,
    *,
    header: list[str],
    mapping: dict[str, str],
    existing_emails: set[str],
) -> list[ValidatedRow]:
    indexes = validate_mapping(mapping, header)
    reader = _reader(content)
    next(reader, None)
    seen: set[str] = set()
    results: list[ValidatedRow] = []
    for row_number, row in enumerate(reader, start=2):
        if len(row) != len(header):
            results.append(
                ValidatedRow(
                    row_number, RowOutcome.INVALID, None, None,
                    [{"code": "malformed_row", "field": "row", "message": "Wrong number of columns"}],
                )
            )
            continue
        clean = {
            field: (row[index].strip() or None) for field, index in indexes.items()
        }
        errors: list[dict[str, str]] = []
        for field in REQUIRED_FIELDS:
            if not clean.get(field):
                errors.append({"code": "required", "field": field, "message": "This field is required"})
        for field, value in clean.items():
            if value and len(value) > MAX_FIELD_LENGTHS[field]:
                errors.append({"code": "too_long", "field": field, "message": f"Maximum length is {MAX_FIELD_LENGTHS[field]}"})

        normalized_email: str | None = None
        email = clean.get("email")
        if email and len(email) <= MAX_FIELD_LENGTHS["email"]:
            try:
                normalized_email = validate_email(email, check_deliverability=False).normalized.casefold()
                clean["email"] = normalized_email
            except EmailNotValidError:
                errors.append({"code": "invalid_email", "field": "email", "message": "Enter a valid email address"})
        country = clean.get("country_code")
        if country:
            country = country.upper()
            clean["country_code"] = country
            if not COUNTRY_CODE.fullmatch(country):
                errors.append({"code": "invalid_country_code", "field": "country_code", "message": "Use a two-letter country code"})

        if errors:
            outcome = RowOutcome.INVALID
        elif normalized_email in seen:
            outcome = RowOutcome.FILE_DUPLICATE
        elif normalized_email in existing_emails:
            outcome = RowOutcome.EXISTING_CONTACT
        else:
            outcome = RowOutcome.ACCEPTED
            assert normalized_email
            seen.add(normalized_email)
        results.append(ValidatedRow(row_number, outcome, normalized_email, clean, errors))
    return results


def neutralize_formula(value: str | None) -> str:
    if value and value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value or ""


def build_report(rows: list[ValidatedRow]) -> bytes:
    output = io.StringIO(newline="")
    fieldnames = [*CANONICAL_FIELDS, "row_number", "outcome", "errors"]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\r\n")
    writer.writeheader()
    for result in rows:
        record = {field: neutralize_formula((result.clean_data or {}).get(field)) for field in CANONICAL_FIELDS}
        record.update(
            row_number=str(result.row_number),
            outcome=result.outcome.value,
            errors="; ".join(error["message"] for error in result.errors),
        )
        writer.writerow(record)
    return output.getvalue().encode("utf-8-sig")
