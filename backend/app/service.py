from __future__ import annotations
from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select, text, bindparam, or_
from . import models
from .utils import utcnow, next_seq, make_no

# --------------------
# Helpers
# --------------------

def get_status_id(db: Session, entity_type: str, code: str) -> int:
    s = db.execute(
        select(models.RefStatus).where(models.RefStatus.entity_type == entity_type, models.RefStatus.code == code)
    ).scalar_one()
    return s.id

def add_history(db: Session, entity_type: str, entity_id: UUID, status_id: int, by: str | None = None):
    db.add(models.StatusHistory(entity_type=entity_type, entity_id=entity_id, status_id=status_id,
                               changed_at=utcnow(), changed_by=by))

def set_status(db: Session, entity_type: str, entity_id: UUID, status_code: str, by: str | None = None) -> int:
    sid = get_status_id(db, entity_type, status_code)
    add_history(db, entity_type, entity_id, sid, by)
    return sid

def fetch_ref_map(db: Session):
    # Often needed for UI dropdowns.
    return {
        "statuses": db.execute(select(models.RefStatus)).scalars().all(),
        "channels": db.execute(select(models.RefChannel).where(models.RefChannel.is_active == True)).scalars().all(),
        "branches": db.execute(select(models.RefBranch).where(models.RefBranch.is_active == True)).scalars().all(),
        "delivery_methods": db.execute(select(models.RefDeliveryMethod).where(models.RefDeliveryMethod.is_active == True)).scalars().all(),
        "vendors": db.execute(select(models.RefVendor).where(models.RefVendor.is_active == True)).scalars().all(),
        "reject_reasons": db.execute(select(models.RefRejectReason).where(models.RefRejectReason.is_active == True)).scalars().all(),
        "products": db.execute(select(models.RefCardProduct).where(models.RefCardProduct.is_active == True)).scalars().all(),
        "tariffs": db.execute(select(models.RefTariffPlan).where(models.RefTariffPlan.is_active == True)).scalars().all(),
    }

# --------------------
# Clients
# --------------------

def create_client(db: Session, data) -> models.Client:
    c = models.Client(**data.model_dump())
    c.created_at = utcnow()
    c.updated_at = utcnow()
    db.add(c)
    db.commit()
    db.refresh(c)
    return c

def update_client(db: Session, client_id: UUID, data) -> models.Client:
    c = db.get(models.Client, client_id)
    if not c:
        raise ValueError("Client not found")
    for k, v in data.model_dump().items():
        setattr(c, k, v)
    c.updated_at = utcnow()
    db.commit()
    db.refresh(c)
    return c

def list_clients(db: Session, q: str | None, limit: int, offset: int):
    stmt = select(models.Client)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(models.Client.full_name.ilike(like), models.Client.doc_number.ilike(like)))
    total = db.execute(select(text("count(*)")).select_from(stmt.subquery())).scalar_one()
    items = db.execute(stmt.order_by(models.Client.created_at.desc()).limit(limit).offset(offset)).scalars().all()
    return total, items

# --------------------
# Applications
# --------------------

def create_application(db: Session, data, by: str | None = None) -> models.CardApplication:
    year = utcnow().year
    seq = next_seq(db, "app_seq")
    app_no = make_no("APP", year, seq, 6)

    sid = get_status_id(db, "application", "NEW")
    a = models.CardApplication(**data.model_dump(), application_no=app_no, status_id=sid)
    a.requested_at = utcnow()
    a.created_at = utcnow()
    a.updated_at = utcnow()

    db.add(a)
    db.commit()
    db.refresh(a)

    add_history(db, "application", a.id, sid, by)
    db.commit()
    return a

def update_application(db: Session, app_id: UUID, data, by: str | None = None) -> models.CardApplication:
    a = db.get(models.CardApplication, app_id)
    if not a:
        raise ValueError("Application not found")

    # protect fields if already decided
    status = db.get(models.RefStatus, a.status_id)
    if status.code in {"APPROVED", "REJECTED", "IN_BATCH"}:
        raise ValueError("Application is already in a final or processing state. Editing is restricted.")

    for k, v in data.model_dump().items():
        setattr(a, k, v)
    a.updated_at = utcnow()
    db.commit()
    db.refresh(a)
    return a

