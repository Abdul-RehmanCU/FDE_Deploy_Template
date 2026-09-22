import uuid

from celery import Celery  # type: ignore[import-untyped]
from celery.signals import worker_ready  # type: ignore[import-untyped]
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from prometheus_client import REGISTRY, start_http_server
from sqlmodel import Session

from app.core.config import settings
from app.core.db import engine
from app.models import JobKind
from app.services.jobs import reconcile_stalled_jobs, run_confirmation, run_validation
from app.worker_metrics import DurableJobCollector

assert settings.REDIS_URL
celery_app = Celery("fde", broker=settings.REDIS_URL)
CeleryInstrumentor().instrument()
celery_app.conf.update(
    broker_connection_retry_on_startup=True,
    broker_transport_options={
        "socket_connect_timeout": 5,
        "socket_timeout": settings.OUTBOX_PUBLISH_TIMEOUT_SECONDS,
        "max_retries": 0,
        "visibility_timeout": settings.CELERY_TASK_TIME_LIMIT_SECONDS * 2,
    },
    task_acks_late=True,
    task_publish_retry=False,
    task_reject_on_worker_lost=True,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT_SECONDS,
    task_soft_time_limit=max(1, settings.CELERY_TASK_TIME_LIMIT_SECONDS - 10),
    worker_prefetch_multiplier=1,
)


@celery_app.task(
    bind=True,
    name="app.process_job",
    autoretry_for=(OSError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=settings.CELERY_TASK_MAX_RETRIES,
)
def process_job(self: object, job_id: str, kind: str) -> None:
    del self
    parsed_id = uuid.UUID(job_id)
    with Session(engine) as session:
        if JobKind(kind) == JobKind.VALIDATE:
            run_validation(session, parsed_id)
        else:
            run_confirmation(session, parsed_id)


@worker_ready.connect
def reconcile_on_start(**kwargs: object) -> None:
    del kwargs
    REGISTRY.register(DurableJobCollector())
    start_http_server(settings.WORKER_METRICS_PORT)
    with Session(engine) as session:
        reconcile_stalled_jobs(session)
