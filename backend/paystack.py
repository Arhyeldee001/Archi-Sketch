import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, RedirectResponse
import requests
import base64
from backend.db import SessionLocal
from backend.models import User, Subscription
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext


router = APIRouter()

# Paystack configuration
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
BASE_URL = os.getenv("BASE_URL")  # Your frontend URL (e.g., "https://yourdomain.com")
WEEKLY_SUBSCRIPTION_AMOUNT = 100 * 200  # 20000 Naira in kobo (₦20,000)
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
        
@router.get("/verify-paystack-payment")
async def verify_payment(
    email: str,
    reference: str = None,
    trxref: str = None,  # Paystack may use either
    db: Session = Depends(get_db)
):
    try:
        # Use either reference or trxref
        payment_ref = reference or trxref
        if not payment_ref:
            raise HTTPException(status_code=400, detail="Payment reference required")

        # Verify payment with Paystack
        verify_response = requests.get(
            f"https://api.paystack.co/transaction/verify/{payment_ref}",
            headers=get_paystack_auth_header()
        )
        
        if verify_response.status_code != 200:
            print(f"Paystack verification failed for reference {payment_ref}")
            raise HTTPException(status_code=400, detail="Payment verification failed")
        
        payment_data = verify_response.json()
        if payment_data["data"]["status"] == "success":
            # Grant 7-day access
            expiry_date = datetime.now() + timedelta(days=7)
            
            # Get or create user
            user = db.query(User).filter(User.email == email).first()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Create new subscription
            subscription = Subscription(
                user_id=user.id,
                user_email=email,
                expiry_date=expiry_date,
                is_trial=False,
                amount_paid=200,  # ₦5000 in Naira (not kobo)
                payment_reference=payment_ref,
                is_active=True
            )
            db.add(subscription)
            
            # Update user's last subscription date
            user.last_subscription_date = datetime.now()
            user.used_trial = True  # If you want to mark trial as used
            
            db.commit()
            
            # Log successful subscription
            print(f"""
            🟢 NEW SUBSCRIPTION CREATED
            User: {email} (ID: {user.id})
            Amount: ₦{5000}
            Expires: {expiry_date}
            Reference: {payment_ref}
            """)
            
            return RedirectResponse(url="/ar?payment=success")
        
        raise HTTPException(status_code=400, detail="Payment not completed")
    
    except Exception as e:
        db.rollback()
        print(f"🔴 Payment verification error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/check-subscription")
async def check_subscription(email: str, db: Session = Depends(get_db)):
    """Check if user has active subscription (even after logout)"""
    try:
        # Find the MOST RECENT valid subscription
        active_sub = db.query(Subscription).filter(
            Subscription.user_email == email,
            Subscription.expiry_date > datetime.now()
        ).order_by(Subscription.expiry_date.desc()).first()

        if active_sub:
            return {
                "has_access": True,
                "expiry": active_sub.expiry_date.isoformat(),
                "is_trial": active_sub.is_trial
            }
        
        return {"has_access": False, "reason": "No active subscription"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/user-profile")
async def get_user_profile(email: str, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "name": user.fullname or "",  # Note: using fullname instead of full_name
            "email": user.email,
            "phone": user.phone or ""  # Note: using phone instead of phone_number
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# Add these at the top of your file
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Add these new endpoints
@router.post("/api/update-profile")
async def update_profile(
    request: Request,
    db: Session = Depends(get_db)
):
    data = await request.json()
    email = data.get("email")
    fullname = data.get("fullname")
    phone = data.get("phone")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if fullname is not None:
        user.fullname = fullname
    if phone is not None:
        user.phone = phone

    db.commit()
    return {"status": "success", "message": "Profile updated"}

@router.post("/api/change-password")
async def change_password(
    request: Request,
    db: Session = Depends(get_db)
):
    data = await request.json()
    email = data.get("email")
    current_password = data.get("current_password")
    new_password = data.get("new_password")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify current password
    if not pwd_context.verify(current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    # Update password
    user.hashed_password = pwd_context.hash(new_password)
    db.commit()

    return {"status": "success", "message": "Password updated successfully"}
