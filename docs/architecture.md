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
Database (PostgreSQL / SQLite)
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
│   │   ├── api/v1/routes/    # REST endpoints
│   │   ├── core/             # Config, security, roles
│   │   ├── db/               # Database session, seed
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic
│   │   └── main.py           # FastAPI entrypoint
│   ├── requirements.txt
│   └── alembic.ini
├── ml/                        # ML pipeline
├── database/                  # Migrations & seed
├── tests/                     # Test suite (80 tests)
└── README.md
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
4. Verification engine runs deterministic checks
5. AI model calculates risk score with explanations
6. System flags conflicts and creates cases
7. Officer reviews and updates case status
8. Auditor reviews all activities
9. All actions are audit-logged

## 6. AI/ML Workflow

1. Load synthetic dataset (clearly labeled as DEMO/SYNTHETIC)
2. Engineer 9 transaction-level features
3. Train Logistic Regression, Decision Tree, Random Forest
4. Evaluate with accuracy, precision, recall, F1, confusion matrix
5. Select best model by F1 score
6. Save model with joblib
7. Backend extracts features and returns risk score + explanations

## 7. Security Architecture

- JWT tokens with 60-minute expiry
- Account lockout after 5 failed attempts
- Security headers (X-Frame-Options, HSTS, CSP)
- Rate limiting on auth endpoints
- RBAC enforced at API route layer
- Input validation via Pydantic
- SQL injection protection via ORM
- Audit logging for all critical actions
- Public endpoint exposes only safe information
