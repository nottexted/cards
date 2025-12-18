from __future__ import annotations

import random
import re
import string
import uuid
from datetime import date, datetime, timedelta
from typing import Iterable

from sqlalchemy.orm import Session

from .db import SessionLocal
from . import models

_RU2EN = {
    "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh","з":"z","и":"i","й":"y","к":"k","л":"l","м":"m",
    "н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f","х":"h","ц":"ts","ч":"ch","ш":"sh","щ":"sch",
    "ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya",
}

def _exists(db: Session, model) -> bool:
    return db.query(model).first() is not None


def _count(db: Session, model) -> int:
    return int(db.query(model).count())


def _get_status_id(db: Session, entity_type: str, code: str) -> int:
    s = (
        db.query(models.RefStatus)
        .filter(models.RefStatus.entity_type == entity_type, models.RefStatus.code == code)
        .one()
    )
    return int(s.id)


def _ensure_statuses(db: Session) -> None:
    # entity_type: application / batch / card
    rows = [
        ("application", "NEW", "Новая", 10),
        ("application", "IN_REVIEW", "На проверке", 20),
        ("application", "APPROVED", "Одобрена", 30),
        ("application", "REJECTED", "Отказ", 40),
        ("application", "IN_BATCH", "В партии", 50),
        ("batch", "CREATED", "Создана", 10),
        ("batch", "SENT", "Отправлена", 20),
        ("batch", "RECEIVED", "Получена", 30),
        ("card", "CREATED", "Карта создана", 10),
        ("card", "ISSUED", "Выпущена", 20),
        ("card", "DELIVERED", "Доставлена", 30),
        ("card", "HANDED", "Выдана клиенту", 40),
        ("card", "ACTIVATED", "Активирована", 50),
        ("card", "CLOSED", "Закрыта", 60),
    ]
    for entity_type, code, name, sort_order in rows:
        ex = (
            db.query(models.RefStatus)
            .filter(models.RefStatus.entity_type == entity_type, models.RefStatus.code == code)
            .first()
        )
        if ex:
            ex.name = name
            ex.sort_order = sort_order
        else:
            db.add(models.RefStatus(entity_type=entity_type, code=code, name=name, sort_order=sort_order))
    db.commit()


def _ensure_reject_reasons(db: Session) -> None:
    if _exists(db, models.RefRejectReason):
        return
    db.add_all(
        [
            models.RefRejectReason(code="KYC_FAIL", name="Не пройдена проверка (KYC/AML)"),
            models.RefRejectReason(code="DUPLICATE", name="Дубликат заявки/клиента"),
            models.RefRejectReason(code="LIMITS", name="Не соответствует требованиям/лимитам"),
            models.RefRejectReason(code="FRAUD", name="Признаки мошенничества"),
            models.RefRejectReason(code="OTHER", name="Иная причина"),
        ]
    )
    db.commit()


def _ensure_branches(db: Session) -> None:
    if _exists(db, models.RefBranch):
        return
    cities = [
        ("Москва", "Центральный офис"),
        ("Санкт-Петербург", "Невский офис"),
        ("Екатеринбург", "Центр"),
        ("Новосибирск", "Площадь Ленина"),
        ("Казань", "Кремлёвская"),
        ("Нижний Новгород", "Оперный"),
        ("Пермь", "Комсомольский"),
        ("Самара", "Набережная"),
    ]
    rows = []
    for i, (city, name) in enumerate(cities[: random.randint(6, 8)], start=1):
        rows.append(
            models.RefBranch(
                code=f"BR{i:02d}",
                name=name,
                city=city,
                address=f"{city}, ул. {random.choice(['Ленина', 'Мира', 'Советская', 'Пушкина', 'Космонавтов'])}, д. {random.randint(1, 200)}",
                phone=f"+7 495 {random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(10, 99)}",
                is_active=True,
            )
        )
    db.add_all(rows)
    db.commit()


