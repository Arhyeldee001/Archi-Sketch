import base64
import requests
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
import os

router = APIRouter()

# Sandbox credentials - REPLACE THESE WITH YOURS
MONNIFY_API_KEY = "MK_TEST_TFD7XNBYF2"
MONNIFY_SECRET_KEY = "R1WZ04VD1PQ9ZW14R3FKF4QLVSJTJZTH"
CONTRACT_CODE = "4527853034"
BASE_URL = "https://your-render-url.onrender.com"  # Your Render URL

def get_monnify_auth_header():
    auth_str = f"{MONNIFY_API_KEY}:{MONNIFY_SECRET_KEY}"
    return base64.b64encode(auth_str.encode()).decode()

@router.post("/initiate-payment")
async def initiate_payment(request: Request):
    data = await request.json()
    email = data.get("email")
    
    if not email:
        raise HTTPException(status_code=400, detail="Email required")

    try:
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
            "redirectUrl": f"{BASE_URL}/payment-success",
            "paymentMethods": ["CARD", "ACCOUNT_TRANSFER"]
        }

        response = requests.post(
            "https://sandbox.monnify.com/api/v1/merchant/transactions/init-transaction",
            json=payload,
            headers={
                "Authorization": f"Basic {get_monnify_auth_header()}"
            }
        )

        if response.status_code == 200:
            return JSONResponse(response.json())
        
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Monnify error: {response.text}"
        )

    @router.get("/payment-success")
async def payment_success(
    paymentReference: str,
    transactionReference: str,
    amountPaid: float
):
    # Verify the payment with Monnify
    try:
        verify_response = requests.get(
            f"https://sandbox.monnify.com/api/v2/transactions/{transactionReference}",
            headers={"Authorization": f"Basic {get_monnify_auth_header()}"}
        )
        
        if verify_response.status_code == 200:
            # Payment successful - grant access
            expiry_date = datetime.now() + timedelta(days=30)
            return JSONResponse({
                "status": "success",
                "expiry_date": expiry_date.isoformat()
            })
    
    except Exception as e:
        print(f"Verification failed: {str(e)}")
    
    return JSONResponse(
        {"status": "failed"},
        status_code=400
    )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Payment processing failed: {str(e)}"
        )
