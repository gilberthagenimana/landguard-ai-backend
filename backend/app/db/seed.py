from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.owner import Owner
from app.models.ownership_history import OwnershipHistory
from app.models.parcel import Parcel
from app.models.role import Role
from app.models.transaction import Transaction
from app.models.user import User
from app.services.audit.service import record_audit

DEMO_NOTE = "DEMO/SYNTHETIC DATA - NOT OFFICIAL LAND RECORDS"

DEMO_ROLES = {
    "ADMIN": "Full system administration access.",
    "OFFICER": "Can verify transactions and manage review cases.",
    "AUDITOR": "Read-only access to verification data and audit records.",
}

DEMO_USERS = [
    {
        "username": "admin",
        "full_name": "Gilbert Godson",
        "email": "admin@landguard.local",
        "password": "AdminPass123!",
        "role": "ADMIN",
    },
    {
        "username": "officer",
        "full_name": "Marie Habyarimana",
        "email": "officer@landguard.local",
        "password": "OfficerPass123!",
        "role": "OFFICER",
    },
    {
        "username": "auditor",
        "full_name": "Patrick Uwizeye",
        "email": "auditor@landguard.local",
        "password": "AuditorPass123!",
        "role": "AUDITOR",
    },
]


def _ensure_roles(db: Session) -> dict[str, Role]:
    roles: dict[str, Role] = {}

    for name, description in DEMO_ROLES.items():
        role = db.query(Role).filter(Role.name == name).first()

        if role is None:
            role = Role(name=name, description=description)
            db.add(role)
            db.flush()
        else:
            role.description = description

        roles[name] = role

    return roles


def _create_demo_users(db: Session, roles: dict[str, Role]) -> dict[str, User]:
    users: dict[str, User] = {}

    for item in DEMO_USERS:
        user = db.query(User).filter(User.email == item["email"]).first()

        if user is None:
            user = User(
                username=item["username"],
                full_name=item["full_name"],
                email=item["email"],
                password_hash=hash_password(item["password"]),
                is_active=True,
                roles=[roles[item["role"]]],
            )
            db.add(user)
            db.flush()
        else:
            user.full_name = item["full_name"]
            user.is_active = True
            user.roles = [roles[item["role"]]]

        users[item["role"]] = user

    return users


def _create_demo_owners(db: Session) -> dict[str, Owner]:
    owners_data = [
        ("O-2291", "Jean Mugisha", "11995521-DEMO", "+250780000001", "jean.demo@example.invalid", "ACTIVE"),
        ("O-2292", "Alice Uwase", "11980073-DEMO", "+250780000002", "alice.demo@example.invalid", "ACTIVE"),
        ("O-2293", "Eric Nkurunziza", "11974412-DEMO", "+250780000003", "eric.demo@example.invalid", "ACTIVE"),
        ("O-2294", "Claudine Ingabire", "11968820-DEMO", "+250780000004", "claudine.demo@example.invalid", "ACTIVE"),
        ("O-2295", "Patrick Habimana", "11951150-DEMO", "+250780000005", "patrick.demo@example.invalid", "ACTIVE"),
        ("O-2296", "Solange Mukamana", "11946634-DEMO", "+250780000006", "solange.demo@example.invalid", "ACTIVE"),
        ("O-2297", "Diane Nsengimana", "11939901-DEMO", None, None, "ACTIVE"),
        ("O-2298", "Felix Byiringiro", "11928844-DEMO", None, None, "ACTIVE"),
        ("O-2299", "Grace Mutesi", "11917720-DEMO", None, None, "ACTIVE"),
        ("O-2300", "Thierry Uwimana", "11906611-DEMO", None, None, "ACTIVE"),
    ]

    owners: dict[str, Owner] = {}

    for code, name, identification, phone, email, status in owners_data:
        owner = db.query(Owner).filter(Owner.owner_code == code).first()

        if owner is None:
            owner = Owner(
                owner_code=code,
                full_name=name,
                identification_number=identification,
                phone=phone,
                email=email,
                status=status,
            )
            db.add(owner)
            db.flush()
        else:
            owner.full_name = name
            owner.status = status

        owners[code] = owner

    return owners


def _create_demo_parcels(db: Session) -> dict[str, Parcel]:
    parcels_data = [
        (
            "RW-10432",
            "Kicukiro / Niboye / Kagarama",
            "Kigali",
            "Kicukiro",
            "Niboye",
            "Kagarama",
            "Demo Village A",
            0.082,
            "ACTIVE",
            "DEMO-PARCEL-10432",
        ),
        (
            "RW-88213",
            "Gasabo / Remera / Nyabisindu",
            "Kigali",
            "Gasabo",
            "Remera",
            "Nyabisindu",
            "Demo Village B",
            0.115,
            "ACTIVE",
            "DEMO-PARCEL-88213",
        ),
        (
            "RW-20991",
            "Huye / Ngoma / Butare",
            "Southern",
            "Huye",
            "Ngoma",
            "Butare",
            "Demo Village C",
            0.064,
            "UNDER_REVIEW",
            "DEMO-PARCEL-20991",
        ),
        (
            "RW-33107",
            "Musanze / Muhoza / Amajyaruguru",
            "Northern",
            "Musanze",
            "Muhoza",
            "Amajyaruguru",
            "Demo Village D",
            0.099,
            "ACTIVE",
            "DEMO-PARCEL-33107",
        ),
        (
            "RW-55621",
            "Nyarugenge / Nyamirambo / Rugarama",
            "Kigali",
            "Nyarugenge",
            "Nyamirambo",
            "Rugarama",
            "Demo Village E",
            0.041,
            "ACTIVE",
            "DEMO-PARCEL-55621",
        ),
        (
            "RW-77890",
            "Rubavu / Gisenyi / Kivu",
            "Western",
            "Rubavu",
            "Gisenyi",
            "Kivu",
            "Demo Village F",
            0.142,
            "DISPUTED",
            "DEMO-PARCEL-77890",
        ),
    ]

    parcels: dict[str, Parcel] = {}

    for (
        code,
        location,
        province,
        district,
        sector,
        cell,
        village,
        area_ha,
        status,
        registration_reference,
    ) in parcels_data:
        parcel = db.query(Parcel).filter(Parcel.parcel_code == code).first()

        if parcel is None:
            parcel = Parcel(
                upi=f"DEMO-UPI-{code}",
                parcel_code=code,
                location=location,
                province=province,
                district=district,
                sector=sector,
                cell=cell,
                village=village,
                area_ha=area_ha,
                status=status,
                registration_reference=registration_reference,
            )
            db.add(parcel)
            db.flush()
        elif not parcel.upi:
            # Backfill only missing synthetic demo identifiers.
            parcel.upi = f"DEMO-UPI-{code}"
            db.flush()

        parcels[code] = parcel

    return parcels


