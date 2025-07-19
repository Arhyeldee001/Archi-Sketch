import os
import base64
import requests
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()

# Test mode configuration
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"
TEST_CONTRACT_CODE = os.getenv("TEST_CONTRACT_CODE")
TEST_API_KEY = os.getenv("TEST_API_KEY")
TEST_SECRET_KEY = os.getenv("TEST_SECRET_KEY")

@router.post("/initiate-payment")
async def initiate_payment(request: Request):
    data = await request.json()
    email = data.get("email")
    immediate_payment = data.get("immediate", False)
    
    if not email:
        raise HTTPException(status_code=400, detail="Email required")

    # In test mode with immediate=False, grant trial without payment
    if TEST_MODE and not immediate_payment:
        return JSONResponse({
            "status": "success",
            "trial_active": True,
            "expires_in": 24  # 1 day trial
        })

    # Real payment flow
    transaction_ref = f"ARTRACER-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    payload = {
        "amount": 5000,
        "customerName": "AR Tracer User",
        "customerEmail": email,
        "paymentReference": transaction_ref,
        "paymentDescription": "1-month AR Tracer Subscription",
        "currencyCode": "NGN",
        "contractCode": TEST_CONTRACT_CODE if TEST_MODE else os.getenv("CONTRACT_CODE"),
        "redirectUrl": f"{os.getenv('BASE_URL')}/payment-success?email={email}",
        "paymentMethods": ["CARD", "ACCOUNT_TRANSFER"]
    }

    auth_str = f"{TEST_API_KEY if TEST_MODE else os.getenv('MONNIFY_API_KEY')}:{TEST_SECRET_KEY if TEST_MODE else os.getenv('MONNIFY_SECRET_KEY')}"
    encoded = base64.b64encode(auth_str.encode()).decode()
    
    response = requests.post(
        "https://sandbox.monnify.com/api/v1/merchant/transactions/init-transaction" if TEST_MODE 
        else "https://api.monnify.com/api/v1/merchant/transactions/init-transaction",
        json=payload,
        headers={"Authorization": f"Basic {encoded}"}
    )
    
    if response.status_code == 200:
        return response.json()
    raise HTTPException(status_code=400, detail="Payment initiation failed")
