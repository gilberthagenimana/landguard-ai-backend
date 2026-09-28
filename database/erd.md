# Entity Relationship Diagram (ERD)

## Conceptual ERD

```mermaid
erDiagram
    USERS ||--o{ USER_ROLES : has
    ROLES ||--o{ USER_ROLES : assigned_to
    USERS ||--o{ PARCELS : creates
    USERS ||--o{ TRANSACTIONS : creates
    USERS ||--o{ AUDIT_LOGS : performs
    USERS ||--o{ CASE_REVIEWS : reviews

    PARCELS ||--o{ OWNERSHIP_HISTORY : has
    PARCELS ||--o{ TRANSACTIONS : has
    PARCELS ||--o{ VERIFICATION_RESULTS : evaluated
    PARCELS ||--o{ CASE_REVIEWS : involved_in

    OWNERS ||--o{ OWNERSHIP_HISTORY : previous_or_new
    OWNERS ||--o{ TRANSACTIONS : seller_or_buyer

    TRANSACTIONS ||--o{ VERIFICATION_RESULTS : analyzed
    TRANSACTIONS ||--o{ RISK_ANALYSIS : scored
    TRANSACTIONS ||--|| CASE_REVIEWS : linked_to

    USERS {
        UUID id PK
        string email
        string password_hash
        string full_name
        string status
        timestamp created_at
    }

    ROLES {
        UUID id PK
        string name
        string description
    }

    USER_ROLES {
        UUID id PK
        UUID user_id FK
        UUID role_id FK
    }

    PARCELS {
        UUID id PK
        string parcel_id
        string location
        string district
        string sector
        string cell
        string village
        float area
        string status
        string registration_ref
        timestamp created_at
        timestamp updated_at
    }

    OWNERS {
        UUID id PK
        string owner_id
        string name
        string identification_number
        string contact_info
        string status
        timestamp created_at
        timestamp updated_at
    }

    OWNERSHIP_HISTORY {
        UUID id PK
        UUID parcel_id FK
        UUID previous_owner_id FK
        UUID new_owner_id FK
        date transfer_date
        string reason_type
        string supporting_reference
        timestamp created_at
    }

    TRANSACTIONS {
        UUID id PK
        UUID parcel_id FK
        UUID seller_owner_id FK
        UUID buyer_owner_id FK
        string transaction_type
        date transaction_date
        decimal declared_value
        string status
        UUID created_by FK
        timestamp created_at
        timestamp updated_at
    }

    VERIFICATION_RESULTS {
        UUID id PK
        UUID transaction_id FK
        string rule_name
        string status
        string severity
        text explanation
    }

    RISK_ANALYSIS {
        UUID id PK
        UUID transaction_id FK
        float risk_score
        string risk_level
        json indicators
        timestamp created_at
    }

    CASE_REVIEWS {
        UUID id PK
        UUID transaction_id FK
        UUID parcel_id FK
        UUID assigned_to FK
        string status
        text review_notes
        timestamp created_at
        timestamp updated_at
    }

    AUDIT_LOGS {
        UUID id PK
        UUID user_id FK
        string action
        string entity
        UUID entity_id
        json metadata
        timestamp created_at
    }
```

## Design notes

- The schema is normalized around transactions, parcels, owners, and reviews.
- Ownership history is tracked separately from current ownership records to support temporal auditing.
- Rule results and AI risk outputs are stored independently to preserve explainability and evidence.
- Audit logs are append-only in practice and capture key human/system actions without storing sensitive personal secrets.
