# Database Seed Data

The application seeds demo data automatically on startup via `backend/app/db/seed.py`.

## What Is Seeded

- **3 user accounts**: admin, officer, auditor (with role assignments)
- **10 owners**: Synthetic Rwandan names with demo identification numbers
- **6 parcels**: Across Kigali, Southern, Northern, and Western provinces
- **9 ownership history records**: Including recent changes for risk detection
- **8 transactions**: Mix of VERIFIED, UNDER_REVIEW, and PENDING statuses
- **5 risk predictions**: Pre-computed risk scores for demonstration
- **5 case reviews**: Various statuses (OPEN, UNDER_REVIEW, NEEDS_INFORMATION)

## Important

All seeded data is **100% synthetic** and created for academic testing.
It does **not** represent real Rwandan citizens or official land records.

## Re-seeding

To reset the database and re-seed:
```powershell
# Delete the SQLite file, then restart the backend
Remove-Item landguard_ai.db -Force
# Start backend — it will recreate and re-seed automatically
```