def _ensure_channels(db: Session) -> None:
    if _exists(db, models.RefChannel):
        return
    db.add_all(
        [
            models.RefChannel(code="BRANCH", name="Отделение", is_active=True),
            models.RefChannel(code="ONLINE", name="Онлайн", is_active=True),
            models.RefChannel(code="CALL", name="Колл-центр", is_active=True),
            models.RefChannel(code="PARTNER", name="Партнёр", is_active=True),
        ]
    )
    db.commit()


def _ensure_delivery_methods(db: Session) -> None:
    if _exists(db, models.RefDeliveryMethod):
        return
    db.add_all(
        [
            models.RefDeliveryMethod(code="PICKUP", name="Самовывоз", is_active=True),
            models.RefDeliveryMethod(code="COURIER", name="Курьер", is_active=True),
            models.RefDeliveryMethod(code="POST", name="Почта России", is_active=True),
        ]
    )
    db.commit()


def _ensure_vendors(db: Session) -> None:
    if _exists(db, models.RefVendor):
        return
    db.add_all(
        [
            models.RefVendor(vendor_type="manufacturer", name="АО 'Пластик-Карт'", contacts="sales@plastic-card.example", sla_days=3, is_active=True),
            models.RefVendor(vendor_type="manufacturer", name="ООО 'Гознак Сервис'", contacts="support@goznak-service.example", sla_days=4, is_active=True),
            models.RefVendor(vendor_type="manufacturer", name="SecureCard Manufacturing", contacts="ops@securecard.example", sla_days=5, is_active=True),
            models.RefVendor(vendor_type="courier", name="СДЭК", contacts="cdek@logistics.example", sla_days=2, is_active=True),
            models.RefVendor(vendor_type="courier", name="DPD", contacts="dpd@logistics.example", sla_days=3, is_active=True),
        ]
    )
    db.commit()


def _ensure_products(db: Session) -> None:
    if _exists(db, models.RefCardProduct):
        return
    db.add_all(
        [
            models.RefCardProduct(code="MIR_CLASSIC", name="МИР Classic", payment_system="МИР", level="Classic", currency="RUB", term_months=36, is_virtual=False, is_active=True),
            models.RefCardProduct(code="MIR_GOLD", name="МИР Gold", payment_system="МИР", level="Gold", currency="RUB", term_months=36, is_virtual=False, is_active=True),
            models.RefCardProduct(code="MIR_VIRTUAL", name="МИР Virtual", payment_system="МИР", level="Virtual", currency="RUB", term_months=24, is_virtual=True, is_active=True),
            models.RefCardProduct(code="MC_WORLDELITE", name="Mastercard World Elite", payment_system="Mastercard", level="World Elite", currency="RUB", term_months=36, is_virtual=False, is_active=True),
        ]
    )
    db.commit()


def _ensure_tariffs(db: Session) -> None:
    if _exists(db, models.RefTariffPlan):
        return
    db.add_all(
        [
            models.RefTariffPlan(
                code="BASE",
                name="Базовый",
                issue_fee=0,
                monthly_fee=0,
                delivery_subsidy=0,
                free_condition_text="Без обслуживания при использовании",
                limits_json={"cash_withdrawal_day": 100000, "purchases_month": 500000},
                is_active=True,
            ),
            models.RefTariffPlan(
                code="PLUS",
                name="Плюс",
                issue_fee=0,
                monthly_fee=199,
                delivery_subsidy=0,
                free_condition_text="Бесплатно при покупках от 10 000 ₽/мес",
                limits_json={"cash_withdrawal_day": 150000, "purchases_month": 800000},
                is_active=True,
            ),
            models.RefTariffPlan(
                code="PREM",
                name="Премиум",
                issue_fee=0,
                monthly_fee=999,
                delivery_subsidy=0,
                free_condition_text="Бесплатно при остатке от 200 000 ₽",
                limits_json={"cash_withdrawal_day": 300000, "purchases_month": 2000000},
                is_active=True,
            ),
        ]
    )
    db.commit()


def _rand_phone() -> str:
    return f"+7 9{random.randint(10,99)} {random.randint(100,999)}-{random.randint(10,99)}-{random.randint(10,99)}"

