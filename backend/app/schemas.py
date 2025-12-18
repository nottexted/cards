from __future__ import annotations
from datetime import datetime, date
from uuid import UUID
import re
from pydantic import BaseModel, Field, ConfigDict, field_validator, ValidationInfo

# ---------- Common ----------

class PageMeta(BaseModel):
    total: int
    limit: int
    offset: int

class Page(BaseModel):
    meta: PageMeta
    items: list

# ---------- Reference DTOs ----------

class RefItemBase(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    is_active: bool = True

class RefItemOut(RefItemBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class RefBranchCreate(BaseModel):
    code: str
    name: str
    city: str
    address: str
    phone: str | None = None
    is_active: bool = True

class RefBranchOut(RefBranchCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)

class RefVendorCreate(BaseModel):
    vendor_type: str  # manufacturer/courier
    name: str
    contacts: str | None = None
    sla_days: int = 3
    is_active: bool = True

class RefVendorOut(RefVendorCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)

class RefCardProductCreate(BaseModel):
    code: str
    name: str
    payment_system: str
    level: str
    currency: str = "RUB"
    term_months: int = 36
    is_virtual: bool = False
    metadata_json: dict = Field(default_factory=dict)
    is_active: bool = True

class RefCardProductOut(RefCardProductCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)

class RefTariffPlanCreate(BaseModel):
    code: str
    name: str
    issue_fee: float = 0
    monthly_fee: float = 0
    delivery_subsidy: float = 0
    free_condition_text: str | None = None
    limits_json: dict = Field(default_factory=dict)
    is_active: bool = True

class RefTariffPlanOut(RefTariffPlanCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)

# ---------- Clients ----------

class ClientCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=250)
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=120)

    birth_date: date | None = None
    gender: str | None = None
    citizenship: str | None = None

    doc_type: str | None = None
    doc_number: str | None = None
    doc_issue_date: date | None = None
    doc_issuer: str | None = None

    reg_address: str | None = None
    fact_address: str | None = None

    segment: str | None = None
    kyc_status: str = "new"
    risk_level: str | None = None
    note: str | None = None

    @field_validator("doc_number")
    @classmethod
    def normalize_doc_number(cls, v: str | None, info: ValidationInfo) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if v == "":
            return None
        # Normalize passport to: '#### ######' (4 digits series + 6 digits number)
        doc_type = (info.data.get("doc_type") or "").lower()
        if "паспорт" in doc_type or doc_type == "":
            digits = re.sub(r"\D", "", v)
            if len(digits) != 10:
                raise ValueError("Паспорт должен содержать 10 цифр: 4 (серия) + 6 (номер), формат '1234 567890'")
            return f"{digits[:4]} {digits[4:]}"
        return v

class ClientUpdate(ClientCreate):
    pass

class ClientOut(ClientCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# ---------- Applications ----------

class ApplicationCreate(BaseModel):
    client_id: UUID
    product_id: int
    tariff_id: int
    channel_id: int
    branch_id: int
    delivery_method_id: int

    delivery_address: str | None = None
    delivery_comment: str | None = None
    embossing_name: str | None = Field(default=None, max_length=40)
    is_salary_project: bool = False

    requested_delivery_date: date | None = None
    priority: str = "normal"
    limits_requested_json: dict = Field(default_factory=dict)

    consent_personal_data: bool = True
    consent_marketing: bool = False

    comment: str | None = None

class ApplicationUpdate(ApplicationCreate):
    pass

class ApplicationDecisionIn(BaseModel):
    decision: str  # approve/reject
    reject_reason_id: int | None = None
    planned_issue_date: date | None = None
    kyc_score: int | None = Field(default=None, ge=0, le=1000)
    kyc_result: str | None = None
    kyc_notes: str | None = None
    decision_by: str | None = None


class BatchBriefOut(BaseModel):
    id: UUID
    batch_no: str
    status: RefItemOut | None = None

class CardBriefOut(BaseModel):
    id: UUID
    card_no: str
    status: RefItemOut | None = None
class ApplicationOut(BaseModel):
    id: UUID
    application_no: str
    requested_at: datetime
    planned_issue_date: date | None

    status: RefItemOut
    reject_reason: RefItemOut | None

    client: ClientOut
    product: RefCardProductOut
    tariff: RefTariffPlanOut
    channel: RefItemOut
    branch: RefBranchOut
    delivery: RefItemOut

    delivery_address: str | None
    delivery_comment: str | None
    embossing_name: str | None
    is_salary_project: bool

    requested_delivery_date: date | None
    priority: str
    limits_requested_json: dict

    consent_personal_data: bool
    consent_marketing: bool

    kyc_score: int | None
    kyc_result: str | None
    kyc_notes: str | None

    decision_at: datetime | None
    decision_by: str | None

    comment: str | None

    created_at: datetime
    updated_at: datetime

    batch: BatchBriefOut | None = None
    card: CardBriefOut | None = None

# ---------- Batches ----------

class BatchCreate(BaseModel):
    vendor_id: int
    planned_send_at: datetime | None = None


class BatchUpdate(BaseModel):
    vendor_id: int | None = None
    planned_send_at: datetime | None = None

class BatchOut(BaseModel):
    id: UUID
    batch_no: str
    vendor: RefVendorOut
    status: RefItemOut
    planned_send_at: datetime | None
    sent_at: datetime | None
    received_at: datetime | None
    created_at: datetime

class BatchAddItems(BaseModel):
    application_ids: list[UUID]

# ---------- Cards ----------

class CardEnsureOut(BaseModel):
    card_id: UUID
    card_no: str

class CardEventIn(BaseModel):
    event: str  # issued/delivered/handed/activated/closed
    by: str | None = None

class CardOut(BaseModel):
    id: UUID
    card_no: str
    status: RefItemOut
    pan_masked: str | None
    expiry_month: int | None
    expiry_year: int | None
    issued_at: datetime | None
    delivered_at: datetime | None
    handed_at: datetime | None
    activated_at: datetime | None
    closed_at: datetime | None
    application_id: UUID

# ---------- Reports ----------

class FunnelReportOut(BaseModel):
    applications: int
    approved: int
    rejected: int
    issued: int
    handed: int
    activated: int

class SlaPoint(BaseModel):
    bucket: str
    days_to_decision_avg: float | None
    days_to_issue_avg: float | None
    days_delivery_avg: float | None
    days_to_activate_avg: float | None

class SlaReportOut(BaseModel):
    points: list[SlaPoint]

class VolumePoint(BaseModel):
    bucket: str
    applications: int
    approved: int
    issued: int
    activated: int

class VolumeReportOut(BaseModel):
    points: list[VolumePoint]

class RejectReasonPoint(BaseModel):
    reason: str
    count: int

class RejectReasonReportOut(BaseModel):
    points: list[RejectReasonPoint]