def _create_demo_ownership_history(
    db: Session,
    owners: dict[str, Owner],
    parcels: dict[str, Parcel],
) -> None:
    existing_count = db.query(OwnershipHistory).count()

    if existing_count > 0:
        return

    now = datetime.utcnow()

    rows = [
        OwnershipHistory(
            parcel_id=parcels["RW-10432"].id,
            previous_owner_id=None,
            new_owner_id=owners["O-2291"].id,
            transfer_date=now - timedelta(days=2200),
            reason_type="FIRST_REGISTRATION",
            supporting_reference=DEMO_NOTE,
        ),
        OwnershipHistory(
            parcel_id=parcels["RW-88213"].id,
            previous_owner_id=None,
            new_owner_id=owners["O-2292"].id,
            transfer_date=now - timedelta(days=900),
            reason_type="FIRST_REGISTRATION",
            supporting_reference=DEMO_NOTE,
        ),
        OwnershipHistory(
            parcel_id=parcels["RW-20991"].id,
            previous_owner_id=None,
            new_owner_id=owners["O-2293"].id,
            transfer_date=now - timedelta(days=1100),
            reason_type="FIRST_REGISTRATION",
            supporting_reference=DEMO_NOTE,
        ),
        OwnershipHistory(
            parcel_id=parcels["RW-20991"].id,
            previous_owner_id=owners["O-2293"].id,
            new_owner_id=owners["O-2294"].id,
            transfer_date=now - timedelta(days=12),
            reason_type="SALE",
            supporting_reference=DEMO_NOTE,
        ),
        OwnershipHistory(
            parcel_id=parcels["RW-20991"].id,
            previous_owner_id=owners["O-2294"].id,
            new_owner_id=owners["O-2293"].id,
            transfer_date=now - timedelta(days=2),
            reason_type="CORRECTION",
            supporting_reference=DEMO_NOTE,
        ),
        OwnershipHistory(
            parcel_id=parcels["RW-33107"].id,
            previous_owner_id=None,
            new_owner_id=owners["O-2294"].id,
            transfer_date=now - timedelta(days=700),
            reason_type="FIRST_REGISTRATION",
            supporting_reference=DEMO_NOTE,
        ),
        OwnershipHistory(
            parcel_id=parcels["RW-55621"].id,
            previous_owner_id=None,
            new_owner_id=owners["O-2295"].id,
            transfer_date=now - timedelta(days=400),
            reason_type="FIRST_REGISTRATION",
            supporting_reference=DEMO_NOTE,
        ),
        OwnershipHistory(
            parcel_id=parcels["RW-77890"].id,
            previous_owner_id=None,
            new_owner_id=owners["O-2296"].id,
            transfer_date=now - timedelta(days=80),
            reason_type="FIRST_REGISTRATION",
            supporting_reference=DEMO_NOTE,
        ),
    ]

    db.add_all(rows)
    db.flush()


def _create_demo_transactions(
    db: Session,
    users: dict[str, User],
    owners: dict[str, Owner],
    parcels: dict[str, Parcel],
) -> None:
    if db.query(Transaction).count() > 0:
        return

    now = datetime.utcnow()
    transactions = [
        Transaction(
            transaction_code="TX-98231",
            parcel_id=parcels["RW-10432"].id,
            seller_owner_id=owners["O-2291"].id,
            buyer_owner_id=owners["O-2295"].id,
            transaction_type="SALE",
            transaction_date=now - timedelta(hours=6),
            declared_value=Decimal("18500000"),
            status="PENDING",
            created_by=users["OFFICER"].id,
        ),
        Transaction(
            transaction_code="TX-98237",
            parcel_id=parcels["RW-10432"].id,
            seller_owner_id=owners["O-2291"].id,
            buyer_owner_id=owners["O-2299"].id,
            transaction_type="SALE",
            transaction_date=now - timedelta(hours=2),
            declared_value=Decimal("19000000"),
            status="PENDING",
            created_by=users["OFFICER"].id,
        ),
    ]

    db.add_all(transactions)
    db.flush()




def seed_demo_data(db: Session) -> None:
    roles = _ensure_roles(db)
    users = _create_demo_users(db, roles)
    owners = _create_demo_owners(db)
    parcels = _create_demo_parcels(db)
    _create_demo_ownership_history(db, owners, parcels)
    _create_demo_transactions(db, users, owners, parcels)

    record_audit(
        db,
        action="SEED_DEMO_DATA",
        entity="System",
        entity_id="demo",
        user_id=users["ADMIN"].id,
        details=DEMO_NOTE,
    )

    db.commit()
