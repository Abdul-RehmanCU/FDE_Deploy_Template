import uuid

from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags, use_span

from app.models import ImportBatch, JobKind, JobOutbox, User, UserRole
from app.services.jobs import enqueue_job


class RecordingSession:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, value: object) -> None:
        self.added.append(value)

    def flush(self) -> None:
        return None


def test_active_server_context_is_injected_without_caller_header() -> None:
    session = RecordingSession()
    actor = User(
        id=uuid.uuid4(),
        email="trace-actor@example.com",
        role=UserRole.OPERATOR,
        hashed_password="unused",
        must_change_password=False,
    )
    batch = ImportBatch(
        id=uuid.uuid4(),
        original_filename="trace.csv",
        upload_object_key=f"uploads/{uuid.uuid4()}/source.csv",
        header=["Email"],
        created_by_id=actor.id,
    )
    trace_id = int("4bf92f3577b34da6a3ce929d0e0e4736", 16)
    span = NonRecordingSpan(
        SpanContext(
            trace_id=trace_id,
            span_id=int("00f067aa0ba902b7", 16),
            is_remote=False,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )
    )
    with use_span(span):
        job = enqueue_job(
            session,  # type: ignore[arg-type]
            import_batch=batch,
            kind=JobKind.VALIDATE,
            actor=actor,
        )
    outbox = next(value for value in session.added if isinstance(value, JobOutbox))
    expected_prefix = f"00-{trace_id:032x}-"
    assert job.traceparent and job.traceparent.startswith(expected_prefix)
    assert outbox.payload["traceparent"] == job.traceparent
