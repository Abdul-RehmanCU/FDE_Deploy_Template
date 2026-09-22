import json
import logging
from unittest.mock import Mock

from fastapi.testclient import TestClient
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags, use_span
from prometheus_client import generate_latest

from app.core import observability
from app.core.observability import (
    AccessLogPrivacyFilter,
    JsonFormatter,
    redact_request_trace,
)
from app.main import app


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


def test_http_metrics_use_bounded_route_labels() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health/live?email=person@example.com")
    assert response.status_code == 200
    metrics = generate_latest().decode()
    assert 'http_route="/health/live"' in metrics
    assert 'http_request_method="GET"' in metrics
    assert 'http_response_status_code="200"' in metrics
    assert "person@example.com" not in metrics
    assert "http_server_request_duration_seconds_count" in metrics
    assert "http_server_requests_total" in metrics


def test_json_formatter_redacts_secrets_and_includes_active_trace() -> None:
    span = NonRecordingSpan(
        SpanContext(
            trace_id=int("4bf92f3577b34da6a3ce929d0e0e4736", 16),
            span_id=int("00f067aa0ba902b7", 16),
            is_remote=False,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )
    )
    record = logging.LogRecord(
        "app.worker",
        logging.INFO,
        __file__,
        1,
        "Bearer top-secret person@example.com postgresql://app:password@database/app",
        (),
        None,
    )
    with use_span(span):
        payload = json.loads(JsonFormatter().format(record))
    assert payload["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert "top-secret" not in payload["message"]
    assert "person@example.com" not in payload["message"]
    assert "password@" not in payload["message"]
