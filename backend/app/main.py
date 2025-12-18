from __future__ import annotations

from datetime import datetime, timedelta, date
from uuid import UUID

from fastapi import FastAPI, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from sqlalchemy.orm import Session
from sqlalchemy import select

from .core.config import settings
from .db import get_db
from . import models, schemas, service
from . import pdf as pdf_renderer

app = FastAPI(
    title="Card Issuance Service",
    version="2.0",
    description="Directories + Applications + Batches + Cards lifecycle + Reports + Print forms (FastAPI + Postgres).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(ValueError)
def value_error_handler(_, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})

# ------------------
# Health / Meta
# ------------------

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/api/meta")
def meta(db: Session = Depends(get_db)):
    refs = service.fetch_ref_map(db)
    return {
        "refs": {
            "channels": [schemas.RefItemOut.model_validate(x).model_dump() for x in refs["channels"]],
            "branches": [schemas.RefBranchOut.model_validate(x).model_dump() for x in refs["branches"]],
            "delivery_methods": [schemas.RefItemOut.model_validate(x).model_dump() for x in refs["delivery_methods"]],
            "vendors": [schemas.RefVendorOut.model_validate(x).model_dump() for x in refs["vendors"]],
            "reject_reasons": [schemas.RefItemOut.model_validate(x).model_dump() for x in refs["reject_reasons"]],
            "products": [schemas.RefCardProductOut.model_validate(x).model_dump() for x in refs["products"]],
            "tariffs": [schemas.RefTariffPlanOut.model_validate(x).model_dump() for x in refs["tariffs"]],
        },
        "server_time_utc": datetime.utcnow().isoformat(),
    }

# ------------------
# Reference (Directories)
# ------------------

def _page(total: int, limit: int, offset: int, items: list):
    return {"meta": {"total": total, "limit": limit, "offset": offset}, "items": items}

@app.get("/api/ref/statuses")
def list_statuses(entity_type: str | None = None, db: Session = Depends(get_db)):
    stmt = select(models.RefStatus)
    if entity_type:
        stmt = stmt.where(models.RefStatus.entity_type == entity_type)
    items = db.execute(stmt.order_by(models.RefStatus.entity_type, models.RefStatus.sort_order)).scalars().all()
    return {"items": [{"id": x.id, "entity_type": x.entity_type, "code": x.code, "name": x.name, "sort_order": x.sort_order} for x in items]}

@app.get("/api/ref/branches")
def list_branches(active_only: bool = False, db: Session = Depends(get_db)):
    stmt = select(models.RefBranch)
    if active_only:
        stmt = stmt.where(models.RefBranch.is_active == True)
    items = db.execute(stmt.order_by(models.RefBranch.city, models.RefBranch.name)).scalars().all()
    return {"items": [schemas.RefBranchOut.model_validate(x).model_dump() for x in items]}

