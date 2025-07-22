import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, RedirectResponse
import base64
import requests
from backend.db import SessionLocal
from backend.models import User, Subscription
from sqlalchemy.orm import Session

router = APIRouter()

# Configuration
TEST_MODE = os.getenv("TEST_MODE", "true").lower() == "true"
TRIAL_DURATION_HOURS = 24  # 1 day trial
PAID_DURATION_DAYS = 7     # 7 days paid access
AMOUNT = 500               # 500 Naira

# Monnify credentials
MONNIFY_API_KEY = os.getenv("MONNIFY_API_KEY")
MONNIFY_SECRET_KEY = os.getenv("MONNIFY_SECRET_KEY")
CONTRACT_CODE = os.getenv("CONTRACT_CODE")
BASE_URL = os.getenv("BASE_URL")

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_auth_header():
    auth_str = f"{MONNIFY_API_KEY}:{MONNIFY_SECRET_KEY}"
    return base64.b64encode(auth_str.encode()).decode()

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

        # Calculate expiry
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

        # Generate unique reference
        transaction_ref = f"ARTRACER-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        payload = {
            "amount": AMOUNT,
            "customerName": "AR Tracer User",
            "customerEmail": email,
            "paymentReference": transaction_ref,
            "paymentDescription": "7-day AR Tracer Subscription",
            "currencyCode": "NGN",
            "contractCode": CONTRACT_CODE,
            "redirectUrl": f"{BASE_URL}/payment-success?email={email}&reference={transaction_ref}",
            "paymentMethods": ["CARD", "ACCOUNT_TRANSFER"]
        }

        # For testing, simulate success
        if TEST_MODE:
            return JSONResponse({
                "status": "success",
                "checkoutUrl": f"{BASE_URL}/payment-success?email={email}&reference={transaction_ref}&test=true"
            })

        # Real payment
        response = requests.post(
            "https://sandbox.monnify.com/api/v1/merchant/transactions/init-transaction",
            json=payload,
            headers={"Authorization": f"Basic {get_auth_header()}"}
        )

        if response.status_code == 200:
            return JSONResponse(response.json())
            
        raise HTTPException(status_code=response.status_code, detail=response.text)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/payment-success")
async def payment_success(
    request: Request,
    email: str,
    reference: str,
    test: str = None,
    db: Session = Depends(get_db)
):
    try:
        # Test mode simulation
        if test:
            expiry_date = datetime.now() + timedelta(days=PAID_DURATION_DAYS)
            return await create_subscription(email, expiry_date, AMOUNT, False, db)
        
        # Verify real payment
        auth_header = f"Basic {get_auth_header()}"
        verify_url = f"https://sandbox.monnify.com/api/v2/transactions/{reference}"
        
        verify_response = requests.get(verify_url, headers={"Authorization": auth_header})
        if verify_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Payment verification failed")
        
        payment_data = verify_response.json()
        if payment_data.get("paymentStatus") == "PAID":
            expiry_date = datetime.now() + timedelta(days=PAID_DURATION_DAYS)
            return await create_subscription(email, expiry_date, AMOUNT, False, db)
        
        raise HTTPException(status_code=400, detail="Payment not completed")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def create_subscription(email: str, expiry_date: datetime, amount: float, is_trial: bool, db: Session):
    # Create/update subscription
    subscription = Subscription(
        user_email=email,
        expiry_date=expiry_date,
        is_trial=is_trial,
        amount_paid=amount
    )
    db.add(subscription)
    db.commit()
    
    return RedirectResponse(url=f"/ar?payment=success&expiry={expiry_date.isoformat()}")
