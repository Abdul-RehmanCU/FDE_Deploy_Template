import logging
import time
from time import monotonic

from opentelemetry import trace
from opentelemetry.propagate import extract
from sqlmodel import Session, col, select

from app.core.config import settings
from app.core.db import engine
from app.core.observability import configure_logging
from app.models import JobOutbox, utc_now
from app.services.jobs import reconcile_stalled_jobs
from app.worker import celery_app

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


def publish_batch() -> int:
    with Session(engine) as session:
        rows = session.exec(
            select(JobOutbox)
            .where(
                col(JobOutbox.published_at).is_(None),
                JobOutbox.available_at <= utc_now(),
            )
            .order_by(col(JobOutbox.created_at))
            .limit(20)
            .with_for_update(skip_locked=True)
        ).all()
        for row in rows:
            row.publish_attempts += 1
            try:
                headers = (
                    {"traceparent": row.payload["traceparent"]}
                    if row.payload.get("traceparent")
                    else {}
                )
                context = extract(headers) if headers else None
                with tracer.start_as_current_span("outbox.publish", context=context):
                    celery_app.send_task(
                        "app.process_job",
                        kwargs={
                            key: value
                            for key, value in row.payload.items()
                            if key != "traceparent"
                        },
                        task_id=str(row.job_id),
                        headers=headers,
                        retry=False,
                    )
                    logger.info("job_published", extra={"event": "job_published"})
                row.published_at = utc_now()
                row.last_error = None
            except Exception:
                row.last_error = "Queue publication failed"
                session.add(row)
                session.commit()
                raise
            session.add(row)
        session.commit()
        return len(rows)


def main() -> None:
    configure_logging()
    last_reconcile = 0.0
    while True:
        if monotonic() - last_reconcile >= settings.JOB_RECONCILE_INTERVAL_SECONDS:
            try:
                with Session(engine) as session:
                    reconcile_stalled_jobs(session)
            except Exception:
                logger.error("Stalled job reconciliation failed")
            last_reconcile = monotonic()
        try:
            count = publish_batch()
        except Exception:
            logger.error("Outbox publication failed")
            count = 0
        time.sleep(0 if count == 20 else settings.OUTBOX_POLL_SECONDS)


if __name__ == "__main__":
    main()
