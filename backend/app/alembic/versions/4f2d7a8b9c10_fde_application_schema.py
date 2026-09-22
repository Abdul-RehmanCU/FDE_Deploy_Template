"""Create the FDE identity, import, job, contact, and audit schema.

Revision ID: 4f2d7a8b9c10
Revises: fe56fa70289e
"""

import sqlalchemy as sa
from alembic import op

revision = "4f2d7a8b9c10"
down_revision = "fe56fa70289e"
branch_labels = None
depends_on = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.drop_table("item")
    op.add_column("user", sa.Column("role", sa.String(16), server_default="viewer", nullable=False))
    op.add_column("user", sa.Column("must_change_password", sa.Boolean(), server_default=sa.true(), nullable=False))
    op.add_column("user", sa.Column("token_version", sa.Integer(), server_default="0", nullable=False))
    op.add_column("user", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.execute("UPDATE \"user\" SET role = CASE WHEN is_superuser THEN 'admin' ELSE 'viewer' END")
    op.drop_column("user", "is_superuser")
    op.alter_column("user", "created_at", existing_type=sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    op.create_check_constraint("ck_user_role", "user", "role IN ('admin','operator','viewer')")
    op.create_check_constraint("ck_user_token_version", "user", "token_version >= 0")
    op.create_index("ix_user_role", "user", ["role"])

    op.create_table(
        "import_batch",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("upload_object_key", sa.String(512), nullable=False, unique=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("mapping", sa.JSON(), nullable=True),
        sa.Column("header", sa.JSON(), nullable=False),
        sa.Column("total_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("accepted_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rejected_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duplicate_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("existing_contact_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("inserted_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("skipped_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("confirm_idempotency_key", sa.String(128), nullable=True, unique=True),
        sa.Column("confirmation_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), sa.ForeignKey("user.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('uploaded','mapped','validating','validated','importing','completed','failed','cancelled')", name="ck_import_batch_status"),
        sa.CheckConstraint("total_rows >= 0 AND accepted_count >= 0 AND rejected_count >= 0 AND duplicate_count >= 0 AND existing_contact_count >= 0 AND inserted_count >= 0 AND skipped_count >= 0", name="ck_import_batch_counts"),
    )
    op.create_index("ix_import_batch_status_created", "import_batch", ["status", "created_at"])
    op.create_index("ix_import_batch_created_by", "import_batch", ["created_by_id"])

    op.create_table(
        "validation_row",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("import_id", sa.Uuid(), sa.ForeignKey("import_batch.id", ondelete="CASCADE"), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("normalized_email", sa.String(320), nullable=True),
        sa.Column("clean_data", sa.JSON(), nullable=True),
        sa.Column("errors", sa.JSON(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("import_id", "row_number", name="uq_validation_row_import_number"),
        sa.CheckConstraint("row_number > 0", name="ck_validation_row_number"),
        sa.CheckConstraint("outcome IN ('accepted','invalid','file_duplicate','existing_contact')", name="ck_validation_row_outcome"),
    )
    op.create_index("ix_validation_row_import_outcome_row", "validation_row", ["import_id", "outcome", "row_number"])

    op.create_table(
        "contact",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("normalized_email", sa.String(320), nullable=False, unique=True),
        sa.Column("first_name", sa.String(120), nullable=False),
        sa.Column("last_name", sa.String(120), nullable=False),
        sa.Column("company", sa.String(255), nullable=True),
        sa.Column("country_code", sa.String(2), nullable=True),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("source_import_id", sa.Uuid(), sa.ForeignKey("import_batch.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("country_code IS NULL OR country_code ~ '^[A-Z]{2}$'", name="ck_contact_country_code"),
    )
    op.create_index("ix_contact_name_id", "contact", ["last_name", "first_name", "id"])
    op.create_index("ix_contact_import_id", "contact", ["source_import_id"])

    op.create_table(
        "job",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("import_id", sa.Uuid(), sa.ForeignKey("import_batch.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("traceparent", sa.String(255), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), sa.ForeignKey("user.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind IN ('validate','confirm')", name="ck_job_kind"),
        sa.CheckConstraint("status IN ('queued','running','succeeded','failed','cancel_requested','cancelled')", name="ck_job_status"),
        sa.CheckConstraint("attempt_count >= 0 AND max_attempts > 0", name="ck_job_attempt_counts"),
    )
    op.create_index("ix_job_status_created", "job", ["status", "created_at"])
    op.create_index("ix_job_import_id", "job", ["import_id"])
    op.create_index("ix_job_created_by_id", "job", ["created_by_id"])

    op.create_table(
        "job_attempt",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("job.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("worker_id", sa.String(255), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("job_id", "attempt_number", name="uq_job_attempt_number"),
        sa.CheckConstraint("attempt_number > 0", name="ck_job_attempt_number"),
        sa.CheckConstraint("status IN ('queued','running','succeeded','failed','cancel_requested','cancelled')", name="ck_job_attempt_status"),
    )
    op.create_index("ix_job_attempt_job_id", "job_attempt", ["job_id"])

    op.create_table(
        "job_outbox",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("job.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("publish_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("publish_attempts >= 0", name="ck_job_outbox_attempts"),
    )
    op.create_index("ix_job_outbox_pending", "job_outbox", ["published_at", "available_at", "created_at"])

    op.create_table(
        "audit_event",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=True),
        *timestamps(),
    )
    op.create_index("ix_audit_event_created_id", "audit_event", ["created_at", "id"])
    op.create_index("ix_audit_event_actor_id", "audit_event", ["actor_id"])


def downgrade() -> None:
    op.drop_table("audit_event")
    op.drop_table("job_outbox")
    op.drop_table("job_attempt")
    op.drop_table("job")
    op.drop_table("contact")
    op.drop_table("validation_row")
    op.drop_table("import_batch")
    op.drop_index("ix_user_role", table_name="user")
    op.drop_constraint("ck_user_token_version", "user", type_="check")
    op.drop_constraint("ck_user_role", "user", type_="check")
    op.add_column("user", sa.Column("is_superuser", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.execute("UPDATE \"user\" SET is_superuser = (role = 'admin')")
    op.drop_column("user", "updated_at")
    op.drop_column("user", "token_version")
    op.drop_column("user", "must_change_password")
    op.drop_column("user", "role")
    op.create_table(
        "item",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
