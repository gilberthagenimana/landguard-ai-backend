"""Reset demo data to original seed state.

This script re-seeds the database with the original demo data.
It does NOT delete user-created data unless explicitly requested.

Usage:
    python scripts/reset_demo_data.py
"""
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.init_db import init_db


def main():
    print("Resetting demo data...")
    print("This will re-seed the database with original demo data.")
    print("User-created records may be preserved depending on implementation.")
    print()

    init_db()

    print("Demo data reset complete!")
    print()
    print("Demo accounts:")
    print("  Admin:   admin@landguard.local / AdminPass123!")
    print("  Officer: officer@landguard.local / OfficerPass123!")
    print("  Auditor: auditor@landguard.local / AuditorPass123!")
    print()
    print("Demo UPI values: UPI-001 through UPI-006")


if __name__ == "__main__":
    main()
