import requests
import base64
from datetime import datetime, timedelta
from fastapi import APIRouter

router = APIRouter()

MONNIFY_API_KEY = "YOUR_API_KEY"
MONNIFY_SECRET_KEY = "YOUR_SECRET_KEY"
CONTRACT_CODE = "YOUR_CONTRACT_CODE"
BASE_URL = "https://api.monnify.com"

def get_auth_header():
    auth_str = f"{MONNIFY_API_KEY}:{MONNIFY_SECRET_KEY}"
    encoded = base64.b64encode(auth_str.encode()).decode()
    return {"Authorization": f"Basic {encoded}"}

@router.post("/initiate-payment")
async def initiate_payment():
    # Generate unique reference
    transaction_ref = f"ARTRACER-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Create payment request
    payload = {
        "amount": 5000,  # ₦5000 Naira (adjust as needed)
        "customerName": "AR Tracer User",
        "customerEmail": "user@example.com",
        "paymentReference": transaction_ref,
        "paymentDescription": "1-month AR Tracer Subscription",
        "currencyCode": "NGN",
        "contractCode": CONTRACT_CODE,
        "redirectUrl": "https://yourdomain.com/payment-success",
        "paymentMethods": ["CARD", "ACCOUNT_TRANSFER"]
    }
    
    response = requests.post(
        f"{BASE_URL}/api/v1/merchant/transactions/init-transaction",
        json=payload,
        headers=get_auth_header()
    )
    
    if response.status_code == 200:
        return response.json()  # Contains payment URL
    return {"error": "Payment initiation failed"}
