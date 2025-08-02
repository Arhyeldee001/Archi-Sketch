from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    fullname = Column(String(100))
    phone = Column(String(20))
    email = Column(String(255), unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_first_login = Column(Boolean, default=True, nullable=False)
    # New payment-related fields
    used_trial = Column(Boolean, default=False, nullable=False)
    last_subscription_date = Column(DateTime)
    
    # Relationships would be added here if using them
    subscriptions = relationship("Subscription", back_populates="user")

class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True)  # Linking to user.id
    user_email = Column(String(255), index=True)  # Duplicate for easy queries
    expiry_date = Column(DateTime, nullable=False)
    is_trial = Column(Boolean, nullable=False)
    amount_paid = Column(Float, default=0.0)
    payment_reference = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

     # Establish relationship with User
    user = relationship("User", back_populates="subscriptions")
