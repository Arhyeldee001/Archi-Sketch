import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()

# Test mode configuration
TEST_MODE = os.getenv("TEST_MODE", "true").lower() == "true"

@router.post("/initiate-payment")
async def initiate_payment(request: Request):
    data = await request.json()
    email = data.get("email")
    immediate = data.get("immediate", False)
    
    if not email:
        raise HTTPException(status_code=400, detail="Email required")

    if TEST_MODE:
        if not immediate:
            # Grant trial without payment
            return JSONResponse({
                "status": "success",
                "trial_active": True,
                "expires_in": 24  # 1 day trial
            })
        else:
            # Simulate payment response
            return JSONResponse({
                "responseBody": {
                    "checkoutUrl": "https://sandbox.monnify.com/test-checkout"
                }
            })
    
    # Production implementation would go here
    raise HTTPException(status_code=501, detail="Production payment not implemented yet")

@router.get("/api/check-subscription")
async def check_subscription():
    # For testing, always return no subscription
    return JSONResponse({
        "hasAccess": False,
        "expiryDate": None
    })
