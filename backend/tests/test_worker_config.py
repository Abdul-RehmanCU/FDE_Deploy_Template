from app.core.config import settings
from app.worker import celery_app


def test_broker_publication_is_bounded_and_application_driven() -> None:
    transport = celery_app.conf.broker_transport_options
    assert transport["socket_connect_timeout"] == 5
    assert transport["socket_timeout"] == settings.OUTBOX_PUBLISH_TIMEOUT_SECONDS
    assert transport["max_retries"] == 0
    assert celery_app.conf.task_publish_retry is False
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.task_reject_on_worker_lost is True
