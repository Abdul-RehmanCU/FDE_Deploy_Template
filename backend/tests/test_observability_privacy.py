import logging
from unittest.mock import Mock

from app.core import observability
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


def test_worker_path_installs_configured_provider_without_exporting(
    monkeypatch,
) -> None:
    provider = Mock()
    build = Mock(return_value=provider)
    install = Mock()
    monkeypatch.setattr(
        observability.settings, "OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317"
    )
    monkeypatch.setattr(observability.settings, "OTEL_SERVICE_NAME", "fde-worker")
    monkeypatch.setattr(observability, "build_tracer_provider", build)
    monkeypatch.setattr(observability.trace, "set_tracer_provider", install)
    monkeypatch.setattr(observability, "_tracer_provider_configured", False)

    assert observability.configure_tracer_provider() is provider
    build.assert_called_once_with("http://collector:4317", "fde-worker")
    install.assert_called_once_with(provider)


def test_provider_builds_otlp_batch_exporter_with_service_name(monkeypatch) -> None:
    exporter = Mock()
    processor = Mock()
    exporter_factory = Mock(return_value=exporter)
    processor_factory = Mock(return_value=processor)
    monkeypatch.setattr(observability, "OTLPSpanExporter", exporter_factory)
    monkeypatch.setattr(observability, "BatchSpanProcessor", processor_factory)

    provider = observability.build_tracer_provider(
        "http://collector:4317", "fde-worker"
    )

    exporter_factory.assert_called_once_with(endpoint="http://collector:4317")
    processor_factory.assert_called_once_with(exporter)
    assert provider.resource.attributes["service.name"] == "fde-worker"
