# Customer data contract

Only CSV is accepted. Spreadsheet files, archives, URLs, and remote fetches are
not part of the contract.

## Canonical fields

| Field | Required | Maximum | Normalization |
| --- | --- | ---: | --- |
| `email` | Yes | 320 | Trim, validate, and case-fold for matching |
| `first_name` | Yes | 120 | Trim surrounding whitespace |
| `last_name` | Yes | 120 | Trim surrounding whitespace |
| `company` | No | 255 | Trim; empty becomes null |
| `country_code` | No | 2 | Uppercase; exactly two ASCII letters |
| `external_id` | No | 255 | Trim; empty becomes null |

Mapping uses canonical field to exact uploaded header:

```json
{
  "mapping": {
    "email": "Email Address",
    "first_name": "First",
    "last_name": "Last",
    "company": "Organization",
    "country_code": "Country",
    "external_id": "Customer ID"
  }
}
```

Mapped headers must exist and each source header may be used once. Header
comparison for duplicate detection is case-insensitive.

## Classification

Invalid rows contain field-specific `{code, field, message}` entries. A valid
normalized email is reserved by its first valid occurrence in the file; later
occurrences are `file_duplicate`. A directory match is `existing_contact`.
Invalid rows do not reserve an email. Accepted validation rows are the only
candidates considered during confirmation, where the unique normalized-email
constraint is checked again.

Example synthetic input:

```csv
Email Address,First,Last,Organization,Country,Customer ID
amelie.tremblay@example.com,Amélie,Tremblay,Northstar Labs,ca,C-1001
duplicate@example.com,First,Copy,,US,C-1002
DUPLICATE@example.com,Second,Copy,,US,C-1003
```

Reports are UTF-8 with BOM. Any exported value beginning with `=`, `+`, `-`,
`@`, tab, or carriage return is prefixed with an apostrophe so opening the CSV
in spreadsheet software does not execute it as a formula.

PostgreSQL stores users, imports, row outcomes, contacts, jobs, attempts,
outbox entries, and audit events. UUID primary keys and UTC timestamps are used.
Foreign-key/list columns are indexed; normalized contact email is unique.