@app.post("/api/ref/branches", response_model=schemas.RefBranchOut)
def create_branch(data: schemas.RefBranchCreate, db: Session = Depends(get_db)):
    obj = models.RefBranch(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@app.put("/api/ref/branches/{branch_id}", response_model=schemas.RefBranchOut)
def update_branch(branch_id: int, data: schemas.RefBranchCreate, db: Session = Depends(get_db)):
    obj = db.get(models.RefBranch, branch_id)
    if not obj: raise ValueError("Branch not found")
    for k, v in data.model_dump().items(): setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return obj

@app.get("/api/ref/channels")
def list_channels(active_only: bool = False, db: Session = Depends(get_db)):
    stmt = select(models.RefChannel)
    if active_only:
        stmt = stmt.where(models.RefChannel.is_active == True)
    items = db.execute(stmt.order_by(models.RefChannel.name)).scalars().all()
    return {"items": [schemas.RefItemOut.model_validate(x).model_dump() for x in items]}

@app.post("/api/ref/channels", response_model=schemas.RefItemOut)
def create_channel(data: schemas.RefItemBase, db: Session = Depends(get_db)):
    obj = models.RefChannel(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@app.put("/api/ref/channels/{channel_id}", response_model=schemas.RefItemOut)
def update_channel(channel_id: int, data: schemas.RefItemBase, db: Session = Depends(get_db)):
    obj = db.get(models.RefChannel, channel_id)
    if not obj: raise ValueError("Channel not found")
    for k, v in data.model_dump().items(): setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return obj

@app.get("/api/ref/delivery-methods")
def list_delivery_methods(active_only: bool = False, db: Session = Depends(get_db)):
    stmt = select(models.RefDeliveryMethod)
    if active_only:
        stmt = stmt.where(models.RefDeliveryMethod.is_active == True)
    items = db.execute(stmt.order_by(models.RefDeliveryMethod.name)).scalars().all()
    return {"items": [{"id": x.id, "code": x.code, "name": x.name, "base_cost": float(x.base_cost), "sla_days": x.sla_days, "is_active": x.is_active} for x in items]}

@app.post("/api/ref/delivery-methods")
def create_delivery_method(data: dict, db: Session = Depends(get_db)):
    obj = models.RefDeliveryMethod(**data)
    db.add(obj); db.commit(); db.refresh(obj)
    return {"id": obj.id}

@app.put("/api/ref/delivery-methods/{dm_id}")
def update_delivery_method(dm_id: int, data: dict, db: Session = Depends(get_db)):
    obj = db.get(models.RefDeliveryMethod, dm_id)
    if not obj: raise ValueError("Delivery method not found")
    for k, v in data.items(): setattr(obj, k, v)
    db.commit()
    return {"ok": True}

@app.get("/api/ref/vendors")
def list_vendors(active_only: bool = False, db: Session = Depends(get_db)):
    stmt = select(models.RefVendor)
    if active_only:
        stmt = stmt.where(models.RefVendor.is_active == True)
    items = db.execute(stmt.order_by(models.RefVendor.vendor_type, models.RefVendor.name)).scalars().all()
    return {"items": [schemas.RefVendorOut.model_validate(x).model_dump() for x in items]}

@app.post("/api/ref/vendors", response_model=schemas.RefVendorOut)
def create_vendor(data: schemas.RefVendorCreate, db: Session = Depends(get_db)):
    obj = models.RefVendor(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@app.put("/api/ref/vendors/{vendor_id}", response_model=schemas.RefVendorOut)
def update_vendor(vendor_id: int, data: schemas.RefVendorCreate, db: Session = Depends(get_db)):
    obj = db.get(models.RefVendor, vendor_id)
    if not obj: raise ValueError("Vendor not found")
    for k, v in data.model_dump().items(): setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return obj

@app.get("/api/ref/reject-reasons")
def list_reject_reasons(active_only: bool = False, db: Session = Depends(get_db)):
    stmt = select(models.RefRejectReason)
    if active_only:
        stmt = stmt.where(models.RefRejectReason.is_active == True)
    items = db.execute(stmt.order_by(models.RefRejectReason.name)).scalars().all()
    return {"items": [schemas.RefItemOut.model_validate(x).model_dump() for x in items]}

@app.post("/api/ref/reject-reasons", response_model=schemas.RefItemOut)
def create_reject_reason(data: schemas.RefItemBase, db: Session = Depends(get_db)):
    obj = models.RefRejectReason(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@app.put("/api/ref/reject-reasons/{rr_id}", response_model=schemas.RefItemOut)
def update_reject_reason(rr_id: int, data: schemas.RefItemBase, db: Session = Depends(get_db)):
    obj = db.get(models.RefRejectReason, rr_id)
    if not obj: raise ValueError("Reject reason not found")
    for k, v in data.model_dump().items(): setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return obj

@app.get("/api/ref/products")
def list_products(active_only: bool = False, db: Session = Depends(get_db)):
    stmt = select(models.RefCardProduct)
    if active_only:
        stmt = stmt.where(models.RefCardProduct.is_active == True)
    items = db.execute(stmt.order_by(models.RefCardProduct.payment_system, models.RefCardProduct.level, models.RefCardProduct.name)).scalars().all()
    return {"items": [schemas.RefCardProductOut.model_validate(x).model_dump() for x in items]}

@app.post("/api/ref/products", response_model=schemas.RefCardProductOut)
def create_product(data: schemas.RefCardProductCreate, db: Session = Depends(get_db)):
    obj = models.RefCardProduct(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@app.put("/api/ref/products/{pid}", response_model=schemas.RefCardProductOut)
def update_product(pid: int, data: schemas.RefCardProductCreate, db: Session = Depends(get_db)):
    obj = db.get(models.RefCardProduct, pid)
    if not obj: raise ValueError("Product not found")
    for k, v in data.model_dump().items(): setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return obj

@app.get("/api/ref/tariffs")
def list_tariffs(active_only: bool = False, db: Session = Depends(get_db)):
    stmt = select(models.RefTariffPlan)
    if active_only:
        stmt = stmt.where(models.RefTariffPlan.is_active == True)
    items = db.execute(stmt.order_by(models.RefTariffPlan.name)).scalars().all()
    return {"items": [schemas.RefTariffPlanOut.model_validate(x).model_dump() for x in items]}

@app.post("/api/ref/tariffs", response_model=schemas.RefTariffPlanOut)
def create_tariff(data: schemas.RefTariffPlanCreate, db: Session = Depends(get_db)):
    obj = models.RefTariffPlan(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@app.put("/api/ref/tariffs/{tid}", response_model=schemas.RefTariffPlanOut)
def update_tariff(tid: int, data: schemas.RefTariffPlanCreate, db: Session = Depends(get_db)):
    obj = db.get(models.RefTariffPlan, tid)
    if not obj: raise ValueError("Tariff not found")
    for k, v in data.model_dump().items(): setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return obj

# ------------------
# Clients
# ------------------

@app.get("/api/clients")
def clients_list(q: str | None = None, limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    total, items = service.list_clients(db, q, limit, offset)
    return _page(total, limit, offset, [schemas.ClientOut.model_validate(x).model_dump() for x in items])

@app.post("/api/clients", response_model=schemas.ClientOut)
def clients_create(data: schemas.ClientCreate, db: Session = Depends(get_db)):
    return service.create_client(db, data)

@app.put("/api/clients/{client_id}", response_model=schemas.ClientOut)
def clients_update(client_id: UUID, data: schemas.ClientUpdate, db: Session = Depends(get_db)):
    return service.update_client(db, client_id, data)

@app.get("/api/clients/{client_id}", response_model=schemas.ClientOut)
def clients_get(client_id: UUID, db: Session = Depends(get_db)):
    c = db.get(models.Client, client_id)
    if not c: raise ValueError("Client not found")
    return c

# ------------------
# Applications
# ------------------

@app.get("/api/applications")
def applications_list(
    q: str | None = None,
    statuses: list[str] | None = Query(default=None),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    total, rows = service.list_applications_view(db, q, statuses, date_from, date_to, limit, offset)
    return _page(total, limit, offset, [dict(r) for r in rows])

@app.get("/api/applications/{app_id}", response_model=schemas.ApplicationOut)
def applications_get(app_id: UUID, db: Session = Depends(get_db)):
    row = service.get_application_bundle(db, app_id)
    if not row: raise ValueError("Application not found")
    return row

@app.post("/api/applications", response_model=dict)
def applications_create(data: schemas.ApplicationCreate, db: Session = Depends(get_db)):
    a = service.create_application(db, data)
    return {"id": str(a.id), "application_no": a.application_no}

@app.put("/api/applications/{app_id}", response_model=dict)
def applications_update(app_id: UUID, data: schemas.ApplicationUpdate, db: Session = Depends(get_db)):
    a = service.update_application(db, app_id, data)
    return {"id": str(a.id), "application_no": a.application_no}

@app.post("/api/applications/{app_id}/decision", response_model=dict)
def applications_decide(app_id: UUID, data: schemas.ApplicationDecisionIn, db: Session = Depends(get_db)):
    a = service.decide_application(db, app_id, data)
    return {"id": str(a.id), "status_id": a.status_id}

@app.post("/api/applications/{app_id}/ensure-card", response_model=schemas.CardEnsureOut)
def applications_ensure_card(app_id: UUID, db: Session = Depends(get_db)):
    c = service.ensure_card_for_application(db, app_id)
    return schemas.CardEnsureOut(card_id=c.id, card_no=c.card_no)

# Print forms
def _parse_iso_date(v: str | None) -> date | None:
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except Exception:
        return None


def _normalize_client_for_print(client: dict) -> dict:
    # In SQL we use row_to_json(c.*): dates come as ISO strings -> convert for templates.
    out = dict(client or {})
    for k in ("birth_date", "doc_issue_date"):
        if isinstance(out.get(k), str):
            out[k] = _parse_iso_date(out.get(k))  # type: ignore[arg-type]
    return out

@app.get("/api/applications/{app_id}/print/statement")
def print_statement(
    app_id: UUID,
    staff_name: str | None = None,
    staff_position: str | None = None,
    db: Session = Depends(get_db),
):
    row = service.get_application_bundle(db, app_id)
    if not row: raise ValueError("Application not found")
    staff_name = staff_name.strip()[:120] if staff_name else None
    staff_position = staff_position.strip()[:120] if staff_position else None
    client = _normalize_client_for_print(row["client"])
    pdf_bytes = pdf_renderer.render_pdf("application_statement.html", {
        "app": row, "client": client, "product": row["product"], "tariff": row["tariff"],
        "channel": row["channel"], "branch": row["branch"], "delivery": row["delivery"],
        "staff_name": staff_name, "staff_position": staff_position,
        "generated_at": datetime.utcnow(),
    })
    return StreamingResponse(iter([pdf_bytes]), media_type="application/pdf",
                             headers={"Content-Disposition": f'inline; filename="{row["application_no"]}_statement.pdf"'})

@app.get("/api/applications/{app_id}/print/contract")
def print_contract(
    app_id: UUID,
    staff_name: str | None = None,
    staff_position: str | None = None,
    db: Session = Depends(get_db),
):
    row = service.get_application_bundle(db, app_id)
    if not row: raise ValueError("Application not found")
    staff_name = staff_name.strip()[:120] if staff_name else None
    staff_position = staff_position.strip()[:120] if staff_position else None
    client = _normalize_client_for_print(row["client"])
    pdf_bytes = pdf_renderer.render_pdf("contract_offer.html", {
        "app": row, "client": client, "product": row["product"], "tariff": row["tariff"],
        "channel": row["channel"], "branch": row["branch"], "delivery": row["delivery"],
        "staff_name": staff_name, "staff_position": staff_position,
        "generated_at": datetime.utcnow(),
    })
    return StreamingResponse(iter([pdf_bytes]), media_type="application/pdf",
                             headers={"Content-Disposition": f'inline; filename="{row["application_no"]}_contract.pdf"'})

# ------------------
# Batches
# ------------------

@app.get("/api/batches")
def batches_list(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    total, rows = service.list_batches(db, limit, offset)
    return _page(total, limit, offset, [dict(r) for r in rows])

@app.get("/api/batches/{batch_id}")
def batch_get(batch_id: UUID, db: Session = Depends(get_db)):
    b = service.get_batch_bundle(db, batch_id)
    if not b:
        raise ValueError("Batch not found")
    return b

@app.put("/api/batches/{batch_id}", response_model=dict)
def batch_update(batch_id: UUID, data: schemas.BatchUpdate, db: Session = Depends(get_db)):
    b = service.update_batch(db, batch_id, data)
    return {"id": str(b.id), "batch_no": b.batch_no}

@app.post("/api/batches/{batch_id}/issue-cards", response_model=dict)
def batch_issue_cards(batch_id: UUID, db: Session = Depends(get_db)):
    return service.issue_batch_cards(db, batch_id, by="System")

@app.post("/api/batches", response_model=dict)
def batches_create(data: schemas.BatchCreate, db: Session = Depends(get_db)):
    b = service.create_batch(db, data)
    return {"id": str(b.id), "batch_no": b.batch_no}

@app.post("/api/batches/{batch_id}/items", response_model=dict)
def batches_add_items(batch_id: UUID, data: schemas.BatchAddItems, db: Session = Depends(get_db)):
    service.add_batch_items(db, batch_id, data.application_ids)
    return {"ok": True}

@app.post("/api/batches/{batch_id}/status", response_model=dict)
def batches_set_status(batch_id: UUID, status: str, db: Session = Depends(get_db)):
    b = service.set_batch_status(db, batch_id, status)
    return {"id": str(b.id), "status_id": b.status_id}

# ------------------
# Cards
# ------------------

@app.get("/api/cards")
def cards_list(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    total, rows = service.list_cards(db, limit, offset)
    return _page(total, limit, offset, [dict(r) for r in rows])


@app.get("/api/cards/{card_id}")
def cards_get(card_id: UUID, db: Session = Depends(get_db)):
    row = service.get_card_bundle(db, card_id)
    if not row:
        raise ValueError("Card not found")
    return row

@app.post("/api/cards/{card_id}/event", response_model=dict)
def cards_event(card_id: UUID, data: schemas.CardEventIn, db: Session = Depends(get_db)):
    c = service.card_event(db, card_id, data.event, data.by)
    return {"id": str(c.id), "status_id": c.status_id}

# ------------------
# Reports
# ------------------

def _default_range(days: int = 30):
    dt = datetime.utcnow()
    df = dt - timedelta(days=days)
    return df, dt

@app.get("/api/reports/funnel", response_model=schemas.FunnelReportOut)
def report_funnel(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: Session = Depends(get_db),
):
    if not date_from or not date_to:
        date_from, date_to = _default_range(30)
    return service.report_funnel(db, date_from, date_to)

@app.get("/api/reports/volume", response_model=schemas.VolumeReportOut)
def report_volume(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    bucket: str = "day",
    db: Session = Depends(get_db),
):
    if not date_from or not date_to:
        date_from, date_to = _default_range(90)
    return service.report_volume(db, date_from, date_to, bucket=bucket)

@app.get("/api/reports/sla", response_model=schemas.SlaReportOut)
def report_sla(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    bucket: str = "month",
    db: Session = Depends(get_db),
):
    if not date_from or not date_to:
        date_from, date_to = _default_range(180)
    return service.report_sla(db, date_from, date_to, bucket=bucket)

@app.get("/api/reports/reject-reasons", response_model=schemas.RejectReasonReportOut)
def report_reject_reasons(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: Session = Depends(get_db),
):
    if not date_from or not date_to:
        date_from, date_to = _default_range(365)
    return service.report_reject_reasons(db, date_from, date_to)
