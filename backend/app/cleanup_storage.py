import logging
from datetime import timedelta

from app.core.config import settings
from app.models import utc_now
from app.services.storage import ObjectStorage, get_storage

logger = logging.getLogger(__name__)


def cleanup_expired_intermediates(storage: ObjectStorage | None = None) -> int:
    backend = storage or get_storage()
    cutoff = utc_now() - timedelta(days=settings.INTERMEDIATE_RETENTION_DAYS)
    keys = [
        *backend.list_older_than("uploads", cutoff),
        *backend.list_older_than("reports", cutoff),
    ]
    for key in keys:
        backend.delete(key)
    return len(keys)


def main() -> None:
    deleted = cleanup_expired_intermediates()
    logger.info("Expired intermediate cleanup complete objects_deleted=%d", deleted)


if __name__ == "__main__":
    main()
