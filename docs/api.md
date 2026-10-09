# LandGuard AI — API Documentation

Interactive documentation available at http://localhost:8000/docs (Swagger UI) and http://localhost:8000/redoc (ReDoc).

## Authentication

### POST /api/auth/login
```json
{
  "email": "officer@landguard.local",
  "password": "OfficerPass123!",
  "role": "OFFICER"
}
```
Returns: `{ "access_token": "eyJ...", "token_type": "bearer" }`

## Public Endpoints (No Auth)

### GET /api/public/parcels/{upi}
Returns safe parcel information for citizens. No authentication required.

```json
{
  "upi": "UPI-001",
  "parcel_code": "RW-10432",
  "location": "Kicukiro / Niboye / Kagarama",
  "district": "Kicukiro",
  "status": "ACTIVE",
  "has_pending_transaction": true,
  "warning_message": "WARNING: This parcel has a pending or under-review transaction...",
  "public_notice": "This is a preliminary check only..."
}
```

## Parcels

### GET /api/parcels/upi/{upi}
Get parcel by UPI (Unique Parcel Identifier).

### GET /api/parcels/{id}/ownership-history
Get ownership history for a parcel.

## Transactions

### POST /api/transactions
Create transaction. Returns 409 if parcel already has active transaction.

### PUT /api/transactions/{id}/status
Update status with validation:
- PENDING → UNDER_REVIEW, FLAGGED, REJECTED
- UNDER_REVIEW → FLAGGED, APPROVED, REJECTED
- FLAGGED → UNDER_REVIEW, APPROVED, REJECTED
- APPROVED → COMPLETED, REJECTED

## Cases

### POST /api/cases
Create investigation case with priority (LOW, MEDIUM, HIGH, CRITICAL).

### GET /api/cases/{id}/status-history
Get case status change history.
