import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.db import SessionLocal
from backend.models import User
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Read admin password from .env or fallback to 'secret123'
ADMIN_SECRET = os.getenv("ADMIN_PASSWORD", "secret123")

router = APIRouter(prefix="/admin", tags=["Admin"])

# Get DB dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Admin user list route
@router.get("/users")
def get_users(admin_password: str, db: Session = Depends(get_db)):
    if admin_password != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized")

    users = db.query(User).all()
    return [
        {
            "id": user.id,
            "fullname": user.fullname,
            "phone": user.phone,
            "email": user.email,
            "hashed_password": user.hashed_password
        }
        for user in users
    ]
