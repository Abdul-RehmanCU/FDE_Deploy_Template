import json
import logging
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from time import monotonic

from fastapi import FastAPI, Request, Response
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span
from prometheus_client import Counter, Histogram

from app.core.config import settings
from app.core.db import engine

_tracer_provider_configured = False
_common_instrumentation_configured = False

HTTP_REQUESTS = Counter(
    "http_server_requests_total",
    "HTTP requests completed by method, route, and response status",
    ("http_request_method", "http_route", "http_response_status_code"),
)
HTTP_DURATION = Histogram(
    "http_server_request_duration_seconds",
    "HTTP request duration by method, route, and response status",
    ("http_request_method", "http_route", "http_response_status_code"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)

_BEARER = re.compile(r"(?i)bearer\s+[^\s,;]+")
_URL_CREDENTIALS = re.compile(r"://([^:/@\s]+):([^@/\s]+)@")
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_SECRET_QUERY = re.compile(r"(?i)([?&](?:token|password|secret|key)=)[^&\s]+")


def redact_log_message(value: str) -> str:
    value = _BEARER.sub("Bearer [REDACTED]", value)
    value = _URL_CREDENTIALS.sub(r"://\1:[REDACTED]@", value)
    value = _SECRET_QUERY.sub(r"\1[REDACTED]", value)
    return _EMAIL.sub("[REDACTED_EMAIL]", value)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_log_message(record.getMessage()),
        }
        span = trace.get_current_span().get_span_context()
        if span.is_valid:
            payload["trace_id"] = f"{span.trace_id:032x}"
            payload["span_id"] = f"{span.span_id:016x}"
        for key in (
            "event",
            "http_request_method",
            "http_route",
            "http_response_status_code",
            "duration_ms",
            "task_kind",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, separators=(",", ":"))


class AccessLogPrivacyFilter(logging.Filter):
    """Strip query strings because contact search terms may contain PII."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple) and len(record.args) >= 3:
            values = list(record.args)
            values[2] = str(values[2]).split("?", 1)[0]
            record.args = tuple(values)
        return True


def redact_request_trace(span: Span, scope: dict[str, object]) -> None:
    if not span.is_recording():
        return
    path = str(scope.get("path", ""))
    span.set_attribute("url.query", "")
    span.set_attribute("url.full", path)
    span.set_attribute("http.target", path)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "celery", "celery.task"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True
    logging.getLogger("uvicorn.access").addFilter(AccessLogPrivacyFilter())


async def observe_http_request(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    if request.url.path == "/internal/metrics":
        return await call_next(request)
    started = monotonic()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            response.headers["X-Trace-Id"] = f"{span_context.trace_id:032x}"
        return response
    finally:
        route = request.scope.get("route")
        route_path = getattr(route, "path", "unmatched")
        labels = {
            "http_request_method": request.method,
            "http_route": route_path,
            "http_response_status_code": str(status_code),
        }
        duration = monotonic() - started
        HTTP_REQUESTS.labels(**labels).inc()
        HTTP_DURATION.labels(**labels).observe(duration)
        logging.getLogger("app.http").info(
            "http_request",
            extra={
                "event": "http_request",
                **labels,
                "duration_ms": round(duration * 1000, 3),
            },
        )


def build_tracer_provider(endpoint: str, service_name: str) -> TracerProvider:
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": service_name,
                "service.version": settings.APP_VERSION,
                "deployment.environment.name": settings.APP_ENVIRONMENT,
            }
        )
    )
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    return provider


def configure_tracer_provider() -> TracerProvider | None:
    global _tracer_provider_configured
    endpoint = settings.OTEL_EXPORTER_OTLP_ENDPOINT
    if not endpoint or _tracer_provider_configured:
        return None
    provider = build_tracer_provider(endpoint, settings.OTEL_SERVICE_NAME)
    trace.set_tracer_provider(provider)
    _tracer_provider_configured = True
    return provider


def configure_common_instrumentation() -> None:
    global _common_instrumentation_configured
    if _common_instrumentation_configured:
        return
    SQLAlchemyInstrumentor().instrument(engine=engine)
    RedisInstrumentor().instrument()
    _common_instrumentation_configured = True


def configure_tracing(app: FastAPI) -> None:
    configure_tracer_provider()
    configure_common_instrumentation()
    FastAPIInstrumentor.instrument_app(app, server_request_hook=redact_request_trace)
