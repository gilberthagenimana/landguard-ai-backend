from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.case_review import CaseReview
from app.models.owner import Owner
from app.models.ownership_history import OwnershipHistory
from app.models.parcel import Parcel
from app.models.risk_prediction import RiskPrediction
from app.models.role import Role
from app.models.transaction import Transaction
from app.models.user import User
from app.services.audit.service import record_audit

DEMO_NOTE = "Synthetic demo record for academic testing. Not official Rwandan land data."


def seed_demo_data(db: Session) -> None:
    if db.query(User).first() is not None:
        return

    roles = {role.name: role for role in db.query(Role).all()}
    admin = User(
        username="admin",
        full_name="Gilbert Godson",
        email="admin@landguard.local",
        password_hash=hash_password("AdminPass123!"),
        is_active=True,
        roles=[roles["ADMIN"]],
    )
    officer = User(
        username="officer",
        full_name="Marie Habyarimana",
        email="officer@landguard.local",
        password_hash=hash_password("OfficerPass123!"),
        is_active=True,
        roles=[roles["OFFICER"]],
    )
    auditor = User(
        username="auditor",
        full_name="Patrick Uwizeye",
        email="auditor@landguard.local",
        password_hash=hash_password("AuditorPass123!"),
        is_active=True,
        roles=[roles["AUDITOR"]],
    )
    db.add_all([admin, officer, auditor])
    db.flush()

    owners = [
        Owner(owner_code="O-2291", full_name="Jean Mugisha", identification_number="11995521-DEMO", phone="+250780000001", email="jean.demo@example.invalid", status="ACTIVE"),
        Owner(owner_code="O-2292", full_name="Alice Uwase", identification_number="11980073-DEMO", phone="+250780000002", email="alice.demo@example.invalid", status="ACTIVE"),
        Owner(owner_code="O-2293", full_name="Eric Nkurunziza", identification_number="11974412-DEMO", phone="+250780000003", email="eric.demo@example.invalid", status="ACTIVE"),
        Owner(owner_code="O-2294", full_name="Claudine Ingabire", identification_number="11968820-DEMO", phone="+250780000004", email="claudine.demo@example.invalid", status="ACTIVE"),
        Owner(owner_code="O-2295", full_name="Patrick Habimana", identification_number="11951150-DEMO", phone="+250780000005", email="patrick.demo@example.invalid", status="INACTIVE"),
        Owner(owner_code="O-2296", full_name="Solange Mukamana", identification_number="11946634-DEMO", phone="+250780000006", email="solange.demo@example.invalid", status="ACTIVE"),
        Owner(owner_code="O-2297", full_name="Diane Nsengimana", identification_number="11939901-DEMO", status="ACTIVE"),
        Owner(owner_code="O-2298", full_name="Felix Byiringiro", identification_number="11928844-DEMO", status="ACTIVE"),
        Owner(owner_code="O-2299", full_name="Grace Mutesi", identification_number="11917720-DEMO", status="ACTIVE"),
        Owner(owner_code="O-2300", full_name="Thierry Uwimana", identification_number="11906611-DEMO", status="ACTIVE"),
    ]
    db.add_all(owners)
    db.flush()
    by_code = {owner.owner_code: owner for owner in owners}

    parcels = [
        Parcel(parcel_code="RW-10432", location="Kicukiro / Niboye / Kagarama", province="Kigali", district="Kicukiro", sector="Niboye", cell="Kagarama", village="Demo Village A", area_ha=0.082, status="ACTIVE", registration_reference="DEMO-PARCEL-10432"),
        Parcel(parcel_code="RW-88213", location="Gasabo / Remera / Nyabisindu", province="Kigali", district="Gasabo", sector="Remera", cell="Nyabisindu", village="Demo Village B", area_ha=0.115, status="ACTIVE", registration_reference="DEMO-PARCEL-88213"),
        Parcel(parcel_code="RW-20991", location="Huye / Ngoma / Butare", province="Southern", district="Huye", sector="Ngoma", cell="Butare", village="Demo Village C", area_ha=0.064, status="UNDER_REVIEW", registration_reference="DEMO-PARCEL-20991"),
        Parcel(parcel_code="RW-33107", location="Musanze / Muhoza / Amajyaruguru", province="Northern", district="Musanze", sector="Muhoza", cell="Amajyaruguru", village="Demo Village D", area_ha=0.099, status="ACTIVE", registration_reference="DEMO-PARCEL-33107"),
        Parcel(parcel_code="RW-55621", location="Nyarugenge / Nyamirambo / Rugarama", province="Kigali", district="Nyarugenge", sector="Nyamirambo", cell="Rugarama", village="Demo Village E", area_ha=0.041, status="ACTIVE", registration_reference="DEMO-PARCEL-55621"),
        Parcel(parcel_code="RW-77890", location="Rubavu / Gisenyi / Kivu", province="Western", district="Rubavu", sector="Gisenyi", cell="Kivu", village="Demo Village F", area_ha=0.142, status="DISPUTED", registration_reference="DEMO-PARCEL-77890"),
    ]
    db.add_all(parcels)
    db.flush()
    parcel_by_code = {parcel.parcel_code: parcel for parcel in parcels}

    now = datetime.utcnow()
    history_rows = [
        OwnershipHistory(parcel_id=parcel_by_code["RW-10432"].id, previous_owner_id=None, new_owner_id=by_code["O-2291"].id, transfer_date=now - timedelta(days=2200), reason_type="FIRST_REGISTRATION", supporting_reference=DEMO_NOTE),
        OwnershipHistory(parcel_id=parcel_by_code["RW-10432"].id, previous_owner_id=by_code["O-2291"].id, new_owner_id=by_code["O-2291"].id, transfer_date=now - timedelta(days=4), reason_type="CORRECTION", supporting_reference=DEMO_NOTE),
        OwnershipHistory(parcel_id=parcel_by_code["RW-88213"].id, previous_owner_id=None, new_owner_id=by_code["O-2292"].id, transfer_date=now - timedelta(days=900), reason_type="FIRST_REGISTRATION", supporting_reference=DEMO_NOTE),
        OwnershipHistory(parcel_id=parcel_by_code["RW-20991"].id, previous_owner_id=None, new_owner_id=by_code["O-2293"].id, transfer_date=now - timedelta(days=1100), reason_type="FIRST_REGISTRATION", supporting_reference=DEMO_NOTE),
        OwnershipHistory(parcel_id=parcel_by_code["RW-20991"].id, previous_owner_id=by_code["O-2293"].id, new_owner_id=by_code["O-2294"].id, transfer_date=now - timedelta(days=12), reason_type="SALE", supporting_reference=DEMO_NOTE),
        OwnershipHistory(parcel_id=parcel_by_code["RW-20991"].id, previous_owner_id=by_code["O-2294"].id, new_owner_id=by_code["O-2293"].id, transfer_date=now - timedelta(days=2), reason_type="CORRECTION", supporting_reference=DEMO_NOTE),
        OwnershipHistory(parcel_id=parcel_by_code["RW-33107"].id, previous_owner_id=None, new_owner_id=by_code["O-2294"].id, transfer_date=now - timedelta(days=700), reason_type="FIRST_REGISTRATION", supporting_reference=DEMO_NOTE),
        OwnershipHistory(parcel_id=parcel_by_code["RW-55621"].id, previous_owner_id=None, new_owner_id=by_code["O-2295"].id, transfer_date=now - timedelta(days=400), reason_type="FIRST_REGISTRATION", supporting_reference=DEMO_NOTE),
        OwnershipHistory(parcel_id=parcel_by_code["RW-77890"].id, previous_owner_id=None, new_owner_id=by_code["O-2296"].id, transfer_date=now - timedelta(days=80), reason_type="FIRST_REGISTRATION", supporting_reference=DEMO_NOTE),
    ]
    db.add_all(history_rows)
    db.flush()

    transactions = [
        Transaction(transaction_code="TX-98231", parcel_id=parcel_by_code["RW-10432"].id, seller_owner_id=by_code["O-2291"].id, buyer_owner_id=by_code["O-2297"].id, transaction_type="SALE", transaction_date=now - timedelta(days=4), declared_value=Decimal("18500000"), status="VERIFIED", created_by=officer.id),
        Transaction(transaction_code="TX-98232", parcel_id=parcel_by_code["RW-88213"].id, seller_owner_id=by_code["O-2292"].id, buyer_owner_id=by_code["O-2298"].id, transaction_type="SALE", transaction_date=now - timedelta(days=3), declared_value=Decimal("24000000"), status="UNDER_REVIEW", created_by=officer.id),
        Transaction(transaction_code="TX-98233", parcel_id=parcel_by_code["RW-20991"].id, seller_owner_id=by_code["O-2293"].id, buyer_owner_id=by_code["O-2299"].id, transaction_type="TRANSFER", transaction_date=now - timedelta(days=1), declared_value=Decimal("9700000"), status="UNDER_REVIEW", created_by=officer.id),
        Transaction(transaction_code="TX-98234", parcel_id=parcel_by_code["RW-33107"].id, seller_owner_id=by_code["O-2294"].id, buyer_owner_id=by_code["O-2297"].id, transaction_type="SALE", transaction_date=now - timedelta(days=6), declared_value=Decimal("15100000"), status="VERIFIED", created_by=officer.id),
        Transaction(transaction_code="TX-98235", parcel_id=parcel_by_code["RW-55621"].id, seller_owner_id=by_code["O-2295"].id, buyer_owner_id=by_code["O-2298"].id, transaction_type="INHERITANCE", transaction_date=now - timedelta(days=7), declared_value=Decimal("8200000"), status="UNDER_REVIEW", created_by=officer.id),
        Transaction(transaction_code="TX-98236", parcel_id=parcel_by_code["RW-77890"].id, seller_owner_id=by_code["O-2296"].id, buyer_owner_id=by_code["O-2300"].id, transaction_type="SALE", transaction_date=now - timedelta(hours=6), declared_value=Decimal("31000000"), status="PENDING", created_by=officer.id),
        Transaction(transaction_code="TX-98237", parcel_id=parcel_by_code["RW-10432"].id, seller_owner_id=by_code["O-2291"].id, buyer_owner_id=by_code["O-2299"].id, transaction_type="SALE", transaction_date=now - timedelta(hours=2), declared_value=Decimal("19000000"), status="PENDING", created_by=officer.id),
        Transaction(transaction_code="TX-98238", parcel_id=parcel_by_code["RW-20991"].id, seller_owner_id=by_code["O-2294"].id, buyer_owner_id=by_code["O-2300"].id, transaction_type="SALE", transaction_date=now - timedelta(hours=5), declared_value=Decimal("10100000"), status="PENDING", created_by=officer.id),
    ]
    db.add_all(transactions)
    db.flush()
    tx = {item.transaction_code: item for item in transactions}

    db.add_all(
        [
            RiskPrediction(transaction_id=tx["TX-98231"].id, risk_score=18, risk_level="LOW", model_version="random_forest-v1-synthetic", explanation="No elevated rule-based risk indicators were observed in the available records.", indicators=["No elevated rule-based risk indicators were observed in the available records."]),
            RiskPrediction(transaction_id=tx["TX-98232"].id, risk_score=48, risk_level="MEDIUM", model_version="random_forest-v1-synthetic", explanation="Further verification is recommended.", indicators=["Recent ownership change detected."]),
            RiskPrediction(transaction_id=tx["TX-98233"].id, risk_score=82, risk_level="HIGH", model_version="random_forest-v1-synthetic", explanation="Possible duplicate transaction detected. Recent ownership change detected.", indicators=["Possible duplicate transaction detected.", "Recent ownership change detected.", "Unusual transaction frequency detected."]),
            RiskPrediction(transaction_id=tx["TX-98236"].id, risk_score=76, risk_level="HIGH", model_version="random_forest-v1-synthetic", explanation="Risk indicators detected. Further verification is recommended.", indicators=["Possible duplicate transaction detected."]),
            RiskPrediction(transaction_id=tx["TX-98237"].id, risk_score=84, risk_level="HIGH", model_version="random_forest-v1-synthetic", explanation="Possible duplicate transaction detected.", indicators=["Possible duplicate transaction detected.", "Recent ownership change detected."]),
        ]
    )

    db.add_all(
        [
            CaseReview(case_code="CASE-0441", transaction_id=tx["TX-98233"].id, parcel_id=parcel_by_code["RW-20991"].id, assigned_to=officer.id, status="UNDER_REVIEW", review_notes="Demo case: recent ownership changes and a second pending sale. Review required."),
            CaseReview(case_code="CASE-0442", transaction_id=tx["TX-98236"].id, parcel_id=parcel_by_code["RW-77890"].id, assigned_to=None, status="OPEN", review_notes=None),
            CaseReview(case_code="CASE-0443", transaction_id=tx["TX-98232"].id, parcel_id=parcel_by_code["RW-88213"].id, assigned_to=officer.id, status="NEEDS_INFORMATION", review_notes="Request supporting documents from the submitting office."),
            CaseReview(case_code="CASE-0444", transaction_id=tx["TX-98235"].id, parcel_id=parcel_by_code["RW-55621"].id, assigned_to=auditor.id, status="UNDER_REVIEW", review_notes="Seller account is inactive in demo records."),
            CaseReview(case_code="CASE-0445", transaction_id=tx["TX-98237"].id, parcel_id=parcel_by_code["RW-10432"].id, assigned_to=officer.id, status="OPEN", review_notes="Possible duplicate of TX-98231 for the same parcel."),
        ]
    )

    record_audit(db, action="SEED_DEMO_DATA", entity="System", entity_id="demo", user_id=admin.id, details=DEMO_NOTE)
    record_audit(db, action="LOGIN", entity="User", entity_id=str(officer.id), user_id=officer.id, details="Seeded historical login for demonstration.")
    db.commit()