def decide_application(db: Session, app_id: UUID, data, by: str | None = None) -> models.CardApplication:
    a = db.get(models.CardApplication, app_id)
    if not a:
        raise ValueError("Application not found")

    cur = db.get(models.RefStatus, a.status_id).code
    if cur not in {"NEW", "IN_REVIEW"}:
        raise ValueError(f"Decision is not allowed from status {cur}")

    now = utcnow()
    a.kyc_score = data.kyc_score
    a.kyc_result = data.kyc_result
    a.kyc_notes = data.kyc_notes
    a.decision_at = now
    a.decision_by = data.decision_by or by

    if data.decision == "approve":
        a.reject_reason_id = None
        a.planned_issue_date = data.planned_issue_date
        a.status_id = set_status(db, "application", a.id, "APPROVED", by)
    elif data.decision == "reject":
        if not data.reject_reason_id:
            raise ValueError("reject_reason_id is required for rejection")
        a.reject_reason_id = data.reject_reason_id
        a.status_id = set_status(db, "application", a.id, "REJECTED", by)
    else:
        raise ValueError("decision must be 'approve' or 'reject'")

    a.updated_at = now
    db.commit()
    db.refresh(a)
    return a


def get_application_bundle(db: Session, app_id: UUID):
    # heavy view for UI (detail)
    q = text("""
      SELECT
        a.*,
        row_to_json(c.*) AS client,
        row_to_json(p.*) AS product,
        row_to_json(t.*) AS tariff,
        jsonb_build_object('id', ch.id, 'code', ch.code, 'name', ch.name, 'is_active', ch.is_active) AS channel,
        row_to_json(b.*) AS branch,
        jsonb_build_object('id', d.id, 'code', d.code, 'name', d.name, 'is_active', d.is_active) AS delivery,
        CASE WHEN rr.id IS NULL THEN NULL ELSE jsonb_build_object('id', rr.id, 'code', rr.code, 'name', rr.name, 'is_active', rr.is_active) END AS reject_reason,
        jsonb_build_object('id', s.id, 'code', s.code, 'name', s.name, 'is_active', true) AS status,
        CASE WHEN bat.id IS NULL THEN NULL ELSE jsonb_build_object(
          'id', bat.id,
          'batch_no', bat.batch_no,
          'status', jsonb_build_object('id', bs.id, 'code', bs.code, 'name', bs.name, 'is_active', true)
        ) END AS batch,
        (CASE WHEN cd.id IS NULL THEN NULL ELSE jsonb_build_object(
          'id', cd.id,
          'card_no', cd.card_no,
          'status', jsonb_build_object('id', cs.id, 'code', cs.code, 'name', cs.name, 'is_active', true)
        ) END) AS card
      FROM card_application a
      JOIN client c ON c.id=a.client_id
      JOIN ref_card_product p ON p.id=a.product_id
      JOIN ref_tariff_plan t ON t.id=a.tariff_id
      JOIN ref_channel ch ON ch.id=a.channel_id
      JOIN ref_branch b ON b.id=a.branch_id
      JOIN ref_delivery_method d ON d.id=a.delivery_method_id
      JOIN ref_status s ON s.id=a.status_id
      LEFT JOIN ref_reject_reason rr ON rr.id=a.reject_reason_id
      LEFT JOIN issue_batch_item bi ON bi.application_id=a.id
      LEFT JOIN issue_batch bat ON bat.id=bi.batch_id
      LEFT JOIN ref_status bs ON bs.id=bat.status_id
      LEFT JOIN card cd ON cd.application_id=a.id
      LEFT JOIN ref_status cs ON cs.id=cd.status_id
      WHERE a.id=:app_id
    """)
    row = db.execute(q, {"app_id": app_id}).mappings().one_or_none()
    return row




