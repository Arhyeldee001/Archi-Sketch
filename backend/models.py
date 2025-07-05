from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)  # Changed for PostgreSQL
    fullname = Column(String(100))  # Added length constraint
    phone = Column(String(20))
    email = Column(String(255), unique=True, index=True)  # Increased length
    hashed_password = Column(String(255), nullable=False)
    is_first_login = Column(Boolean, default=True, nullable=False)