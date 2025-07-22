import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import base64
import requests

router = APIRouter()

# Configuration
TEST_MODE = os.getenv("TEST_MODE", "true").lower() == "true"
TRIAL_DURATION_HOURS = 24  # 1 day trial

# Sandbox credentials - replace with yours from Monnify dashboard
MONNIFY_API_KEY = os.getenv("MONNIFY_API_KEY", "MK_TEST_XXXXXXXXXXXXXXXX")
MONNIFY_SECRET_KEY = os.getenv("MONNIFY_SECRET_KEY", "YOUR_TEST_SECRET_KEY")
CONTRACT_CODE = os.getenv("CONTRACT_CODE", "MO_TEST_XXXXXXXXXXXXXXXX")
BASE_URL = os.getenv("BASE_URL", "https://your-render-url.onrender.com")

def get_auth_header():
    auth_str = f"{MONNIFY_API_KEY}:{MONNIFY_SECRET_KEY}"
    return base64.b64encode(auth_str.encode()).decode()

@router.post("/initiate-trial")
async def start_trial(request: Request):
    try:
        data = await request.json()
        email = data.get("email")
        
        if not email:
            raise HTTPException(status_code=400, detail="Email required")

        # In test mode, simulate successful trial
        expiry_date = datetime.now() + timedelta(hours=TRIAL_DURATION_HOURS)
        
        return JSONResponse({
            "status": "success",
            "trial_active": True,
            "expiry_date": expiry_date.isoformat(),
            "message": f"Free trial activated for {TRIAL_DURATION_HOURS} hours"
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/initiate-payment")
async def initiate_payment(request: Request):
    try:
        data = await request.json()
        email = data.get("email")
        
        if not email:
            raise HTTPException(status_code=400, detail="Email required")

        # Generate unique reference
        transaction_ref = f"ARTRACER-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        payload = {
            "amount": 5000,
            "customerName": "AR Tracer User",
            "customerEmail": email,
            "paymentReference": transaction_ref,
            "paymentDescription": "1-month AR Tracer Subscription",
            "currencyCode": "NGN",
            "contractCode": CONTRACT_CODE,
            "redirectUrl": f"{BASE_URL}/payment-success?"
                         f"paymentReference={transaction_ref}&"
                         f"transactionReference=PLACEHOLDER&"  # Monnify will replace this
                         f"status=PLACEHOLDER&"
                         f"amountPaid=5000",
            "paymentMethods": ["CARD", "ACCOUNT_TRANSFER"]
        }

        response = requests.post(
            "https://sandbox.monnify.com/api/v1/merchant/transactions/init-transaction",
            json=payload,
            headers={"Authorization": f"Basic {get_auth_header()}"}
        )

        if response.status_code == 200:
            return JSONResponse({
                "status": "success",
                "checkoutUrl": response.json().get("responseBody", {}).get("checkoutUrl")
            })
            
        raise HTTPException(
            status_code=response.status_code,
            detail=response.text
        )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/payment-success")
async def payment_success(
    request: Request,
    paymentReference: str = None,
    transactionReference: str = None,
    amountPaid: float = None,
    status: str = None
):
    # Debugging - log incoming parameters
    print(f"Received callback with: {request.query_params}")
    
    # Test mode simulation
    if TEST_MODE and not transactionReference:
        expiry_date = datetime.now() + timedelta(days=30)
        return RedirectResponse(
            url=f"/ar?payment=success&expiry={expiry_date.isoformat()}"
        )
    
    # Verify minimum required parameters
    if not transactionReference:
        raise HTTPException(
            status_code=400,
            detail="Transaction reference missing"
        )
    
    # Verify payment with Monnify
    try:
        auth_header = f"Basic {get_auth_header()}"
        verify_url = f"https://sandbox.monnify.com/api/v2/transactions/{transactionReference}"
        
        verify_response = requests.get(
            verify_url,
            headers={"Authorization": auth_header}
        )
        
        if verify_response.status_code == 200:
            payment_data = verify_response.json()
            
            if payment_data.get("paymentStatus") == "PAID":
                expiry_date = datetime.now() + timedelta(days=30)
                
                # In production: Save to database here
                return RedirectResponse(
                    url=f"/ar?payment=success&expiry={expiry_date.isoformat()}"
                )
    
    except Exception as e:
        print(f"Payment verification failed: {str(e)}")
    
    # If any check fails
    return RedirectResponse(url="/ar?payment=failed")
