import bcrypt

def hash_password(password: str) -> str:
    """Hash a password using bcrypt (with auto-generated salt)"""
    # bcrypt handles salt generation internally
    hashed_bytes = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    return hashed_bytes.decode('utf-8')  # Convert bytes to string for storage

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check if the provided password matches the stored hash"""
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except Exception:
        return False  # Safe fallback if verification fails