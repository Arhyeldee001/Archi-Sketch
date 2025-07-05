from backend.db import engine
from backend.models import Base

# ⚠️ WARNING: This will delete all tables and recreate them from scratch.
print("Resetting database...")

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

print("Database reset done ✅")