def list_applications_view(
    db: Session,
    q: str | None,
    status_codes: list[str] | None,
    date_from: datetime | None,
    date_to: datetime | None,
    limit: int,
    offset: int,
):
    base = """
      FROM card_application a
      JOIN client c ON c.id=a.client_id
      JOIN ref_card_product p ON p.id=a.product_id
      JOIN ref_tariff_plan t ON t.id=a.tariff_id
      JOIN ref_channel ch ON ch.id=a.channel_id
      JOIN ref_branch b ON b.id=a.branch_id
      JOIN ref_delivery_method d ON d.id=a.delivery_method_id
      LEFT JOIN ref_reject_reason rr ON rr.id=a.reject_reason_id
      JOIN ref_status s ON s.id=a.status_id
      LEFT JOIN issue_batch_item bi ON bi.application_id=a.id
      LEFT JOIN issue_batch bat ON bat.id=bi.batch_id
      LEFT JOIN ref_status bs ON bs.id=bat.status_id
      LEFT JOIN card cd ON cd.application_id=a.id
      LEFT JOIN ref_status cs ON cs.id=cd.status_id
    """

    where = " WHERE 1=1"
    params: dict = {}

    if q:
        params["q"] = f"%{q.strip()}%"
        where += " AND (a.application_no ILIKE :q OR c.full_name ILIKE :q OR c.doc_number ILIKE :q)"

    if status_codes:
        params["sc"] = status_codes
        # IMPORTANT: with text() we must use expanding bindparam for IN
        where += " AND s.code IN :sc"

    if date_from:
        params["df"] = date_from
        where += " AND a.requested_at >= :df"

    if date_to:
        params["dt"] = date_to
        where += " AND a.requested_at < :dt"

    count_stmt = text("SELECT count(*) " + base + where)

    sql = """
      SELECT
        a.id, a.application_no, a.requested_at, a.planned_issue_date, a.requested_delivery_date,
        a.priority, a.is_salary_project, a.embossing_name,
        a.delivery_address, a.delivery_comment,
        a.kyc_score, a.kyc_result, a.decision_at, a.decision_by,
        a.reject_reason_id,
        a.comment, a.created_at, a.updated_at,
        row_to_json(c.*) AS client,
        row_to_json(p.*) AS product,
        row_to_json(t.*) AS tariff,
        row_to_json(ch.*) AS channel,
        row_to_json(b.*) AS branch,
        row_to_json(d.*) AS delivery_method,
        jsonb_build_object('id', s.id, 'entity_type', s.entity_type, 'code', s.code, 'name', s.name) AS status,
        (CASE WHEN rr.id IS NULL THEN NULL ELSE jsonb_build_object('id', rr.id, 'code', rr.code, 'name', rr.name) END) AS reject_reason,
        (CASE WHEN bat.id IS NULL THEN NULL ELSE jsonb_build_object(
          'id', bat.id,
          'batch_no', bat.batch_no,
          'planned_send_at', bat.planned_send_at,
          'sent_at', bat.sent_at,
          'received_at', bat.received_at,
          'status', jsonb_build_object('id', bs.id, 'entity_type', bs.entity_type, 'code', bs.code, 'name', bs.name)
        ) END) AS batch,
        (CASE WHEN cd.id IS NULL THEN NULL ELSE jsonb_build_object(
          'id', cd.id,
          'card_no', cd.card_no,
          'pan_masked', cd.pan_masked,
          'expiry_month', cd.expiry_month,
          'expiry_year', cd.expiry_year,
          'issued_at', cd.issued_at,
          'delivered_at', cd.delivered_at,
          'handed_at', cd.handed_at,
          'activated_at', cd.activated_at,
          'status', jsonb_build_object('id', cs.id, 'entity_type', cs.entity_type, 'code', cs.code, 'name', cs.name)
        ) END) AS card
      """ + base + where + """
      ORDER BY a.requested_at DESC
      LIMIT :limit OFFSET :offset
    """

    data_stmt = text(sql)
    params.update({"limit": limit, "offset": offset})

    if "sc" in params:
        count_stmt = count_stmt.bindparams(bindparam("sc", expanding=True))
        data_stmt = data_stmt.bindparams(bindparam("sc", expanding=True))

    total = db.execute(count_stmt, params).scalar_one()
    rows = db.execute(data_stmt, params).mappings().all()
    return total, rows

# --------------------
# Batches
# --------------------

