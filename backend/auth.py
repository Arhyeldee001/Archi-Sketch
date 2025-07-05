from sqlalchemy.orm import Session
from .models import User
from .utils import hash_password, verify_password  # Updated import

def register_user(db: Session, fullname: str, phone: str, email: str, password: str):
    hashed_password = hash_password(password)  # Uses bcrypt now
    print("🔐 Hashed password (bcrypt):", hashed_password)
    
    user = User(
        fullname=fullname,
        phone=phone,
        email=email,
        hashed_password=hashed_password
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def login_user(db: Session, email: str, password: str):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None

    print("LOGIN 🔍 Input password:", password)
    print("LOGIN 🔐 Password in DB:", user.hashed_password)

    # Use verify_password instead of direct comparison
    if not verify_password(password, user.hashed_password):
        print("LOGIN ❌ Passwords didn't match")
        return None

    print("LOGIN ✅ Passwords matched")
    return user