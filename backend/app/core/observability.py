import json
import logging
from datetime import UTC, datetime

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span

from app.core.config import settings
from app.core.db import engine


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        span = trace.get_current_span().get_span_context()
        if span.is_valid:
            payload["trace_id"] = f"{span.trace_id:032x}"
            payload["span_id"] = f"{span.span_id:016x}"
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
    logging.getLogger("uvicorn.access").addFilter(AccessLogPrivacyFilter())


def configure_tracing(app: FastAPI) -> None:
    if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        provider = TracerProvider(
            resource=Resource.create(
                {
                    "service.name": settings.OTEL_SERVICE_NAME,
                    "service.version": settings.APP_VERSION,
                    "deployment.environment.name": settings.APP_ENVIRONMENT,
                }
            )
        )
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
            )
        )
        trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, server_request_hook=redact_request_trace)
    SQLAlchemyInstrumentor().instrument(engine=engine)
    RedisInstrumentor().instrument()
