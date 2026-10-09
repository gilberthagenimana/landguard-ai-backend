# LandGuard AI — Backend

FastAPI backend for the LandGuard AI land transaction verification and fraud risk detection system.

## Technology Stack

- **Framework**: FastAPI + Uvicorn
- **Database**: PostgreSQL (Neon) / SQLite (local dev)
- **ORM**: SQLAlchemy 2 + Alembic
- **ML**: scikit-learn, pandas, NumPy, joblib
- **Auth**: JWT (python-jose), bcrypt (passlib), account lockout
- **Rate Limiting**: slowapi
- **Security Headers**: X-Content-Type-Options, X-Frame-Options, HSTS, CSP

## Quick Start

### 1. Create Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```powershell
pip install -r backend/requirements.txt
```

### 3. Configure Environment

Copy `.env.example` to `.env` and update:

```ini
DATABASE_URL=sqlite:///./landguard_ai.db
JWT_SECRET_KEY=your-secret-key
```

### 4. Initialize Database

```powershell
cd backend
python -c "from app.db.init_db import init_db; init_db()"
```

### 5. Start Server

```powershell
uvicorn app.main:app --reload --port 8000
```

## API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Project Structure

```
landguard-ai-backend/
├── backend/
│   ├── app/
│   │   ├── api/v1/routes/    # REST endpoints (auth, parcels, transactions, cases, public...)
│   │   ├── core/             # Config, security, roles
│   │   ├── db/               # Database session, seed
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic (verification, risk, audit, auth)
│   │   └── main.py           # FastAPI entrypoint
│   ├── requirements.txt
│   └── alembic.ini
├── ml/                        # ML pipeline
├── database/                  # Migrations & seed
├── tests/                     # Test suite (80 tests)
├── alembic.ini
├── pytest.ini
├── .env.example
└── README.md
```

## API Endpoints

### Authentication
- `POST /api/auth/login` — Login with email/username + password + role
- `POST /api/auth/logout` — Logout
- `GET /api/auth/me` — Get current user profile
- `PUT /api/auth/me` — Update profile

### Public (No Auth)
- `GET /api/public/parcels/{upi}` — Public UPI check

### Parcels
- `GET /api/parcels` — List/search parcels
- `POST /api/parcels` — Create parcel (with UPI)
- `GET /api/parcels/{id}` — Get parcel by ID
- `GET /api/parcels/upi/{upi}` — Get parcel by UPI
- `PUT /api/parcels/{id}` — Update parcel
- `GET /api/parcels/{id}/ownership-history` — Ownership history
- `GET /api/parcels/upi/{upi}/ownership-history` — Ownership history by UPI
- `GET /api/parcels/{id}/transactions` — Parcel transactions

### Owners
- `GET /api/owners` — List/search owners
- `POST /api/owners` — Create owner
- `GET /api/owners/{id}` — Get owner
- `PUT /api/owners/{id}` — Update owner

### Transactions
- `GET /api/transactions` — List transactions
- `POST /api/transactions` — Create transaction
- `GET /api/transactions/{id}` — Get transaction
- `PUT /api/transactions/{id}/status` — Update status (with validation)
- `GET /api/transactions/{id}/status-history` — Status history
- `GET /api/transactions/{id}/verification` — Verification results

### Verification & Risk
- `POST /api/verification/transactions/{id}` — Run verification
- `POST /api/risk-analysis/transactions/{id}` — AI risk analysis

### Cases
- `GET /api/cases` — List cases
- `POST /api/cases` — Create case
- `GET /api/cases/{id}` — Get case detail
- `PUT /api/cases/{id}` — Update case
- `GET /api/cases/{id}/status-history` — Case status history

### Audit & Reports
- `GET /api/audit-logs` — View audit logs
- `GET /api/audit-logs/export` — Export audit logs
- `GET /api/reports/verification` — Verification report
- `GET /api/reports/risk` — Risk report
- `GET /api/reports/cases` — Cases report
- `GET /api/reports/audit` — Audit report
- `GET /api/reports/parcels/{id}/history` — Parcel history report

## Demo Credentials

| Role | Email | Password |
|---|---|---|
| Admin | admin@landguard.local | AdminPass123! |
| Officer | officer@landguard.local | OfficerPass123! |
| Auditor | auditor@landguard.local | AuditorPass123! |

## Demo UPI Values

| UPI | Parcel Code | District | Status |
|---|---|---|---|
| UPI-001 | RW-10432 | Kicukiro | ACTIVE |
| UPI-002 | RW-88213 | Gasabo | ACTIVE |
| UPI-003 | RW-20991 | Huye | UNDER_REVIEW |
| UPI-004 | RW-33107 | Musanze | ACTIVE |
| UPI-005 | RW-55621 | Nyarugenge | ACTIVE |
| UPI-006 | RW-77890 | Rubavu | DISPUTED |

## Testing

```powershell
pytest -v
```

80 tests covering authentication, RBAC, parcels, owners, transactions, verification, risk analysis, cases, audit, and reports.

## Security Features

- Account lockout after 5 failed attempts (30-min lockout)
- Security headers (X-Content-Type-Options, X-Frame-Options, HSTS, CSP)
- Rate limiting via slowapi
- JWT authentication with role-based access control
- Input validation via Pydantic
- SQL injection protection via SQLAlchemy ORM
- Audit logging for all critical actions
- Public endpoint exposes only safe, non-sensitive information

## Docker

```powershell
docker build -t landguard-backend .
docker run -p 8000:8000 landguard-backend
```
