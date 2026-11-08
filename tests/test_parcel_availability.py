"""Parcel availability and transaction status synchronization tests."""
from datetime import datetime

from conftest import (
    TestingSessionLocal,
    create_ownership_history,
    create_test_owner,
    create_test_parcel,
    create_test_transaction,
    make_admin_token,
    make_officer_token,
)


def _lookup(client, upi):
    response = client.get(f"/api/public/parcels/{upi}")
    assert response.status_code == 200, response.text
    return response.json()


def _seed_parcel(db, *, parcel_code: str, upi: str, status: str = "ACTIVE"):
    return create_test_parcel(db, parcel_code=parcel_code, upi=upi, status=status)


def test_available_parcel_without_transactions_is_available(client):
    db = TestingSessionLocal()
    parcel = _seed_parcel(db, parcel_code="RW-AVAIL-BASE", upi="DEMO-UPI-RW-AVAIL-BASE")
    upi = parcel.upi
    db.close()

    data = _lookup(client, upi)
    assert data["availability"] == "AVAILABLE"
    assert data["has_pending_transaction"] is False
    assert data["transaction_status"] is None
    assert data["warning_message"] is None


def test_pending_transaction_makes_parcel_unavailable(client):
    db = TestingSessionLocal()
    parcel = _seed_parcel(db, parcel_code="RW-AVAIL-PENDING", upi="DEMO-UPI-RW-AVAIL-PENDING")
    seller = create_test_owner(db, owner_code="OWN-AVAIL-SELLER", full_name="Availability Seller")
    buyer = create_test_owner(db, owner_code="OWN-AVAIL-BUYER", full_name="Availability Buyer", email="avail-buyer@test.local", identification_number="11995522-DEMO", phone="+250780000002")
    create_test_transaction(db, parcel_id=parcel.id, seller_id=seller.id, buyer_id=buyer.id, transaction_code="TX-AVAIL-PENDING", status="PENDING_REVIEW")
    upi = parcel.upi
    db.close()

    data = _lookup(client, upi)
    assert data["availability"] == "UNAVAILABLE"
    assert data["has_pending_transaction"] is True
    assert data["transaction_status"] == "PENDING_REVIEW"
    assert "NOT AVAILABLE FOR ANOTHER SALE" in (data["warning_message"] or "")


def test_under_review_transaction_keeps_parcel_unavailable(client):
    db = TestingSessionLocal()
    parcel = _seed_parcel(db, parcel_code="RW-AVAIL-REVIEW", upi="DEMO-UPI-RW-AVAIL-REVIEW")
    seller = create_test_owner(db, owner_code="OWN-AVAIL-SELLER-2", full_name="Availability Seller Two")
    buyer = create_test_owner(db, owner_code="OWN-AVAIL-BUYER-2", full_name="Availability Buyer Two", email="avail-buyer2@test.local", identification_number="11995522-DEMO2", phone="+250780000003")
    create_test_transaction(db, parcel_id=parcel.id, seller_id=seller.id, buyer_id=buyer.id, transaction_code="TX-AVAIL-REVIEW", status="UNDER_REVIEW")
    upi = parcel.upi
    db.close()

    data = _lookup(client, upi)
    assert data["availability"] == "UNAVAILABLE"
    assert data["has_pending_transaction"] is True
    assert data["transaction_status"] == "UNDER_REVIEW"
    assert "UNDER REVIEW — OWNERSHIP TRANSFER NOT YET CONFIRMED" in (data["warning_message"] or "")


def test_verified_transaction_keeps_parcel_unavailable(client):
    db = TestingSessionLocal()
    parcel = _seed_parcel(db, parcel_code="RW-AVAIL-VERIFIED", upi="DEMO-UPI-RW-AVAIL-VERIFIED")
    seller = create_test_owner(db, owner_code="OWN-AVAIL-SELLER-3", full_name="Availability Seller Three")
    buyer = create_test_owner(db, owner_code="OWN-AVAIL-BUYER-3", full_name="Availability Buyer Three", email="avail-buyer3@test.local", identification_number="11995522-DEMO3", phone="+250780000004")
    create_test_transaction(db, parcel_id=parcel.id, seller_id=seller.id, buyer_id=buyer.id, transaction_code="TX-AVAIL-VERIFIED", status="VERIFIED")
    upi = parcel.upi
    db.close()

    data = _lookup(client, upi)
    assert data["availability"] == "UNAVAILABLE"
    assert data["has_pending_transaction"] is True
    assert data["transaction_status"] == "VERIFIED"
    assert "OWNERSHIP TRANSFER PENDING CONFIRMATION" in (data["warning_message"] or "")