def create_batch(db: Session, data, by: str | None = None) -> models.IssueBatch:
    year = utcnow().year
    seq = next_seq(db, "batch_seq")
    batch_no = make_no("BAT", year, seq, 6)

    sid = get_status_id(db, "batch", "CREATED")
    b = models.IssueBatch(
        batch_no=batch_no,
        vendor_id=data.vendor_id,
        status_id=sid,
        planned_send_at=data.planned_send_at,
        created_at=utcnow(),
    )
    db.add(b)
    db.commit()
    db.refresh(b)

    add_history(db, "batch", b.id, sid, by)
    db.commit()
    return b

def add_batch_items(db: Session, batch_id: UUID, application_ids: list[UUID], by: str | None = None):
    batch = db.get(models.IssueBatch, batch_id)
    if not batch:
        raise ValueError("Batch not found")

    approved_id = get_status_id(db, "application", "APPROVED")
    in_batch_id = get_status_id(db, "application", "IN_BATCH")

    for aid in application_ids:
        a = db.get(models.CardApplication, aid)
        if not a:
            raise ValueError(f"Application {aid} not found")
        if a.status_id != approved_id:
            raise ValueError(f"Application {a.application_no} must be APPROVED to be added to batch")

        # add item (unique constraint on application_id prevents duplicates)
        db.add(models.IssueBatchItem(batch_id=batch_id, application_id=aid))

        # move application to IN_BATCH
        a.status_id = in_batch_id
        a.updated_at = utcnow()
        add_history(db, "application", a.id, in_batch_id, by)

    db.commit()

def set_batch_status(db: Session, batch_id: UUID, status_code: str, by: str | None = None):
    b = db.get(models.IssueBatch, batch_id)
    if not b:
        raise ValueError("Batch not found")

    now = utcnow()
    if status_code == "SENT":
        b.sent_at = now
    if status_code == "RECEIVED":
        b.received_at = now

    b.status_id = set_status(db, "batch", b.id, status_code, by)
    db.commit()
    db.refresh(b)
    if status_code == "RECEIVED":
        # automatically issue cards when batch is received from the vendor
        issue_batch_cards(db, batch_id, by=by)
    return b

def update_batch(db: Session, batch_id: UUID, data, by: str | None = None) -> models.IssueBatch:
    b = db.get(models.IssueBatch, batch_id)
    if not b:
        raise ValueError("Batch not found")
    if data.vendor_id is not None:
        b.vendor_id = data.vendor_id
    if data.planned_send_at is not None or data.planned_send_at is None:
        # allow explicit null
        b.planned_send_at = data.planned_send_at
    b.updated_at = utcnow()
    db.commit()
    db.refresh(b)
    return b


def get_batch_bundle(db: Session, batch_id: UUID):
    sql = text("""
      SELECT
        b.*,
        jsonb_build_object('id', v.id, 'vendor_type', v.vendor_type, 'name', v.name, 'contacts', v.contacts, 'sla_days', v.sla_days, 'is_active', v.is_active) AS vendor,
        jsonb_build_object('id', s.id, 'code', s.code, 'name', s.name, 'is_active', true) AS status
      FROM issue_batch b
      JOIN ref_vendor v ON v.id=b.vendor_id
      JOIN ref_status s ON s.id=b.status_id
      WHERE b.id=:bid
    """)
    batch = db.execute(sql, {"bid": batch_id}).mappings().one_or_none()
    if not batch:
        return None

    items_sql = text("""
      SELECT
        i.id,
        row_to_json(a.*) AS application,
        jsonb_build_object('id', st.id, 'code', st.code, 'name', st.name, 'is_active', true) AS app_status,
        row_to_json(c.*) AS client,
        CASE WHEN cd.id IS NULL THEN NULL ELSE jsonb_build_object(
          'id', cd.id, 'card_no', cd.card_no,
          'status', jsonb_build_object('id', cs.id, 'code', cs.code, 'name', cs.name, 'is_active', true),
          'issued_at', cd.issued_at, 'delivered_at', cd.delivered_at, 'handed_at', cd.handed_at, 'activated_at', cd.activated_at
        ) END AS card
      FROM issue_batch_item i
      JOIN card_application a ON a.id=i.application_id
      JOIN ref_status st ON st.id=a.status_id
      JOIN client c ON c.id=a.client_id
      LEFT JOIN card cd ON cd.application_id=a.id
      LEFT JOIN ref_status cs ON cs.id=cd.status_id
      WHERE i.batch_id=:bid
      ORDER BY a.requested_at DESC
    """)
    items = db.execute(items_sql, {"bid": batch_id}).mappings().all()

    return {**dict(batch), "items": [dict(x) for x in items]}


