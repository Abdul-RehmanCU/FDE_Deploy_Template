# Database and job recovery

PostgreSQL is the durable authority. Redis transports Celery messages and may
be restarted without becoming the source of job status.

An API transaction creates the job and `job_outbox` row together. The publisher
claims outbox rows with `FOR UPDATE SKIP LOCKED`, performs one broker call with
5-second connect and 10-second socket bounds, and records publication. Celery
publish retries are disabled so PostgreSQL controls recovery. A publish failure
leaves the row available for the next publisher pass.

Workers use late acknowledgement and reject work on child loss. Job claim logic
ignores concurrent `running` or completed delivery. Validation refreshes its
heartbeat every 500 rows and during conflict-query batches. Every 30 seconds the
publisher reconciles running jobs with stale heartbeats and queued jobs whose
published message has remained unclaimed beyond the stale threshold. It clears
their publication marker for safe redelivery. Attempts are bounded.

Confirmation locks the import, rechecks cancellation under the job lock, marks
the transaction start, and inserts contacts with PostgreSQL `ON CONFLICT DO
NOTHING`. Counts reflect returned inserted IDs. A process failure before commit
rolls back contacts, state, and audit; replay can retry. A failure after commit
finds completed state and returns without new contacts. Database migrations are
not automatically reversed during application rollback.

## Backup/restore drill

Use installation-specific credentials and never overwrite the live database.
A customer drill should:

1. create a PostgreSQL custom-format backup with `pg_dump`;
2. create a disposable empty database;
3. restore with `pg_restore --clean --if-exists` only against that disposable
   target;
4. compare user, import, validation-row, contact, job, outbox, and audit counts;
5. run the application readiness check and a read-only directory query;
6. delete the disposable database and retain sanitized count evidence.

The demo/in-cluster and managed Cloud SQL procedures are deployment-owned.
Backup/restore execution against a live GCP installation remains **pending
verification** until its evidence bundle identifies the tested revision,
database target, timestamps, counts, and cleanup result.
