from collections.abc import Iterable
from datetime import datetime
from typing import Any, cast

from prometheus_client.core import GaugeMetricFamily
from sqlalchemy import func, text
from sqlmodel import Session, col, select

from app.core.db import engine
from app.models import ImportBatch, Job, JobStatus, utc_now


class DurableJobCollector:
    """Read bounded aggregate metrics from PostgreSQL, the durable job authority."""

    def collect(self) -> Iterable[GaugeMetricFamily]:
        healthy = GaugeMetricFamily(
            "fde_worker_metrics_collection_success",
            "Whether durable worker metrics were collected from PostgreSQL",
        )
        try:
            with Session(engine) as session:
                worker_up = GaugeMetricFamily(
                    "fde_worker_up", "Whether the worker metrics process is running"
                )
                worker_up.add_metric([], 1)
                yield worker_up

                connections = GaugeMetricFamily(
                    "fde_database_connections",
                    "PostgreSQL and worker pool connections by bounded state",
                    labels=["state"],
                )
                connection_rows = session.execute(
                    text(
                        "SELECT coalesce(state, 'unknown'), count(*) "
                        "FROM pg_stat_activity WHERE datname = current_database() "
                        "GROUP BY coalesce(state, 'unknown')"
                    )
                ).all()
                for state, count in connection_rows:
                    connections.add_metric([f"postgres_{state}"], int(count))
                pool = engine.pool
                for state, value in (
                    ("checked_out", pool.checkedout()),  # type: ignore[attr-defined]
                    ("pool_size", pool.size()),  # type: ignore[attr-defined]
                    # QueuePool represents unused base capacity as a negative
                    # internal overflow count. Export only connections above
                    # the configured pool size.
                    ("overflow", max(0, pool.overflow())),  # type: ignore[attr-defined]
                ):
                    connections.add_metric([state], value)
                yield connections

                job_rows = session.exec(
                    select(Job.status, func.count()).group_by(Job.status)
                ).all()
                job_metric = GaugeMetricFamily(
                    "fde_jobs", "Durable jobs by status", labels=["status"]
                )
                for status, count in job_rows:
                    job_metric.add_metric([str(status)], count)
                yield job_metric

                oldest = session.exec(
                    select(func.min(Job.created_at)).where(
                        Job.status == JobStatus.QUEUED
                    )
                ).one()
                age_metric = GaugeMetricFamily(
                    "fde_oldest_queued_job_seconds",
                    "Age in seconds of the oldest queued durable job",
                )
                age_metric.add_metric(
                    [],
                    max(0.0, (utc_now() - cast(datetime, oldest)).total_seconds())
                    if oldest
                    else 0.0,
                )
                yield age_metric

                attempt_rows = session.exec(
                    select(Job.kind, func.sum(Job.attempt_count)).group_by(Job.kind)
                ).all()
                attempts = GaugeMetricFamily(
                    "fde_job_attempts", "Durable job attempts by kind", labels=["kind"]
                )
                for kind, count in attempt_rows:
                    attempts.add_metric([str(kind)], int(count or 0))
                yield attempts

                duration_rows = session.exec(
                    select(
                        Job.kind,
                        func.avg(
                            func.extract(
                                "epoch",
                                cast(Any, col(Job.finished_at))
                                - cast(Any, col(Job.started_at)),
                            )
                        ),
                    )
                    .where(
                        Job.status == JobStatus.SUCCEEDED,
                        col(Job.started_at).is_not(None),
                        col(Job.finished_at).is_not(None),
                    )
                    .group_by(Job.kind)
                ).all()
                durations = GaugeMetricFamily(
                    "fde_job_duration_seconds",
                    "Average completed job duration by kind",
                    labels=["kind"],
                )
                for kind, average in duration_rows:
                    durations.add_metric([str(kind)], float(average or 0))
                yield durations

                outcomes = GaugeMetricFamily(
                    "fde_import_rows",
                    "Validated/imported rows by outcome",
                    labels=["outcome"],
                )
                totals = session.execute(
                    select(  # type: ignore[call-overload]
                        func.coalesce(func.sum(ImportBatch.accepted_count), 0),
                        func.coalesce(func.sum(ImportBatch.rejected_count), 0),
                        func.coalesce(func.sum(ImportBatch.duplicate_count), 0),
                        func.coalesce(func.sum(ImportBatch.existing_contact_count), 0),
                        func.coalesce(func.sum(ImportBatch.inserted_count), 0),
                        func.coalesce(func.sum(ImportBatch.skipped_count), 0),
                    )
                ).one()
                for label, value in zip(
                    (
                        "accepted",
                        "rejected",
                        "duplicate",
                        "existing",
                        "inserted",
                        "skipped",
                    ),
                    totals,
                    strict=True,
                ):
                    outcomes.add_metric([label], int(value))
                yield outcomes
            healthy.add_metric([], 1)
        except Exception:
            healthy.add_metric([], 0)
        yield healthy
