import json
import logging
from datetime import UTC, datetime

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import Counter, Gauge, Histogram

from app.core.config import settings
from app.core.db import engine

IMPORT_ROWS = Counter(
    "fde_import_rows_total", "Rows processed by outcome", labelnames=("outcome",)
)
JOB_RUNS = Counter(
    "fde_job_runs_total", "Durable jobs by kind and outcome", labelnames=("kind", "outcome")
)
JOB_DURATION = Histogram(
    "fde_job_duration_seconds", "Durable job execution duration", labelnames=("kind",)
)
OLDEST_QUEUED_JOB = Gauge(
    "fde_oldest_queued_job_seconds", "Age of the oldest queued durable job"
)


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


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


def configure_tracing(app: object) -> None:
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
    FastAPIInstrumentor.instrument_app(app)  # type: ignore[arg-type]
    SQLAlchemyInstrumentor().instrument(engine=engine)
    RedisInstrumentor().instrument()
