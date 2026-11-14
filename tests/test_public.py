from conftest import (
    TestingSessionLocal,
    create_test_owner,
    create_test_parcel,
    create_test_transaction,
)


def test_public_lookup_labels_demo_parcel(client):
    db = TestingSessionLocal()
    try:
        parcel = create_test_parcel(
            db,
            parcel_code="RW-PUBLIC-DEMO",
            upi="DEMO-UPI-RW-PUBLIC-DEMO",
            registration_reference="DEMO-PARCEL-RW-PUBLIC-DEMO",
        )
        upi = parcel.upi
    finally:
        db.close()

    response = client.get(f"/api/public/parcels/{upi}")

    assert response.status_code == 200
    data = response.json()
    assert data["record_classification"] == "DEMO_SYNTHETIC"
    assert data["official_verification"] == "NOT_INDEPENDENTLY_VERIFIED"
    assert "not an official land registry record" in data["public_notice"].lower()


def test_public_lookup_labels_other_records_unverified(client):
    db = TestingSessionLocal()
    try:
        parcel = create_test_parcel(
            db,
            parcel_code="RW-PUBLIC-LOCAL",
            upi="UPI-LOCAL-001",
            registration_reference="LOCAL-REG-001",
        )
        upi = parcel.upi
    finally:
        db.close()

    response = client.get(f"/api/public/parcels/{upi}")

    assert response.status_code == 200
    data = response.json()
    assert data["record_classification"] == "UNVERIFIED_LOCAL_RECORD"
    assert data["official_verification"] == "NOT_INDEPENDENTLY_VERIFIED"


def test_public_lookup_warns_about_pending_transaction(client):
    db = TestingSessionLocal()
    try:
        parcel = create_test_parcel(
            db,
            parcel_code="RW-PUBLIC-PENDING",
            upi="DEMO-UPI-RW-PUBLIC-PENDING",
        )
        seller = create_test_owner(
            db,
            owner_code="OWN-PUBLIC-SELLER",
        )
        buyer = create_test_owner(
            db,
            owner_code="OWN-PUBLIC-BUYER",
            email="public-buyer@test.local",
            identification_number="11995522-DEMO",
            phone="+250780000002",
        )
        create_test_transaction(
            db,
            parcel_id=parcel.id,
            seller_id=seller.id,
            buyer_id=buyer.id,
            transaction_code="TX-PUBLIC-PENDING",
            status="PENDING",
        )
        upi = parcel.upi
    finally:
        db.close()

    response = client.get(f"/api/public/parcels/{upi}")

    assert response.status_code == 200
    data = response.json()
    assert data["has_pending_transaction"] is True
    assert data["warning_message"]
    assert "pending" in data["warning_message"].lower()
    assert data["official_verification"] == "NOT_INDEPENDENTLY_VERIFIED"


def test_public_lookup_returns_404_for_unknown_upi(client):
    response = client.get("/api/public/parcels/DEMO-UPI-NOT-FOUND")

    assert response.status_code == 404


def test_public_lookup_by_parcel_code_preserves_existing_upi_lookup(client):
    db = TestingSessionLocal()
    try:
        parcel = create_test_parcel(
            db,
            parcel_code="RW-PUBLIC-BY-CODE",
            upi="UPI-PUBLIC-BY-CODE",
        )
        upi = parcel.upi
    finally:
        db.close()

    upi_response = client.get(f"/api/public/parcels/{upi}")
    code_response = client.get("/api/public/parcels/by-code/RW-PUBLIC-BY-CODE")

    assert upi_response.status_code == 200
    assert code_response.status_code == 200
    assert code_response.json()["upi"] == "UPI-PUBLIC-BY-CODE"
    assert code_response.json()["parcel_code"] == "RW-PUBLIC-BY-CODE"
    assert set(code_response.json()) == set(upi_response.json())


def test_public_lookup_by_parcel_code_supports_null_upi(client):
    db = TestingSessionLocal()
    try:
        create_test_parcel(
            db,
            parcel_code="RW-PUBLIC-NULL-UPI",
            upi=None,
        )
    finally:
        db.close()

    response = client.get("/api/public/parcels/by-code/RW-PUBLIC-NULL-UPI")

    assert response.status_code == 200
    data = response.json()
    assert data["upi"] is None
    assert data["parcel_code"] == "RW-PUBLIC-NULL-UPI"
    assert not {"identification_number", "email", "phone", "audit_metadata", "investigation_notes"} & set(data)


def test_public_lookup_by_unknown_parcel_code_returns_404(client):
    response = client.get("/api/public/parcels/by-code/RW-PUBLIC-NOT-FOUND")
    assert response.status_code == 404


def test_public_response_schema_accepts_null_upi():
    from app.schemas.domain import PublicParcelOut

    response = PublicParcelOut(
        upi=None,
        parcel_code="RW-NULL-UPI-PUBLIC",
        location="Kigali",
        district="Gasabo",
        status="ACTIVE",
    )
    assert response.upi is None
