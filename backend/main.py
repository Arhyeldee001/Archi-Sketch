import os
import base64
import requests
import json
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, Request, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from pathlib import Path
from pydantic import BaseModel
from backend.db import SessionLocal, init_db
from backend.models import User
from backend.utils import hash_password
from backend.auth import register_user, login_user
from backend import models
from backend.routes import admin
from backend.monnify import router as monnify_router

# Init FastAPI app
app = FastAPI()

# Mount static files and include routers
app.include_router(monnify_router)
app.include_router(admin.router)
static_path = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database init
init_db()

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Models
class AuthData(BaseModel):
    email: str
    password: str

class UserRegistration(BaseModel):
    fullname: str
    phone: str
    email: str
    password: str

class SubscriptionData(BaseModel):
    email: str
    expiry_date: str

# Subscription storage file path
SUBSCRIPTIONS_FILE = "subscriptions.txt"

# ===== Middleware ===== #
@app.middleware("http")
async def check_subscription(request: Request, call_next):
    if request.url.path in ["/", "/onboarding", "/login", "/dashboard.html", "/api/register", "/api/login", "/initiate-payment", "/payment-success", "/static"]:
        return await call_next(request)
    
    if request.url.path.startswith("/ar"):
        email = request.cookies.get("user_email")
        if not email:
            return RedirectResponse(url="/onboarding?payment_required=true")
        
        try:
            with open(SUBSCRIPTIONS_FILE, "r") as f:
                for line in f:
                    if email in line:
                        parts = line.strip().split(',')
                        if len(parts) == 2:
                            expiry = datetime.fromisoformat(parts[1])
                            if expiry > datetime.now():
                                return await call_next(request)
        except FileNotFoundError:
            pass
        
        return RedirectResponse(url="/onboarding?payment_required=true")
    
    return await call_next(request)

# ===== Payment Endpoint ===== #
@app.get("/payment-success")
async def payment_success(
    request: Request,
    transaction_ref: str = Query(...),
    email: str = Query(...),
    db: Session = Depends(get_db)
):
    try:
        auth_str = f"{os.getenv('MONNIFY_API_KEY')}:{os.getenv('MONNIFY_SECRET_KEY')}"
        encoded = base64.b64encode(auth_str.encode()).decode()
        headers = {"Authorization": f"Basic {encoded}"}
        
        response = requests.get(
            f"https://api.monnify.com/api/v2/transactions/{transaction_ref}",
            headers=headers
        )
        
        if response.status_code == 200:
            transaction_data = response.json()
            if transaction_data['responseBody']['paymentStatus'] == "PAID":
                expiry_date = datetime.now() + timedelta(days=30)
                expiry_str = expiry_date.isoformat()
                
                with open(SUBSCRIPTIONS_FILE, "a") as f:
                    f.write(f"{email},{expiry_str}\n")
                
                user = db.query(User).filter(User.email == email).first()
                if user:
                    user.has_subscription = True
                    db.commit()
                
                response = RedirectResponse(url="/dashboard.html?payment=success")
                response.set_cookie(
                    key="user_email",
                    value=email,
                    max_age=30*24*60*60,
                    httponly=True
                )
                return response
    
    except Exception as e:
        print(f"Payment verification error: {e}")
    
    return RedirectResponse(url="/onboarding?payment=failed")

# ===== Auth Endpoints ===== #
@app.post("/api/register")
def register(user_data: UserRegistration, db: Session = Depends(get_db)):
    hashed_password = hash_password(user_data.password)
    user = User(
        fullname=user_data.fullname,
        phone=user_data.phone,
        email=user_data.email,
        hashed_password=hashed_password,
        is_first_login=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "message": "User registered successfully",
        "user_id": user.id,
        "redirect_to": f"/onboarding?user_id={user.id}"
    }

@app.post("/api/login")
def login(payload: AuthData, db: Session = Depends(get_db)):
    user = login_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if user.is_first_login:
        return {
            "message": "Login successful - redirect to onboarding",
            "user_id": user.id,
            "redirect_to": f"/onboarding?user_id={user.id}"
        }
    return {
        "message": "Login successful",
        "user_id": user.id,
        "redirect_to": "/dashboard.html"  # Changed to dashboard
    }

@app.post("/complete-onboarding")
async def complete_onboarding(request: Request, response: Response, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        user_id = data.get("user_id")
        
        if not user_id:
            return {"status": "error", "message": "user_id required"}
            
        db.query(User).filter(User.id == user_id).update({"is_first_login": False})
        db.commit()
        
        response = RedirectResponse(url="/dashboard.html")  # Redirect to dashboard
        response.set_cookie(
            key="session_token",
            value=f"session_{user_id}",
            max_age=31536000,
            httponly=True,
            secure=False,
            samesite='lax'
        )
        return response
        
    except json.JSONDecodeError:
        return {"status": "error", "message": "Invalid JSON"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ===== Frontend Routes ===== #
@app.get("/")
def root(request: Request, db: Session = Depends(get_db)):
    if request.cookies.get("session_token"):
        return RedirectResponse(url="/dashboard.html")  # Changed to dashboard
    return RedirectResponse(url="/onboarding")

@app.get("/dashboard.html", response_class=HTMLResponse)
def serve_dashboard(request: Request, db: Session = Depends(get_db)):
    if not request.cookies.get("session_token"):
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/onboarding", response_class=HTMLResponse)
def show_onboarding(request: Request, db: Session = Depends(get_db)):
    user_id = request.query_params.get("user_id")
    payment_required = request.query_params.get("payment_required")
    
    context = {
        "request": request,
        "user_id": user_id,
        "payment_required": payment_required == "true"
    }
    return templates.TemplateResponse("onboarding.html", context)

@app.get("/login", response_class=HTMLResponse)
def serve_login():
    return FileResponse("templates/login.html")

@app.get("/ar", response_class=HTMLResponse)
def serve_ar(request: Request):
    if not request.cookies.get("session_token"):
        return RedirectResponse(url="/login")
    
    template_id = request.query_params.get("template")
    payment_status = request.query_params.get("payment")
    
    with open("index.html", "r", encoding="utf-8") as f:
        content = f.read()
    
    if template_id:
        content = content.replace('<body>', f'<body data-template="{template_id}">')
    
    return HTMLResponse(content)

@app.get("/admin", response_class=HTMLResponse)
def show_admin_dashboard(request: Request):
    if not request.cookies.get("session_token"):
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("admin_users.html", {"request": request})

@app.get("/templates", response_class=HTMLResponse)
def template_gallery(request: Request):
    if not request.cookies.get("session_token"):
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("templates.html", {"request": request})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True
    )
