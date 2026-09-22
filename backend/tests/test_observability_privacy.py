import logging
from unittest.mock import Mock

from app.core.observability import AccessLogPrivacyFilter, redact_request_trace


def test_access_log_filter_removes_query_string() -> None:
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        (
            "127.0.0.1:1",
            "GET",
            "/api/v1/contacts?q=person%40example.com",
            "1.1",
            200,
        ),
        None,
    )
    assert AccessLogPrivacyFilter().filter(record)
    assert "person" not in record.getMessage()
    assert record.getMessage().endswith('GET /api/v1/contacts HTTP/1.1" 200')


def test_trace_hook_overwrites_query_bearing_attributes() -> None:
    span = Mock()
    span.is_recording.return_value = True
    redact_request_trace(span, {"path": "/api/v1/contacts"})
    span.set_attribute.assert_any_call("url.query", "")
    span.set_attribute.assert_any_call("url.full", "/api/v1/contacts")
    span.set_attribute.assert_any_call("http.target", "/api/v1/contacts")
