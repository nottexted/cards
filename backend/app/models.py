from __future__ import annotations

import uuid
from datetime import datetime, date
from sqlalchemy import (
    String, DateTime, Date, Boolean, ForeignKey, Numeric, Text, Integer, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

def uuid_pk():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

# -----------------------
# Reference (Directories)
# -----------------------

class RefStatus(Base):
    __tablename__ = "ref_status"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(20))  # application/card/batch
    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(150))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("entity_type", "code", name="uq_status_entity_code"),
        Index("ix_ref_status_entity", "entity_type", "sort_order"),
    )

class RefBranch(Base):
    __tablename__ = "ref_branch"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    city: Mapped[str] = mapped_column(String(80))
    address: Mapped[str] = mapped_column(String(300))
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class RefChannel(Base):
    __tablename__ = "ref_channel"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class RefDeliveryMethod(Base):
    __tablename__ = "ref_delivery_method"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)  # office/courier/post
    name: Mapped[str] = mapped_column(String(120))
    base_cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    sla_days: Mapped[int] = mapped_column(Integer, default=3)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class RefVendor(Base):
    __tablename__ = "ref_vendor"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vendor_type: Mapped[str] = mapped_column(String(30))  # manufacturer/courier
    name: Mapped[str] = mapped_column(String(150))
    contacts: Mapped[str | None] = mapped_column(String(300), nullable=True)
    sla_days: Mapped[int] = mapped_column(Integer, default=3)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class RefRejectReason(Base):
    __tablename__ = "ref_reject_reason"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(250))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class RefCardProduct(Base):
    # Card product: payment system + level + currency + term + virtual/plastic.
    __tablename__ = "ref_card_product"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    payment_system: Mapped[str] = mapped_column(String(40))   # MIR/Visa/MC (for demo use MIR)
    level: Mapped[str] = mapped_column(String(40))            # Classic/Gold/Premium/Virtual
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    term_months: Mapped[int] = mapped_column(Integer, default=36)
    is_virtual: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class RefTariffPlan(Base):
    __tablename__ = "ref_tariff_plan"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    issue_fee: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    monthly_fee: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    delivery_subsidy: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    free_condition_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    limits_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

# -----------------------
# Domain tables
# -----------------------

class Client(Base):
    __tablename__ = "client"
    id = uuid_pk()

    client_type: Mapped[str] = mapped_column(String(20), default="person")  # person/company
    full_name: Mapped[str] = mapped_column(String(250))
    short_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(120), nullable=True)

    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)
    citizenship: Mapped[str | None] = mapped_column(String(80), nullable=True)

    doc_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    doc_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    doc_issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    doc_issuer: Mapped[str | None] = mapped_column(String(200), nullable=True)

    reg_address: Mapped[str | None] = mapped_column(String(400), nullable=True)
    fact_address: Mapped[str | None] = mapped_column(String(400), nullable=True)

    segment: Mapped[str | None] = mapped_column(String(40), nullable=True)  # mass/affluent/premium etc
    kyc_status: Mapped[str] = mapped_column(String(20), default="new")  # new/verified/failed
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)  # low/medium/high

    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    applications = relationship("CardApplication", back_populates="client")

    __table_args__ = (
        Index("ix_client_name", "full_name"),
        Index("ix_client_doc", "doc_number"),
    )

class CardApplication(Base):
    __tablename__ = "card_application"
    id = uuid_pk()

    application_no: Mapped[str] = mapped_column(String(30), unique=True)  # APP-YYYY-XXXXXX

    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("client.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("ref_card_product.id"))
    tariff_id: Mapped[int] = mapped_column(ForeignKey("ref_tariff_plan.id"))

    channel_id: Mapped[int] = mapped_column(ForeignKey("ref_channel.id"))
    branch_id: Mapped[int] = mapped_column(ForeignKey("ref_branch.id"))

    delivery_method_id: Mapped[int] = mapped_column(ForeignKey("ref_delivery_method.id"))
    delivery_address: Mapped[str | None] = mapped_column(String(400), nullable=True)
    delivery_comment: Mapped[str | None] = mapped_column(String(300), nullable=True)

    embossing_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_salary_project: Mapped[bool] = mapped_column(Boolean, default=False)

    requested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    requested_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    status_id: Mapped[int] = mapped_column(ForeignKey("ref_status.id"))
    reject_reason_id: Mapped[int | None] = mapped_column(ForeignKey("ref_reject_reason.id"), nullable=True)

    kyc_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kyc_result: Mapped[str | None] = mapped_column(String(20), nullable=True)  # pass/fail/manual
    kyc_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    decision_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decision_by: Mapped[str | None] = mapped_column(String(120), nullable=True)

    priority: Mapped[str] = mapped_column(String(20), default="normal")  # low/normal/high
    limits_requested_json: Mapped[dict] = mapped_column(JSONB, default=dict)

    consent_personal_data: Mapped[bool] = mapped_column(Boolean, default=True)
    consent_marketing: Mapped[bool] = mapped_column(Boolean, default=False)

    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    client = relationship("Client", back_populates="applications")
    card = relationship("Card", back_populates="application", uselist=False)

    __table_args__ = (
        Index("ix_app_requested_at", "requested_at"),
        Index("ix_app_status", "status_id"),
        Index("ix_app_client", "client_id"),
        Index("ix_app_no", "application_no"),
    )

class IssueBatch(Base):
    __tablename__ = "issue_batch"
    id = uuid_pk()
    batch_no: Mapped[str] = mapped_column(String(30), unique=True)  # BAT-YYYY-XXXXXX

    vendor_id: Mapped[int] = mapped_column(ForeignKey("ref_vendor.id"))
    status_id: Mapped[int] = mapped_column(ForeignKey("ref_status.id"))

    planned_send_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    items = relationship("IssueBatchItem", back_populates="batch")

class IssueBatchItem(Base):
    __tablename__ = "issue_batch_item"
    id = uuid_pk()
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("issue_batch.id"))
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("card_application.id"), unique=True)

    produced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_to_branch_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    batch = relationship("IssueBatch", back_populates="items")

class Card(Base):
    __tablename__ = "card"
    id = uuid_pk()

    card_no: Mapped[str] = mapped_column(String(30), unique=True)  # CARD-YYYY-XXXXXX
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("card_application.id"), unique=True)

    status_id: Mapped[int] = mapped_column(ForeignKey("ref_status.id"))

    pan_masked: Mapped[str | None] = mapped_column(String(30), nullable=True)
    expiry_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expiry_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    issued_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    handed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    activation_channel_id: Mapped[int | None] = mapped_column(ForeignKey("ref_channel.id"), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    application = relationship("CardApplication", back_populates="card")

    __table_args__ = (
        Index("ix_card_status", "status_id"),
        Index("ix_card_issued_at", "issued_at"),
    )

class StatusHistory(Base):
    __tablename__ = "status_history"
    id = uuid_pk()
    entity_type: Mapped[str] = mapped_column(String(20))
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    status_id: Mapped[int] = mapped_column(ForeignKey("ref_status.id"))
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    changed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)

    __table_args__ = (
        Index("ix_status_hist_entity", "entity_type", "entity_id", "changed_at"),
    )

class FeeOperation(Base):
    __tablename__ = "fee_operation"
    id = uuid_pk()
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("card_application.id"))

    op_type: Mapped[str] = mapped_column(String(30))  # issue_fee/monthly_fee/delivery_cost/plastic_cost
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    meta_json: Mapped[dict] = mapped_column(JSONB, default=dict)

    __table_args__ = (
        Index("ix_fee_app", "application_id", "occurred_at"),
    )
