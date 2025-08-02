import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, RiniedirectResponse
import requests
import base64
from backend.db import SessionLocal
from backend.models import User, Subscription
from sqlalchemy.orm import Session

router = APIRouter()

# Paystack configuration
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
BASE_URL = os.getenv("BASE_URL")  # Your frontend URL (e.g., "https://yourdomain.com")
WEEKLY_SUBSCRIPTION_AMOUNT = 5000  # 5000 Naira in kobo (₦5,000)
TRIAL_DURATION_HOURS = 24  # 1 day trial

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_paystack_auth_header():
    return {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}

@router.post("/initiate-trial")
async def start_trial(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        email = data.get("email")
        
        if not email:
            raise HTTPException(status_code=400, detail="Email required")

        # Check if user already used trial
        user = db.query(User).filter(User.email == email).first()
        if user and user.used_trial:
            raise HTTPException(status_code=400, detail="Free trial already used")

        # Calculate expiry (24 hours)
        expiry_date = datetime.now() + timedelta(hours=TRIAL_DURATION_HOURS)
        
        # Create/update user record
        if not user:
            user = User(email=email, used_trial=True)
            db.add(user)
        else:
            user.used_trial = True
        
        # Create subscription
        subscription = Subscription(
            user_email=email,
            expiry_date=expiry_date,
            is_trial=True,
            amount_paid=0
        )
        db.add(subscription)
        db.commit()
        
        return JSONResponse({
            "status": "success",
            "expiry_date": expiry_date.isoformat(),
            "message": f"Free trial activated for {TRIAL_DURATION_HOURS} hours"
        })
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/initiate-payment")
async def initiate_payment(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        email = data.get("email")
        
        if not email:
            raise HTTPException(status_code=400, detail="Email required")

        transaction_ref = f"ARTRACER-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        payload = {
            "email": email,
            "amount": WEEKLY_SUBSCRIPTION_AMOUNT,
            "reference": transaction_ref,
            "callback_url": f"{BASE_URL}/verify-paystack-payment?email={email}",
            "metadata": {
                "custom_fields": [
                    {
                        "display_name": "Subscription Type",
                        "variable_name": "subscription_type",
                        "value": "weekly_access"
                    }
                ]
            }
        }

        print(f"Payload sent to Paystack: {payload}")  # Debug log

        response = requests.post(
            "https://api.paystack.co/transaction/initialize",
            json=payload,
            headers=get_paystack_auth_header()
        )

        print(f"Paystack response: {response.text}")  # Debug log

        if response.status_code == 200:
            return JSONResponse({
                "status": "success",
                "payment_url": response.json()["data"]["authorization_url"]
            })
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Paystack error: {response.text}"
            )
            
    except Exception as e:
        print(f"Error in initiate-payment: {str(e)}")  # Debug log
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/check-subscription")
async def check_subscription(email: str, db: Session = Depends(get_db)):
    """Check if user has active subscription"""
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return JSONResponse({"has_access": False, "reason": "User not found"})
        
        # Check for active subscription
        active_sub = db.query(Subscription).filter(
            Subscription.user_email == email,
            Subscription.expiry_date > datetime.now()
        ).first()
        
        if active_sub:
            return JSONResponse({
                "has_access": True,
                "expiry": active_sub.expiry_date.isoformat(),
                "is_trial": active_sub.is_trial
            })
        
        return JSONResponse({"has_access": False, "reason": "No active subscription"})
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
