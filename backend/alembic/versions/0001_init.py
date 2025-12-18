"""Initial schema for Card Issuance Service"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # sequences for business numbers
    op.execute("CREATE SEQUENCE IF NOT EXISTS app_seq START 1;")
    op.execute("CREATE SEQUENCE IF NOT EXISTS batch_seq START 1;")
    op.execute("CREATE SEQUENCE IF NOT EXISTS card_seq START 1;")

    op.create_table(
        "ref_status",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(20), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("entity_type", "code", name="uq_status_entity_code"),
    )
    op.create_index("ix_ref_status_entity", "ref_status", ["entity_type", "sort_order"])

    op.create_table(
        "ref_branch",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("city", sa.String(80), nullable=False),
        sa.Column("address", sa.String(300), nullable=False),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "ref_channel",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(30), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "ref_delivery_method",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(30), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("base_cost", sa.Numeric(12,2), nullable=False, server_default="0"),
        sa.Column("sla_days", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "ref_vendor",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vendor_type", sa.String(30), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("contacts", sa.String(300), nullable=True),
        sa.Column("sla_days", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "ref_reject_reason",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
        sa.Column("name", sa.String(250), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "ref_card_product",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("payment_system", sa.String(40), nullable=False),
        sa.Column("level", sa.String(40), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="RUB"),
        sa.Column("term_months", sa.Integer(), nullable=False, server_default="36"),
        sa.Column("is_virtual", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "ref_tariff_plan",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("issue_fee", sa.Numeric(12,2), nullable=False, server_default="0"),
        sa.Column("monthly_fee", sa.Numeric(12,2), nullable=False, server_default="0"),
        sa.Column("delivery_subsidy", sa.Numeric(12,2), nullable=False, server_default="0"),
        sa.Column("free_condition_text", sa.String(500), nullable=True),
        sa.Column("limits_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "client",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("client_type", sa.String(20), nullable=False, server_default="person"),
        sa.Column("full_name", sa.String(250), nullable=False),
        sa.Column("short_name", sa.String(120), nullable=True),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("email", sa.String(120), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(10), nullable=True),
        sa.Column("citizenship", sa.String(80), nullable=True),
        sa.Column("doc_type", sa.String(40), nullable=True),
        sa.Column("doc_number", sa.String(40), nullable=True),
        sa.Column("doc_issue_date", sa.Date(), nullable=True),
        sa.Column("doc_issuer", sa.String(200), nullable=True),
        sa.Column("reg_address", sa.String(400), nullable=True),
        sa.Column("fact_address", sa.String(400), nullable=True),
        sa.Column("segment", sa.String(40), nullable=True),
        sa.Column("kyc_status", sa.String(20), nullable=False, server_default="new"),
        sa.Column("risk_level", sa.String(20), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_client_name", "client", ["full_name"])
    op.create_index("ix_client_doc", "client", ["doc_number"])

    op.create_table(
        "card_application",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("application_no", sa.String(30), nullable=False, unique=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("client.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("ref_card_product.id"), nullable=False),
        sa.Column("tariff_id", sa.Integer(), sa.ForeignKey("ref_tariff_plan.id"), nullable=False),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("ref_channel.id"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("ref_branch.id"), nullable=False),
        sa.Column("delivery_method_id", sa.Integer(), sa.ForeignKey("ref_delivery_method.id"), nullable=False),
        sa.Column("delivery_address", sa.String(400), nullable=True),
        sa.Column("delivery_comment", sa.String(300), nullable=True),
        sa.Column("embossing_name", sa.String(40), nullable=True),
        sa.Column("is_salary_project", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("requested_delivery_date", sa.Date(), nullable=True),
        sa.Column("planned_issue_date", sa.Date(), nullable=True),
        sa.Column("status_id", sa.Integer(), sa.ForeignKey("ref_status.id"), nullable=False),
        sa.Column("reject_reason_id", sa.Integer(), sa.ForeignKey("ref_reject_reason.id"), nullable=True),
        sa.Column("kyc_score", sa.Integer(), nullable=True),
        sa.Column("kyc_result", sa.String(20), nullable=True),
        sa.Column("kyc_notes", sa.Text(), nullable=True),
        sa.Column("decision_at", sa.DateTime(), nullable=True),
        sa.Column("decision_by", sa.String(120), nullable=True),
        sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("limits_requested_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("consent_personal_data", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("consent_marketing", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_app_requested_at", "card_application", ["requested_at"])
    op.create_index("ix_app_status", "card_application", ["status_id"])
    op.create_index("ix_app_client", "card_application", ["client_id"])
    op.create_index("ix_app_no", "card_application", ["application_no"])

    op.create_table(
        "issue_batch",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("batch_no", sa.String(30), nullable=False, unique=True),
        sa.Column("vendor_id", sa.Integer(), sa.ForeignKey("ref_vendor.id"), nullable=False),
        sa.Column("status_id", sa.Integer(), sa.ForeignKey("ref_status.id"), nullable=False),
        sa.Column("planned_send_at", sa.DateTime(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "issue_batch_item",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("issue_batch.id"), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("card_application.id"), nullable=False, unique=True),
        sa.Column("produced_at", sa.DateTime(), nullable=True),
        sa.Column("delivered_to_branch_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "card",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("card_no", sa.String(30), nullable=False, unique=True),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("card_application.id"), nullable=False, unique=True),
        sa.Column("status_id", sa.Integer(), sa.ForeignKey("ref_status.id"), nullable=False),
        sa.Column("pan_masked", sa.String(30), nullable=True),
        sa.Column("expiry_month", sa.Integer(), nullable=True),
        sa.Column("expiry_year", sa.Integer(), nullable=True),
        sa.Column("issued_at", sa.DateTime(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("handed_at", sa.DateTime(), nullable=True),
        sa.Column("activated_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("activation_channel_id", sa.Integer(), sa.ForeignKey("ref_channel.id"), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
    )
    op.create_index("ix_card_status", "card", ["status_id"])
    op.create_index("ix_card_issued_at", "card", ["issued_at"])

    op.create_table(
        "status_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.String(20), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status_id", sa.Integer(), sa.ForeignKey("ref_status.id"), nullable=False),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
        sa.Column("changed_by", sa.String(120), nullable=True),
    )
    op.create_index("ix_status_hist_entity", "status_history", ["entity_type", "entity_id", "changed_at"])

    op.create_table(
        "fee_operation",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("card_application.id"), nullable=False),
        sa.Column("op_type", sa.String(30), nullable=False),
        sa.Column("amount", sa.Numeric(12,2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="RUB"),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("meta_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_fee_app", "fee_operation", ["application_id", "occurred_at"])

def downgrade():
    op.drop_index("ix_fee_app", table_name="fee_operation")
    op.drop_table("fee_operation")
    op.drop_index("ix_status_hist_entity", table_name="status_history")
    op.drop_table("status_history")
    op.drop_index("ix_card_issued_at", table_name="card")
    op.drop_index("ix_card_status", table_name="card")
    op.drop_table("card")
    op.drop_table("issue_batch_item")
    op.drop_table("issue_batch")
    op.drop_index("ix_app_no", table_name="card_application")
    op.drop_index("ix_app_client", table_name="card_application")
    op.drop_index("ix_app_status", table_name="card_application")
    op.drop_index("ix_app_requested_at", table_name="card_application")
    op.drop_table("card_application")
    op.drop_index("ix_client_doc", table_name="client")
    op.drop_index("ix_client_name", table_name="client")
    op.drop_table("client")
    op.drop_table("ref_tariff_plan")
    op.drop_table("ref_card_product")
    op.drop_table("ref_reject_reason")
    op.drop_table("ref_vendor")
    op.drop_table("ref_delivery_method")
    op.drop_table("ref_channel")
    op.drop_table("ref_branch")
    op.drop_index("ix_ref_status_entity", table_name="ref_status")
    op.drop_table("ref_status")
    op.execute("DROP SEQUENCE IF EXISTS card_seq;")
    op.execute("DROP SEQUENCE IF EXISTS batch_seq;")
    op.execute("DROP SEQUENCE IF EXISTS app_seq;")
