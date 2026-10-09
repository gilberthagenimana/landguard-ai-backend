# LandGuard AI — Security Documentation

## Authentication

- **JWT tokens** with 60-minute expiry
- **bcrypt** password hashing via passlib
- **Account lockout** after 5 failed attempts (30-minute lockout)
- **Role validation** at login (user must have the requested role)

## Authorization

- **RBAC** enforced at API route layer via `require_roles()` decorator
- Three roles: ADMIN, OFFICER, AUDITOR
- Each endpoint specifies allowed roles
- Auditor has read-only access

## Security Headers

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `Content-Security-Policy: default-src 'self'`
- `Referrer-Policy: strict-origin-when-cross-origin`

## Rate Limiting

- **slowapi** configured with IP-based rate limiting
- Applied to authentication endpoints
- Prevents brute-force attacks

## Input Validation

- **Pydantic v2** schemas for all request/response models
- Automatic 422 validation errors
- Field constraints (min_length, gt=0, Literal types)
- No raw user input passed to database

## SQL Injection Protection

- **SQLAlchemy ORM** with parameterized queries
- No raw SQL string concatenation
- All database operations through ORM

## Audit Logging

- All critical actions logged with user, action, entity, timestamp
- Audit logs are append-only (no DELETE/PUT endpoints)
- Failed login attempts recorded
- Status changes tracked with history

## Public Endpoint Security

- `GET /api/public/parcels/{upi}` requires no authentication
- Returns only safe, non-sensitive information
- Does NOT expose: owner names, contact info, seller/buyer details, audit data, investigation notes
- Includes clear disclaimer about official verification

## CORS

- Configured via environment variable `CORS_ORIGINS`
- Defaults to localhost:3000 and localhost:5173
- Credentials enabled for authenticated requests
