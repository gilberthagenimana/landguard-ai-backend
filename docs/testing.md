# LandGuard AI — Testing Documentation

## Test Suite: 80 tests, all passing

### Test Files

| File | Tests | Coverage |
|---|---|---|
| `test_auth.py` | 11 | Login, logout, token, inactive users |
| `test_rbac.py` | 13 | Role enforcement for all endpoints |
| `test_parcels.py` | 10 | Parcel CRUD, UPI validation, search |
| `test_owners.py` | 8 | Owner CRUD, search |
| `test_transactions.py` | 8 | Transaction CRUD, validation |
| `test_cases.py` | 10 | Case workflow, status transitions |
| `test_audit.py` | 5 | Audit log access control |
| `test_dashboard.py` | 3 | Dashboard stats for all roles |
| `test_reports.py` | 8 | All report endpoints |
| `test_verification.py` | 2 | 9-rule verification engine |
| `test_risk_service.py` | 1 | AI risk analysis |
| `test_ml_pipeline.py` | 3 | Dataset, training, prediction |
| `test_admin_user_creation.py` | 3 | Admin user management |
| `test_integration_flow.py` | 1 | End-to-end flow |

## Running Tests

```powershell
cd landguard-ai-backend
pytest -v
```

## Test Isolation

- Each test uses in-memory SQLite with `StaticPool`
- `app.dependency_overrides[get_db]` for clean database per test
- No state leakage between tests

## Coverage Areas

- **Authentication**: Login success/failure, token validation, inactive users
- **RBAC**: Officer cannot access admin endpoints, auditor read-only
- **Parcels**: Create, duplicate UPI/code detection, search, update
- **Owners**: Create, duplicate code, search, update
- **Transactions**: Create, validation, nonexistent references
- **Cases**: Status transitions, invalid status rejection
- **Verification**: 9-rule engine, conflict detection
- **Risk**: AI scoring, explanations, feature importance
- **ML**: Dataset generation, model training, prediction
- **Integration**: Full flow from creation to verification
