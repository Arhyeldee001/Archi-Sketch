import os
import base64
import requests
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()

@router.post("/initiate-payment")
async def initiate_payment(request: Request):
    # Get email from frontend
    data = await request.json()
    email = data.get("email")
    
    if not email:
        return JSONResponse({"error": "Email required"}, status_code=400)
    
    # Generate unique reference
    transaction_ref = f"ARTRACER-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Create payment request
    payload = {
        "amount": 5000,
        "customerName": "AR Tracer User",
        "customerEmail": email,
        "paymentReference": transaction_ref,
        "paymentDescription": "1-month AR Tracer Subscription",
        "currencyCode": "NGN",
        "contractCode": os.getenv("CONTRACT_CODE"),
        "redirectUrl": f"{os.getenv('BASE_URL')}/payment-success?email={email}",
        "paymentMethods": ["CARD", "ACCOUNT_TRANSFER"]
    }
    
    auth_str = f"{os.getenv('MONNIFY_API_KEY')}:{os.getenv('MONNIFY_SECRET_KEY')}"
    encoded = base64.b64encode(auth_str.encode()).decode()
    
    response = requests.post(
        "https://api.monnify.com/api/v1/merchant/transactions/init-transaction",
        json=payload,
        headers={"Authorization": f"Basic {encoded}"}
    )
    
    if response.status_code == 200:
        return response.json()
    return JSONResponse({"error": "Payment initiation failed"}, status_code=400)