def issue_batch_cards(db: Session, batch_id: UUID, by: str | None = None) -> dict:
    # Create cards for all applications in the batch and move them to ISSUED
    ids = db.execute(text("SELECT application_id FROM issue_batch_item WHERE batch_id=:bid"), {"bid": batch_id}).scalars().all()
    issued = 0
    created = 0
    for app_id in ids:
        card = ensure_card_for_application(db, app_id, by=by)
        # if already issued or later - skip
        cur_code = db.get(models.RefStatus, card.status_id).code
        if cur_code == "CREATED":
            card_event(db, card.id, "issued", by=by)
            issued += 1
        created += 1
    return {"applications": len(ids), "cards_total": created, "cards_issued_now": issued}


def get_card_bundle(db: Session, card_id: UUID):
    q = text("""
      SELECT
        c.*,
        jsonb_build_object('id', s.id, 'code', s.code, 'name', s.name, 'is_active', true) AS status,
        jsonb_build_object('id', a.id, 'application_no', a.application_no) AS application,
        jsonb_build_object('id', cl.id, 'full_name', cl.full_name, 'phone', cl.phone) AS client,
        CASE WHEN b.id IS NULL THEN NULL ELSE jsonb_build_object('id', b.id, 'batch_no', b.batch_no) END AS batch
      FROM card c
      JOIN ref_status s ON s.id=c.status_id
      JOIN card_application a ON a.id=c.application_id
      JOIN client cl ON cl.id=a.client_id
      LEFT JOIN issue_batch_item bi ON bi.application_id=a.id
      LEFT JOIN issue_batch b ON b.id=bi.batch_id
      WHERE c.id=:cid
    """)
    return db.execute(q, {"cid": card_id}).mappings().one_or_none()


def list_batches(db: Session, limit: int, offset: int):
    total = db.execute(text("SELECT count(*) FROM issue_batch")).scalar_one()
    sql = text("""
      SELECT
        b.*,
        jsonb_build_object('id', v.id, 'vendor_type', v.vendor_type, 'name', v.name, 'contacts', v.contacts, 'sla_days', v.sla_days, 'is_active', v.is_active) AS vendor,
        jsonb_build_object('id', s.id, 'code', s.code, 'name', s.name, 'is_active', true) AS status,
        (SELECT count(*) FROM issue_batch_item i WHERE i.batch_id=b.id) AS applications_count,
        (SELECT count(*) FROM issue_batch_item i JOIN card cd ON cd.application_id=i.application_id WHERE i.batch_id=b.id) AS cards_count,
        (SELECT count(*) FROM issue_batch_item i
           JOIN card cd ON cd.application_id=i.application_id
           JOIN ref_status cs ON cs.id=cd.status_id
         WHERE i.batch_id=b.id AND cs.code='ISSUED') AS cards_issued_count,
        (SELECT count(*) FROM issue_batch_item i
           JOIN card cd ON cd.application_id=i.application_id
           JOIN ref_status cs ON cs.id=cd.status_id
         WHERE i.batch_id=b.id AND cs.code='ACTIVATED') AS cards_activated_count
      FROM issue_batch b
      JOIN ref_vendor v ON v.id=b.vendor_id
      JOIN ref_status s ON s.id=b.status_id
      ORDER BY b.created_at DESC
      LIMIT :limit OFFSET :offset
    """)
    rows = db.execute(sql, {"limit": limit, "offset": offset}).mappings().all()
    return total, rows

# --------------------
# Cards
# --------------------

CARD_ALLOWED = {
    "CREATED": {"ISSUED"},
    "ISSUED": {"DELIVERED"},
    "DELIVERED": {"HANDED"},
    "HANDED": {"ACTIVATED"},
    "ACTIVATED": {"CLOSED"},
    "CLOSED": set(),
}

