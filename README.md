# LandGuard AI — Backend

FastAPI backend for the LandGuard AI land transaction verification and fraud risk detection system.

## Technology Stack

- **Framework**: FastAPI + Uvicorn
- **Database**: PostgreSQL (Neon) / SQLite (local dev)
- **ORM**: SQLAlchemy 2 + Alembic
- **ML**: scikit-learn, pandas, NumPy, joblib
- **Auth**: JWT (python-jose), bcrypt (passlib)
- **Rate Limiting**: slowapi

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
DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/dbname
JWT_SECRET_KEY=your-secret-key
```

### 4. Run Migrations

```powershell
alembic upgrade head
python -c "from app.db.init_db import init_db; init_db()"
```

### 5. Start Server

```powershell
cd backend
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
├── tests/                     # Test suite
├── alembic.ini
├── pytest.ini
├── .env.example
└── README.md
```

## Testing

```powershell
pytest -v
```

## Docker

```powershell
docker build -t landguard-backend .
docker run -p 8000:8000 landguard-backend
```
