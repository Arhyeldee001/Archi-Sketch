import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()

# Configuration
TEST_MODE = os.getenv("TEST_MODE", "true").lower() == "true"
TRIAL_DURATION_HOURS = 24  # 1 day trial
SUBSCRIPTION_DURATION_DAYS = 30  # 1 month paid

@router.post("/initiate-trial")
async def initiate_trial(request: Request):
    data = await request.json()
    email = data.get("email")
    
    if not email:
        raise HTTPException(status_code=400, detail="Email required")

    # Calculate expiry date
    expiry = datetime.now() + timedelta(hours=TRIAL_DURATION_HOURS)
    
    # In a real app, you would save this to your database
    return JSONResponse({
        "status": "success",
        "expiryDate": expiry.isoformat(),
        "message": f"Trial activated for {TRIAL_DURATION_HOURS} hours"
    })

@router.post("/initiate-payment")
async def initiate_payment(request: Request):
    data = await request.json()
    email = data.get("email")
    
    if not email:
        raise HTTPException(status_code=400, detail="Email required")

    if TEST_MODE:
        # Simulate payment response
        return JSONResponse({
            "checkoutUrl": "https://sandbox.monnify.com/checkout/test-transaction",
            "test_mode": True,
            "message": "Redirecting to Monnify sandbox"
        })
    
    # Production implementation
    # ... (your existing Monnify integration code)
    
    raise HTTPException(status_code=501, detail="Production payment not implemented")

@router.get("/api/check-subscription")
async def check_subscription():
    # This would normally check your database
    return JSONResponse({
        "hasAccess": False,
        "expiryDate": None
    })