def ensure_card_for_application(db: Session, app_id: UUID, by: str | None = None) -> models.Card:
    a = db.get(models.CardApplication, app_id)
    if not a:
        raise ValueError("Application not found")
    # must be approved or in batch
    cur_code = db.get(models.RefStatus, a.status_id).code
    if cur_code not in {"APPROVED", "IN_BATCH"}:
        raise ValueError("Card can be created only for APPROVED/IN_BATCH applications")

    existing = db.execute(select(models.Card).where(models.Card.application_id == app_id)).scalar_one_or_none()
    if existing:
        return existing

    year = utcnow().year
    seq = next_seq(db, "card_seq")
    card_no = make_no("CARD", year, seq, 6)

    sid = get_status_id(db, "card", "CREATED")
    c = models.Card(card_no=card_no, application_id=app_id, status_id=sid)
    db.add(c)
    db.commit()
    db.refresh(c)

    add_history(db, "card", c.id, sid, by)
    db.commit()
    return c

def card_event(db: Session, card_id: UUID, event: str, by: str | None = None) -> models.Card:
    c = db.get(models.Card, card_id)
    if not c:
        raise ValueError("Card not found")

    now = utcnow()
    current_code = db.get(models.RefStatus, c.status_id).code

    mapping = {
        "issued": "ISSUED",
        "delivered": "DELIVERED",
        "handed": "HANDED",
        "activated": "ACTIVATED",
        "closed": "CLOSED",
    }
    if event not in mapping:
        raise ValueError("Invalid event")

    next_code = mapping[event]
    if next_code not in CARD_ALLOWED.get(current_code, set()):
        raise ValueError(f"Transition {current_code} -> {next_code} is not allowed")

    # set timestamps + demo PAN
    if next_code == "ISSUED":
        c.issued_at = now
        if not c.pan_masked:
            # demo masked PAN (do not generate real PANs)
            c.pan_masked = "**** **** **** " + str(1000 + (next_seq(db, "card_seq") % 9000))
        if not c.expiry_month:
            c.expiry_month = 12
        if not c.expiry_year:
            c.expiry_year = now.year + 3
    elif next_code == "DELIVERED":
        c.delivered_at = now
    elif next_code == "HANDED":
        c.handed_at = now
    elif next_code == "ACTIVATED":
        c.activated_at = now
    elif next_code == "CLOSED":
        c.closed_at = now

    c.status_id = set_status(db, "card", c.id, next_code, by)
    db.commit()
    db.refresh(c)
    return c

def list_cards(db: Session, limit: int, offset: int):
    total = db.execute(text("SELECT count(*) FROM card")).scalar_one()
    sql = text("""
      SELECT
        c.*,
        jsonb_build_object('id', s.id, 'code', s.code, 'name', s.name, 'is_active', true) AS status,
        jsonb_build_object('id', a.id, 'application_no', a.application_no) AS application,
        jsonb_build_object('id', cl.id, 'full_name', cl.full_name, 'phone', cl.phone) AS client,
        CASE WHEN b.id IS NULL THEN NULL ELSE jsonb_build_object('id', b.id, 'batch_no', b.batch_no) END AS batch
      FROM card c
      JOIN ref_status s ON s.id=c.status_id
      JOIN card_application a ON a.id=c.application_id
      JOIN client cl ON cl.id=a.client_id
      LEFT JOIN issue_batch_item bi ON bi.application_id=a.id
      LEFT JOIN issue_batch b ON b.id=bi.batch_id
      ORDER BY c.issued_at DESC NULLS LAST, c.id DESC
      LIMIT :limit OFFSET :offset
    """)
    rows = db.execute(sql, {"limit": limit, "offset": offset}).mappings().all()
    return total, rows

# --------------------
# Reports (for charts)
# --------------------

