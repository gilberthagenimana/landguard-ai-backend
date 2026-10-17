# LandGuard AI — System Architecture

## 1. Overview

LandGuard AI is a three-layer architecture with clear separation of concerns:

```
Frontend (React + TypeScript + Vite)
    ↓
Backend API (FastAPI + Python)
    ↓
Business Services / Domain Logic
    ↓
Database (PostgreSQL / Neon)
    ↓
AI/ML Module (scikit-learn)
```

## 2. Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript 5, Vite 6, Lucide React |
| Backend | Python 3.13+, FastAPI, Pydantic v2, SQLAlchemy 2 |
| Database | PostgreSQL (Neon) / SQLite (local dev) |
| ML/AI | scikit-learn, pandas, NumPy, joblib |
| Auth | JWT (python-jose), bcrypt (passlib), account lockout |
| Rate Limiting | slowapi |
| Testing | pytest, pytest-asyncio, HTTPX |

## 3. Folder Structure

```
landguard-ai-backend/
├── backend/
│   ├── app/
│   │   ├── api/v1/routes/    # REST endpoints (12 routers)
│   │   ├── core/             # Config, security, roles, transaction_status
│   │   ├── db/               # Database session, seed
│   │   ├── models/           # SQLAlchemy models (10 tables)
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic (auth, verification, risk, audit)
│   │   └── main.py           # FastAPI entrypoint
│   ├── requirements.txt
│   └── alembic.ini
├── ml/                        # ML pipeline
├── database/                  # Migrations & seed
├── tests/                     # Test suite (91 tests)
└── docs/                      # Documentation
```

## 4. User Roles

| Role | Permissions |
|---|---|
| ADMIN | User management, role assignment, system config, audit logs |
| OFFICER | CRUD parcels/owners, create transactions, verify, risk analysis, case management |
| AUDITOR | Read-only access to transactions, verification, risk, cases, audit logs |

## 5. Main Workflow

1. User logs in with JWT authentication
2. System validates role and permissions
3. Officer creates transaction with UPI
4. Verification engine runs 10 deterministic checks
5. AI model calculates risk score with explanations
6. System flags conflicts and creates cases
7. Officer reviews and updates case status
8. Auditor reviews all activities
9. All actions are audit-logged

## 6. Transaction Status Workflow

```
PENDING → UNDER_REVIEW → APPROVED → COMPLETED
   ↓           ↓            ↓
FLAGGED    REJECTED     REJECTED
   ↓
UNDER_REVIEW
```

## 7. AI/ML Workflow

1. Load synthetic dataset (clearly labeled as DEMO/SYNTHETIC)
2. Engineer 9 transaction-level features
3. Train Logistic Regression, Decision Tree, Random Forest
4. Evaluate with accuracy, precision, recall, F1, confusion matrix
5. Select best model by F1 score
6. Save model with joblib
7. Backend extracts features and returns risk score + explanations

## 8. Security Architecture

- JWT tokens with 60-minute expiry
- Account lockout after 5 failed attempts (30-min lockout)
- Security headers (X-Frame-Options, HSTS, CSP)
- Rate limiting on auth endpoints
- RBAC enforced at API route layer
- Input validation via Pydantic
- SQL injection protection via ORM
- Audit logging for all critical actions
- Public endpoint exposes only safe information

## 9. Database Schema

### Core Tables
- `users` — System users with lockout fields
- `roles` — ADMIN, OFFICER, AUDITOR
- `user_roles` — User-to-role assignments
- `owners` — Landowners
- `parcels` — Land parcels with UPI
- `ownership_history` — Title transfer history
- `transactions` — Land transactions with status
- `verification_results` — Rule check results
- `risk_predictions` — AI risk scores
- `case_reviews` — Investigation cases
- `case_status_history` — Case status changes
- `transaction_status_history` — Transaction status changes
- `audit_logs` — Immutable activity log
- `subdivisions` — Parcel subdivision records
- `system_config` — System configuration

## 10. API Endpoints

### Authentication
- `POST /api/auth/login` — Login
- `POST /api/auth/logout` — Logout
- `GET /api/auth/me` — Current user
- `PUT /api/auth/me` — Update profile

### Public (No Auth)
- `GET /api/public/parcels/{upi}` — Public UPI check

### Parcels
- `GET /api/parcels` — List/search
- `POST /api/parcels` — Create
- `GET /api/parcels/{id}` — Get by ID
- `GET /api/parcels/upi/{upi}` — Get by UPI
- `PUT /api/parcels/{id}` — Update
- `GET /api/parcels/{id}/ownership-history` — History
- `GET /api/parcels/upi/{upi}/ownership-history` — History by UPI
- `GET /api/parcels/{id}/transactions` — Transactions

### Owners
- `GET /api/owners` — List/search
- `POST /api/owners` — Create
- `GET /api/owners/{id}` — Get
- `PUT /api/owners/{id}` — Update

### Transactions
- `GET /api/transactions` — List
- `POST /api/transactions` — Create
- `GET /api/transactions/{id}` — Get
- `PUT /api/transactions/{id}/status` — Update status
- `GET /api/transactions/{id}/status-history` — Status history
- `GET /api/transactions/{id}/verification` — Verification results

### Verification & Risk
- `POST /api/verification/transactions/{id}` — Run verification
- `POST /api/risk-analysis/transactions/{id}` — AI risk analysis

### Cases
- `GET /api/cases` — List
- `POST /api/cases` — Create
- `GET /api/cases/{id}` — Get
- `PUT /api/cases/{id}` — Update
- `GET /api/cases/{id}/status-history` — Status history

### Audit & Reports
- `GET /api/audit-logs` — View logs
- `GET /api/audit-logs/export` — Export logs
- `GET /api/reports/verification` — Verification report
- `GET /api/reports/risk` — Risk report
- `GET /api/reports/cases` — Cases report
- `GET /api/reports/audit` — Audit report
- `GET /api/reports/parcels/{id}/history` — Parcel history report
