from app.db.seed import seed_demo_data
from app.db.session import SessionLocal

db = SessionLocal()

try:
    seed_demo_data(db)
    print("Demo seed completed successfully.")
finally:
    db.close()