def _translit_ru(s: str) -> str:
    out = []
    for ch in s.lower():
        if ch in _RU2EN:
            out.append(_RU2EN[ch])
        else:
            out.append(ch)
    return "".join(out)

def _slug_latin(s: str) -> str:
    s = _translit_ru(s)
    s = s.replace(" ", ".").replace("'", "").replace("`", "")
    # keep only ascii letters/digits/dot/underscore/hyphen
    allowed = set(string.ascii_lowercase + string.digits + "._-")
    s = "".join(ch for ch in s if ch in allowed)
    s = re.sub(r"\.+", ".", s).strip(".")
    return s or f"user{random.randint(1000,9999)}"

def _email_is_ascii(email: str) -> bool:
    # allow typical email chars
    return bool(re.fullmatch(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$", email))



def _rand_email(full_name: str, used: set[str] | None = None) -> str:
    slug = _slug_latin(full_name)
    used = used or set()
    for _ in range(20):
        cand = f"{slug}.{random.randint(10,99)}@mail.ru"
        if cand not in used:
            used.add(cand)
            return cand
    # fallback
    cand = f"{slug}.{random.randint(100,999)}@mail.ru"
    used.add(cand)
    return cand


def _passport() -> str:
    series = random.randint(1000, 9999)
    number = random.randint(100000, 999999)
    return f"{series:04d} {number:06d}"


def _issuer(city: str) -> str:
    base = random.choice(["ГУ МВД России", "УМВД России", "ОВД", "УФМС"])
    tail = random.choice(["по району", "по городу", "по области", "по округу"])
    return f"{base} {tail} {city}"


def _address(city: str) -> str:
    street = random.choice(["Ленина", "Мира", "Советская", "Пушкина", "Космонавтов", "Гагарина", "Набережная"])
    prefix = random.choice(["ул.", "пр-т", "пер."])
    return f"{city}, {prefix} {street}, д. {random.randint(1, 220)}, кв. {random.randint(1, 180)}"


def _ensure_clients(db: Session, target: int = 18) -> None:
    cur = _count(db, models.Client)
    if cur >= target:
        return

    last_names_m = ["Иванов", "Петров", "Сидоров", "Морозов", "Кузнецов", "Орлов", "Глазунов", "Смирнов", "Волков", "Егоров"]
    last_names_f = ["Иванова", "Петрова", "Сидорова", "Морозова", "Кузнецова", "Орлова", "Глазунова", "Смирнова", "Волкова", "Егорова"]
    first_m = ["Иван", "Пётр", "Максим", "Андрей", "Владимир", "Дмитрий", "Егор", "Константин", "Никита", "Алексей"]
    first_f = ["Мария", "Анна", "Екатерина", "Ольга", "Наталья", "Татьяна", "Алина", "Ксения", "Юлия", "Ирина"]
    middle_m = ["Иванович", "Петрович", "Андреевич", "Владимирович", "Дмитриевич", "Сергеевич", "Алексеевич", "Николаевич"]
    middle_f = ["Ивановна", "Петровна", "Андреевна", "Владимировна", "Дмитриевна", "Сергеевна", "Алексеевна", "Николаевна"]

    cities = ["Москва", "Санкт-Петербург", "Екатеринбург", "Новосибирск", "Казань", "Нижний Новгород", "Пермь", "Самара"]

    segments = ["Mass", "Affluent", "Premium"]

    used_emails = set(e for (e,) in db.query(models.Client.email).filter(models.Client.email.isnot(None)).all() if e)
    kyc = ["new", "verified", "failed"]
    risks = ["low", "medium", "high"]

    for _ in range(target - cur):
        is_f = random.random() < 0.45
        city = random.choice(cities)
        if is_f:
            full = f"{random.choice(last_names_f)} {random.choice(first_f)} {random.choice(middle_f)}"
            gender = "F"
        else:
            full = f"{random.choice(last_names_m)} {random.choice(first_m)} {random.choice(middle_m)}"
            gender = "M"

        bd = date(random.randint(1965, 2005), random.randint(1, 12), random.randint(1, 28))
        doc_num = _passport()
        issuer = _issuer(city)
        reg = _address(city)
        fact = _address(city) if random.random() < 0.6 else reg

        c = models.Client(
            id=uuid.uuid4(),
            client_type="person",
            full_name=full,
            phone=_rand_phone(),
            email=_rand_email(full, used_emails),
            birth_date=bd,
            gender=gender,
            citizenship="RU",
            doc_type="Паспорт",
            doc_number=doc_num,
            doc_issue_date=date(min(bd.year + 20, 2020), random.randint(1, 12), random.randint(1, 28)),
            doc_issuer=issuer,
            reg_address=reg,
            fact_address=fact,
            segment=random.choice(segments),
            kyc_status=random.choice(kyc),
            risk_level=random.choice(risks),
            note=random.choice([None, "VIP", "salary project", ""]),
        )
        db.add(c)

    db.commit()


def _backfill_clients_profile(db: Session) -> None:
    cities = ["Москва", "Санкт-Петербург", "Екатеринбург", "Новосибирск", "Казань", "Нижний Новгород", "Пермь", "Самара"]

    used_emails = set(e for (e,) in db.query(models.Client.email).filter(models.Client.email.isnot(None)).all() if e)

    rows = db.query(models.Client).all()
    changed = False

    for c in rows:
        city = random.choice(cities)

        if not c.reg_address or str(c.reg_address).strip() == "":
            c.reg_address = _address(city)
            changed = True

        if not c.fact_address or str(c.fact_address).strip() == "":
            c.fact_address = _address(city)
            changed = True

        if not c.doc_issuer or str(c.doc_issuer).strip() == "":
            c.doc_issuer = _issuer(city)
            changed = True

        # email: make sure it's ascii; if missing or contains non-ascii -> regenerate from name
        if not c.email or str(c.email).strip() == "":
            c.email = _rand_email(c.full_name, used_emails)
            changed = True
        else:
            em = str(c.email).strip()
            if not _email_is_ascii(em):
                c.email = _rand_email(c.full_name, used_emails)
                changed = True

    if changed:
        db.commit()


def _ensure_applications(db: Session, target: int = 60) -> None:
    cur = _count(db, models.CardApplication)
    if cur >= target:
        return

    clients = db.query(models.Client).all()
    products = db.query(models.RefCardProduct).all()
    tariffs = db.query(models.RefTariffPlan).all()
    channels = db.query(models.RefChannel).all()
    branches = db.query(models.RefBranch).all()
    delivery = db.query(models.RefDeliveryMethod).all()
    reject_reasons = db.query(models.RefRejectReason).all()

    if not (clients and products and tariffs and channels and branches and delivery):
        return

    year = datetime.utcnow().year
    start_seq = cur + 1

    # distribution for statuses
    statuses = [
        ("NEW", 0.20),
        ("IN_REVIEW", 0.15),
        ("APPROVED", 0.35),
        ("REJECTED", 0.20),
        ("IN_BATCH", 0.10),  # will be reconciled later when batches created
    ]

    def pick_status() -> str:
        r = random.random()
        acc = 0.0
        for code, w in statuses:
            acc += w
            if r <= acc:
                return code
        return "APPROVED"

    now = datetime.utcnow()
    for i in range(target - cur):
        client = random.choice(clients)
        product = random.choice(products)
        tariff = random.choice(tariffs)
        ch = random.choice(channels)
        br = random.choice(branches)
        dm = random.choice(delivery)

        created = now - timedelta(days=random.randint(0, 89), hours=random.randint(0, 23), minutes=random.randint(0, 59))
        req_deliv = (created.date() + timedelta(days=random.randint(2, 15))) if random.random() < 0.5 else None

        status_code = pick_status()
        status_id = _get_status_id(db, "application", status_code)

        app = models.CardApplication(
            id=uuid.uuid4(),
            application_no=f"APP-{year}-{start_seq + i:06d}",
            client_id=client.id,
            product_id=product.id,
            tariff_id=tariff.id,
            channel_id=ch.id,
            branch_id=br.id,
            delivery_method_id=dm.id,
            delivery_address=_address(br.city) if dm.code != "PICKUP" else None,
            delivery_comment=random.choice([None, "Позвонить за 1 час", "Охрана, пропуск на стойке", ""]),
            embossing_name=" ".join(client.full_name.split()[:2]).upper()[:22],
            is_salary_project=random.random() < 0.2,
            requested_at=created,
            requested_delivery_date=req_deliv,
            planned_issue_date=(created.date() + timedelta(days=random.randint(3, 12))) if status_code in {"APPROVED", "IN_BATCH"} else None,
            status_id=status_id,
            priority=random.choice(["low", "normal", "high"]),
            limits_requested_json={"atm_day": random.choice([50000, 100000, 150000]), "purchases_month": random.choice([300000, 500000, 800000])},
            consent_personal_data=True,
            consent_marketing=random.random() < 0.3,
            comment=random.choice([None, "Клиент просит доставку в выходной", "Повышенный приоритет", ""]),
        )

        # decision fields
        if status_code in {"APPROVED", "REJECTED", "IN_BATCH"}:
            app.decision_at = created + timedelta(hours=random.randint(1, 48))
            app.decision_by = random.choice(["KYC Bot", "Оператор 1", "Оператор 2"])
            app.kyc_score = random.randint(30, 95)
            app.kyc_result = "pass" if status_code != "REJECTED" else "fail"
            app.kyc_notes = random.choice([None, "ok", "manual review", "matchlist check"])
        if status_code == "REJECTED":
            app.reject_reason_id = random.choice(reject_reasons).id if reject_reasons else None

        db.add(app)

    db.commit()


def _ensure_batches_and_cards(db: Session, batches_target: int = 4) -> None:
    # Ensure batches
    batches = db.query(models.IssueBatch).all()
    vendors = db.query(models.RefVendor).all()
    year = datetime.utcnow().year

    if not vendors:
        return

    if len(batches) < batches_target:
        start_seq = len(batches) + 1
        for i in range(batches_target - len(batches)):
            vendor = random.choice(vendors)
            status_code = random.choice(["CREATED", "SENT", "RECEIVED"])
            status_id = _get_status_id(db, "batch", status_code)
            created = datetime.utcnow() - timedelta(days=random.randint(0, 20))
            planned = created + timedelta(days=random.randint(1, 5))
            sent = planned + timedelta(hours=random.randint(2, 20)) if status_code in {"SENT", "RECEIVED"} else None
            received = sent + timedelta(days=random.randint(1, 4)) if status_code == "RECEIVED" else None

            b = models.IssueBatch(
                id=uuid.uuid4(),
                batch_no=f"BAT-{year}-{start_seq + i:06d}",
                vendor_id=vendor.id,
                status_id=status_id,
                planned_send_at=planned,
                sent_at=sent,
                received_at=received,
            )
            db.add(b)
        db.commit()

    batches = db.query(models.IssueBatch).all()

    # Select approved applications not yet in any batch
    approved_id = _get_status_id(db, "application", "APPROVED")
    in_batch_id = _get_status_id(db, "application", "IN_BATCH")

    approved_apps = (
        db.query(models.CardApplication)
        .filter(models.CardApplication.status_id == approved_id)
        .order_by(models.CardApplication.requested_at.desc())
        .all()
    )

    # Add some approved apps into batches
    per_batch = max(2, min(8, len(approved_apps) // max(1, len(batches))))
    take = min(len(approved_apps), per_batch * len(batches))

    used = 0
    for b in batches:
        for a in approved_apps[used : used + per_batch]:
            # ensure unique application_id in IssueBatchItem
            if db.query(models.IssueBatchItem).filter(models.IssueBatchItem.application_id == a.id).first():
                continue
            it = models.IssueBatchItem(
                id=uuid.uuid4(),
                batch_id=b.id,
                application_id=a.id,
                produced_at=(b.sent_at or b.planned_send_at or datetime.utcnow()) + timedelta(hours=random.randint(1, 24)),
                delivered_to_branch_at=(b.received_at or datetime.utcnow()) + timedelta(hours=random.randint(4, 48))
                if random.random() < 0.7
                else None,
            )
            a.status_id = in_batch_id
            db.add(it)
        used += per_batch
        if used >= take:
            break
    db.commit()

    # Cards: create for part of applications (some may still be NEW/IN_REVIEW/REJECTED without cards)
    card_count = _count(db, models.Card)
    start_seq = card_count + 1

    apps_for_cards = (
        db.query(models.CardApplication)
        .filter(models.CardApplication.status_id.in_([in_batch_id, approved_id]))
        .order_by(models.CardApplication.requested_at.desc())
        .limit(30)
        .all()
    )

    # status ids for cards
    c_created = _get_status_id(db, "card", "CREATED")
    c_issued = _get_status_id(db, "card", "ISSUED")
    c_deliv = _get_status_id(db, "card", "DELIVERED")
    c_handed = _get_status_id(db, "card", "HANDED")
    c_activated = _get_status_id(db, "card", "ACTIVATED")

    channels = db.query(models.RefChannel).all()
    act_ch = random.choice(channels).id if channels else None

    def pan_mask() -> str:
        return f"{random.choice([4276, 5469, 2200])} **** **** {random.randint(1000,9999)}"

    for i, a in enumerate(apps_for_cards):
        if db.query(models.Card).filter(models.Card.application_id == a.id).first():
            continue

        stage = random.choices(
            population=["CREATED", "ISSUED", "DELIVERED", "HANDED", "ACTIVATED"],
            weights=[0.15, 0.20, 0.20, 0.20, 0.25],
            k=1,
        )[0]

        base = a.requested_at + timedelta(days=random.randint(1, 10))
        issued_at = base if stage in {"ISSUED", "DELIVERED", "HANDED", "ACTIVATED"} else None
        delivered_at = (issued_at + timedelta(days=random.randint(1, 4))) if stage in {"DELIVERED", "HANDED", "ACTIVATED"} else None
        handed_at = (delivered_at + timedelta(days=random.randint(0, 3))) if stage in {"HANDED", "ACTIVATED"} else None
        activated_at = (handed_at + timedelta(hours=random.randint(1, 72))) if stage == "ACTIVATED" else None

        status_id = {
            "CREATED": c_created,
            "ISSUED": c_issued,
            "DELIVERED": c_deliv,
            "HANDED": c_handed,
            "ACTIVATED": c_activated,
        }[stage]

        expiry = datetime.utcnow().date().replace(year=datetime.utcnow().year + 3)
        c = models.Card(
            id=uuid.uuid4(),
            card_no=f"CARD-{year}-{start_seq + i:06d}",
            application_id=a.id,
            status_id=status_id,
            pan_masked=pan_mask() if stage != "CREATED" else None,
            expiry_month=random.randint(1, 12) if stage != "CREATED" else None,
            expiry_year=expiry.year if stage != "CREATED" else None,
            issued_at=issued_at,
            delivered_at=delivered_at,
            handed_at=handed_at,
            activated_at=activated_at,
            activation_channel_id=act_ch if activated_at else None,
            note=random.choice([None, "Без пин-конверта", "Доставка в офис", ""]),
        )
        db.add(c)

    db.commit()


def seed() -> None:
    random.seed(42)
    with SessionLocal() as db:
        _ensure_statuses(db)
        _ensure_reject_reasons(db)
        _ensure_branches(db)
        _ensure_channels(db)
        _ensure_delivery_methods(db)
        _ensure_vendors(db)
        _ensure_products(db)
        _ensure_tariffs(db)

        _ensure_clients(db, target=25)
        _backfill_clients_profile(db)

        _ensure_applications(db, target=80)
        _ensure_batches_and_cards(db, batches_target=7)


if __name__ == "__main__":
    seed()