def report_funnel(db: Session, date_from: datetime, date_to: datetime):
    q = text("""
    WITH base AS (
      SELECT a.id, a.status_id
      FROM card_application a
      WHERE a.requested_at >= :df AND a.requested_at < :dt
    ),
    app_status AS (
      SELECT b.id, s.code AS status_code
      FROM base b JOIN ref_status s ON s.id=b.status_id
    )
    SELECT
      (SELECT count(*) FROM base) AS applications,
      (SELECT count(*) FROM app_status WHERE status_code='APPROVED' OR status_code='IN_BATCH') AS approved,
      (SELECT count(*) FROM app_status WHERE status_code='REJECTED') AS rejected,
      (SELECT count(*) FROM card c JOIN card_application a ON a.id=c.application_id WHERE a.requested_at >= :df AND a.requested_at < :dt AND c.issued_at IS NOT NULL) AS issued,
      (SELECT count(*) FROM card c JOIN card_application a ON a.id=c.application_id WHERE a.requested_at >= :df AND a.requested_at < :dt AND c.handed_at IS NOT NULL) AS handed,
      (SELECT count(*) FROM card c JOIN card_application a ON a.id=c.application_id WHERE a.requested_at >= :df AND a.requested_at < :dt AND c.activated_at IS NOT NULL) AS activated
    """)
    return dict(db.execute(q, {"df": date_from, "dt": date_to}).mappings().one())

def report_volume(db: Session, date_from: datetime, date_to: datetime, bucket: str = "day"):
    trunc = "day" if bucket == "day" else "month"
    q = text(f"""
    WITH base AS (
      SELECT date_trunc('{trunc}', a.requested_at)::date AS bucket,
             s.code AS app_status,
             a.id AS app_id
      FROM card_application a
      JOIN ref_status s ON s.id=a.status_id
      WHERE a.requested_at >= :df AND a.requested_at < :dt
    ),
    cards AS (
      SELECT date_trunc('{trunc}', a.requested_at)::date AS bucket,
             c.issued_at IS NOT NULL AS issued,
             c.activated_at IS NOT NULL AS activated
      FROM card_application a
      LEFT JOIN card c ON c.application_id=a.id
      WHERE a.requested_at >= :df AND a.requested_at < :dt
    )
    SELECT
      b.bucket::text AS bucket,
      count(*) AS applications,
      count(*) FILTER (WHERE b.app_status IN ('APPROVED','IN_BATCH')) AS approved,
      count(*) FILTER (WHERE c.issued) AS issued,
      count(*) FILTER (WHERE c.activated) AS activated
    FROM base b
    JOIN cards c ON c.bucket=b.bucket
    GROUP BY 1
    ORDER BY 1
    """)
    rows = db.execute(q, {"df": date_from, "dt": date_to}).mappings().all()
    return {"points": [dict(r) for r in rows]}

def report_sla(db: Session, date_from: datetime, date_to: datetime, bucket: str = "month"):
    trunc = "month" if bucket == "month" else "week"
    q = text(f"""
    SELECT
      date_trunc('{trunc}', a.requested_at)::date::text AS bucket,
      AVG(EXTRACT(EPOCH FROM (a.decision_at - a.requested_at))/86400.0) AS days_to_decision_avg,
      AVG(EXTRACT(EPOCH FROM (c.issued_at - a.requested_at))/86400.0) AS days_to_issue_avg,
      AVG(EXTRACT(EPOCH FROM (c.delivered_at - c.issued_at))/86400.0) AS days_delivery_avg,
      AVG(EXTRACT(EPOCH FROM (c.activated_at - c.handed_at))/86400.0) AS days_to_activate_avg
    FROM card_application a
    LEFT JOIN card c ON c.application_id=a.id
    WHERE a.requested_at >= :df AND a.requested_at < :dt
    GROUP BY 1
    ORDER BY 1
    """)
    rows = db.execute(q, {"df": date_from, "dt": date_to}).mappings().all()
    return {"points": [dict(r) for r in rows]}

def report_reject_reasons(db: Session, date_from: datetime, date_to: datetime):
    q = text("""
    SELECT COALESCE(rr.name, 'Не указано') AS reason, COUNT(*) AS count
    FROM card_application a
    JOIN ref_status s ON s.id=a.status_id
    LEFT JOIN ref_reject_reason rr ON rr.id=a.reject_reason_id
    WHERE a.requested_at >= :df AND a.requested_at < :dt
      AND s.code='REJECTED'
    GROUP BY 1
    ORDER BY count DESC, reason
    """)
    rows = db.execute(q, {"df": date_from, "dt": date_to}).mappings().all()
    return {"points": [dict(r) for r in rows]}
