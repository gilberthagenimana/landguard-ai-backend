# LandGuard AI — Final Defense Demonstration Guide

## Overview

This guide provides a step-by-step demonstration of the LandGuard AI system for your final-year project defense.

> **Important**: All data used in this demonstration is **synthetic/demo data** created for academic purposes. It does NOT represent real Rwandan citizens or official land records.

---

## Prerequisites

1. Backend running on http://localhost:8000
2. Frontend running on http://localhost:3000
3. Database connected (Neon PostgreSQL)

---

## Demo Accounts

| Role | Email | Password | Purpose |
|---|---|---|---|
| **Admin** | `admin@landguard.local` | `AdminPass123!` | User management, system overview |
| **Officer** | `officer@landguard.local` | `OfficerPass123!` | Transaction creation, verification, case review |
| **Auditor** | `auditor@landguard.local` | `AuditorPass123!` | Read-only review, audit trail |

---

## Step-by-Step Demonstration

### Step 1: Public Citizen UPI Check (No Login)

1. Open http://localhost:3000
2. Click **"Public UPI Check (No Login Required)"**
3. Enter UPI: `UPI-001`
4. Click **"Check Parcel Status"**
5. **Expected**: Parcel status shown, pending transaction warning displayed
6. **Explain**: "This is a public service. Citizens can check if a parcel has pending transactions without creating an account. No personal information is exposed."

### Step 2: Officer Login

1. Click **"Back to Login"**
2. Select **"Officer"** role
3. Email: `officer@landguard.local`
4. Password: `OfficerPass123!`
5. Click **"Sign in to Console"**
6. **Expected**: Officer Dashboard with verification queue

### Step 3: Search Parcel by UPI

1. Go to **Parcels** page
2. Search for `UPI-001`
3. Click **"Details"** on the parcel
4. **Expected**: Parcel details, current owner (Jean Mugisha), ownership history
5. **Explain**: "The system shows the current recorded owner and complete ownership history."

### Step 4: Register a Normal Transaction

1. Click **"+ Conveyance Application"** (or go to Transactions → New Transaction)
2. Fill the form:
   - Parcel: UPI-001 (Jean Mugisha's parcel)
   - Seller: Jean Mugisha
   - Buyer: Diane Nsengimana
   - Type: SALE
   - Value: 15,000,000 RWF
3. Click **"Register & Proceed to Verification"**
4. **Expected**: Transaction created with PENDING status

### Step 5: Run Verification

1. In the Transaction Workspace, click **"Execute Rule Verification Engine"**
2. **Expected**: 10 rule results displayed
3. **Explain**: "The verification engine checks 10 deterministic rules including UPI validity, seller ownership match, conflicting transactions, and unusual patterns."

### Step 6: AI Risk Analysis

1. Click **"Run AI Fraud Risk Analysis"**
2. **Expected**: Risk score (0-100), risk level (LOW/MEDIUM/HIGH), and explanations
3. **Explain**: "The AI model analyzes transaction patterns and provides a risk score with understandable explanations. This is a decision-support tool, not proof of fraud."

### Step 7: Demonstrate Conflicting Transaction

1. Go to **Transactions** → **New Transaction**
2. Try to create another transaction for the same parcel (UPI-001) with a different buyer
3. **Expected**: Error message "Parcel already has an active transaction"
4. **Explain**: "The system prevents duplicate transactions for the same parcel. This is a key fraud prevention feature."

### Step 8: Officer Case Review

1. Go to **Cases** page
2. Click on a case (e.g., CASE-0441)
3. Review the case details, verification results, and AI risk analysis
4. Add review notes
5. Update case status to "UNDER_REVIEW" or "RESOLVED"
6. **Explain**: "Officers can investigate flagged transactions, add notes, and update case status. All actions are audit-logged."

### Step 9: Auditor Login and Review

1. Logout (click user menu → Sign out)
2. Login as **Auditor** (`auditor@landguard.local` / `AuditorPass123!`)
3. Go to **Transactions** — view all transactions
4. Go to **Cases** — review case details
5. Go to **Audit logs** — view complete audit trail
6. **Explain**: "Auditors have read-only access to all records. They can review transactions, verification results, and audit logs but cannot modify them."

### Step 10: Admin User Management

1. Logout and login as **Admin** (`admin@landguard.local` / `AdminPass123!`)
2. Go to **Users** page
3. View all users and their roles
4. Create a new user (demonstrate)
5. Disable/enable a user (demonstrate)
6. **Explain**: "Admins manage user accounts and role assignments. They cannot manipulate transaction history or AI results."

### Step 11: Show Audit Trail

1. Go to **Audit logs** page (as Admin or Auditor)
2. Show the complete audit trail of all actions
3. **Explain**: "Every critical action is recorded in the immutable audit log, including who performed it, when, and what changed."

### Step 12: Explain Limitations

1. **Synthetic data**: "All data is synthetic and created for academic purposes."
2. **Not official**: "This system does not replace official land authorities."
3. **AI limitations**: "AI risk scores are indicators, not proof of fraud."
4. **Data gaps**: "The system cannot detect sales that were never entered into the system."
5. **Human decision**: "Final decisions remain with authorized human officers."

---

## Expected Outputs

| Step | Expected Result |
|---|---|
| Public UPI check | Parcel status + pending warning |
| Officer login | Officer Dashboard |
| Parcel search | Parcel details + ownership history |
| Transaction creation | PENDING status |
| Verification | 10 rules, all PASS (clean) or some WARNING/FAIL |
| AI risk analysis | Score 0-100, level, explanations |
| Conflicting transaction | 409 Conflict error |
| Case review | Status update + notes |
| Auditor review | Read-only access to all records |
| Admin management | User CRUD operations |
| Audit trail | Complete activity log |

---

## Troubleshooting

| Issue | Solution |
|---|---|
| Backend not starting | Check port 8000 is free, run `uvicorn app.main:app --reload --port 8000` |
| Frontend not starting | Run `npm install` then `npm run dev` |
| Database connection error | Check `.env` DATABASE_URL is correct |
| Login fails | Verify email/password, check user is active |
| CORS error | Check CORS_ORIGINS in `.env` includes localhost:3000 |

---

## Reset Demo Data

To reset the database to its original demo state:

```powershell
cd "D:\LandGuard AI\landguard-ai-backend\backend"
python -c "from app.db.init_db import init_db; init_db()"
```

This will re-seed the database with the original demo data.