def test_flagged_transaction_restricts_parcel(client):
    db = TestingSessionLocal()
    parcel = _seed_parcel(db, parcel_code="RW-AVAIL-FLAGGED", upi="DEMO-UPI-RW-AVAIL-FLAGGED")
    seller = create_test_owner(db, owner_code="OWN-AVAIL-SELLER-4", full_name="Availability Seller Four")
    buyer = create_test_owner(db, owner_code="OWN-AVAIL-BUYER-4", full_name="Availability Buyer Four", email="avail-buyer4@test.local", identification_number="11995522-DEMO4", phone="+250780000005")
    create_test_transaction(db, parcel_id=parcel.id, seller_id=seller.id, buyer_id=buyer.id, transaction_code="TX-AVAIL-FLAGGED", status="FLAGGED")
    upi = parcel.upi
    db.close()

    data = _lookup(client, upi)
    assert data["availability"] == "UNAVAILABLE"
    assert data["has_pending_transaction"] is True
    assert data["transaction_status"] == "FLAGGED"
    assert "FLAGGED" in (data["warning_message"] or "")


def test_completed_transaction_is_not_unavailable(client):
    db = TestingSessionLocal()
    parcel = _seed_parcel(db, parcel_code="RW-AVAIL-DONE", upi="DEMO-UPI-RW-AVAIL-DONE")
    seller = create_test_owner(db, owner_code="OWN-AVAIL-SELLER-5", full_name="Availability Seller Five")
    buyer = create_test_owner(db, owner_code="OWN-AVAIL-BUYER-5", full_name="Availability Buyer Five", email="avail-buyer5@test.local", identification_number="11995522-DEMO5", phone="+250780000006")
    create_test_transaction(db, parcel_id=parcel.id, seller_id=seller.id, buyer_id=buyer.id, transaction_code="TX-AVAIL-DONE", status="COMPLETED")
    upi = parcel.upi
    db.close()

    data = _lookup(client, upi)
    assert data["availability"] == "COMPLETED"
    assert data["has_pending_transaction"] is False
    assert data["transaction_status"] == "COMPLETED"


def test_rejected_transaction_restores_availability(client):
    db = TestingSessionLocal()
    parcel = _seed_parcel(db, parcel_code="RW-AVAIL-REJECTED", upi="DEMO-UPI-RW-AVAIL-REJECTED")
    seller = create_test_owner(db, owner_code="OWN-AVAIL-SELLER-6", full_name="Availability Seller Six")
    buyer = create_test_owner(db, owner_code="OWN-AVAIL-BUYER-6", full_name="Availability Buyer Six", email="avail-buyer6@test.local", identification_number="11995522-DEMO6", phone="+250780000007")
    create_test_transaction(db, parcel_id=parcel.id, seller_id=seller.id, buyer_id=buyer.id, transaction_code="TX-AVAIL-REJECTED", status="REJECTED")
    upi = parcel.upi
    db.close()

    data = _lookup(client, upi)
    assert data["availability"] == "AVAILABLE"
    assert data["has_pending_transaction"] is False
    assert data["transaction_status"] == "REJECTED"


def test_second_unresolved_transaction_for_same_parcel_is_rejected(client):
    db = TestingSessionLocal()
    parcel = _seed_parcel(db, parcel_code="RW-AVAIL-CONFLICT", upi="DEMO-UPI-RW-AVAIL-CONFLICT")
    seller = create_test_owner(db, owner_code="OWN-AVAIL-SELLER-7", full_name="Availability Seller Seven")
    buyer = create_test_owner(db, owner_code="OWN-AVAIL-BUYER-7", full_name="Availability Buyer Seven", email="avail-buyer7@test.local", identification_number="11995522-DEMO7", phone="+250780000008")
    parcel_id = parcel.id
    seller_id = seller.id
    buyer_id = buyer.id
    create_ownership_history(db, parcel_id, new_owner_id=seller_id)
    db.close()

    token = make_officer_token(db)
    payload = {
        "parcel_id": parcel_id,
        "seller_owner_id": seller_id,
        "buyer_owner_id": buyer_id,
        "transaction_type": "SALE",
        "transaction_date": datetime.utcnow().isoformat(),
        "declared_value": "1000000",
    }
    first = client.post("/api/transactions", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert first.status_code == 201, first.text

    second = client.post("/api/transactions", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert second.status_code == 409
    assert "incompatible pending transaction" in second.json()["detail"].lower()
