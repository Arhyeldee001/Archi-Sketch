import os
import base64
import requests
import json
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, Request, Response, Query, Form
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
from backend.paystack import router as paystack_router

# Init FastAPI app
app = FastAPI()

# Mount static files and include routers
app.include_router(paystack_router)
app.include_router(admin.router)

# IMPORTANT: Render.com specific static files setup
static_dir = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# CORS - Updated for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://archisketch.onrender.com",
        "http://archisketch.onrender.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database init
init_db()

# ======== ADD THESE LINES ======== #
def initialize_data():
    """Create tables and add test data if empty"""
    from backend.models import Base
    from sqlalchemy import create_engine
    
    # 1. Force-create all tables
    engine = create_engine(os.getenv("DATABASE_URL"))
    Base.metadata.create_all(bind=engine)
    
    # 2. Optional: Add test user if none exists
    db = SessionLocal()
    try:
        if not db.query(User).first():
            test_user = User(
                fullname="Test User",
                email="test@example.com",
                hashed_password=hash_password("test123"),
                phone="08012345678",
                is_first_login=True,
                used_trial=False
            )
            db.add(test_user)
            db.commit()
            print("✅ Created test user")
    except Exception as e:
        print(f"❌ Initialization error: {e}")
    finally:
        db.close()


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
async def auth_middleware(request: Request, call_next):
    # Skip auth for these paths
    public_paths = [
        "/", "/login", "/api/login", "/api/register", 
        "/static", "/onboarding", "/onboarding/images",
        "/complete-onboarding"
    ]
    
    if request.url.path in public_paths or request.url.path.startswith("/static"):
        return await call_next(request)
    
    # Check session cookie
    session_token = request.cookies.get("session_token")
    if not session_token:
        return RedirectResponse(url="/login")
    
    # Verify token format
    if not session_token.startswith("session_"):
        response = RedirectResponse(url="/login")
        response.delete_cookie("session_token")
        return response
    
    return await call_next(request)

# ===== Image Serving ===== #
@app.get("/static/onboarding/{image_name}")
async def serve_onboarding_image(image_name: str):
    """Serve onboarding images with proper caching headers"""
    image_path = static_dir / "onboarding" / image_name
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    
    response = FileResponse(image_path)
    response.headers["Cache-Control"] = "public, max-age=604800"  # 1 week cache
    return response

# Debug endpoint to verify static files
@app.get("/debug-static")
async def debug_static_files():
    """Endpoint to verify static files are properly deployed"""
    onboarding_path = static_dir / "onboarding"
    files = []
    
    if onboarding_path.exists():
        files = [f.name for f in onboarding_path.glob("*") if f.is_file()]
    
    return {
        "static_dir": str(static_dir),
        "onboarding_exists": onboarding_path.exists(),
        "onboarding_files": files
    }

# ===== Auth Endpoints ===== #
# ===== Auth Endpoints ===== #
@app.post("/api/login")
def login(response: Response, payload: AuthData, db: Session = Depends(get_db)):
    user = login_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Create redirect response
    if user.is_first_login:
        redirect_url = f"/onboarding?user_id={user.id}"
    else:
        redirect_url = "/dashboard.html"
    
    # Set cookies in response
    response = JSONResponse({
        "message": "Login successful",
        "redirect_to": redirect_url,
        "user_id": str(user.id),
        "email": user.email  # <-- Add this line to include email in response
    })
    
    response.set_cookie(
        key="session_token",
        value=f"session_{user.id}",
        max_age=31536000,  # 1 year
        httponly=True,
        secure=True,  # Must be True in production (HTTPS)
        samesite='lax',
        path='/'
    )
    
    return response
    
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
    return {
        "message": "User registered successfully",
        "redirect_to": f"/onboarding?user_id={user.id}",
        "user_id": str(user.id)
    }

@app.post("/complete-onboarding")
async def complete_onboarding(
    user_id: str = Form(...),
    db: Session = Depends(get_db)
):
    """Endpoint to complete onboarding flow"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user.is_first_login = False
        db.commit()
        
        response = RedirectResponse(url="/login?onboarding=success", status_code=303)
        response.set_cookie(
            key="session_token",
            value=f"session_{user_id}",
            max_age=31536000,
            httponly=True,
            secure=True,  # Must be True in production
            samesite='lax',
            path='/'
        )
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ===== Frontend Routes ===== #
@app.get("/")
def root(request: Request):
    if request.cookies.get("session_token"):
        return RedirectResponse(url="/dashboard.html")
    return RedirectResponse(url="/onboarding")

@app.get("/dashboard.html", response_class=HTMLResponse)
def dashboard(request: Request):
    """Main dashboard route"""
    if not request.cookies.get("session_token"):
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    """Login page with onboarding success message"""
    onboarding_success = request.query_params.get("onboarding") == "success"
    return templates.TemplateResponse("login.html", {
        "request": request,
        "onboarding_success": onboarding_success
    })

@app.get("/onboarding", response_class=HTMLResponse)
def onboarding(request: Request):
    """Onboarding flow entry point"""
    user_id = request.query_params.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login")
    
    return templates.TemplateResponse("onboarding.html", {
        "request": request,
        "user_id": user_id
    })

@app.get("/api/check-access")
async def check_access(db: Session = Depends(get_db)):
    """Endpoint to verify if user has active subscription"""
    try:
        # Get email from localStorage via frontend
        email = request.query_params.get("email")
        if not email:
            return {"has_access": False, "reason": "Email required"}
        
        # Check for active subscription
        active_sub = db.query(Subscription).filter(
            Subscription.user_email == email,
            Subscription.expiry_date > datetime.now(),
            Subscription.is_active == True
        ).first()
        
        if active_sub:
            return {
                "has_access": True,
                "expiry": active_sub.expiry_date.isoformat()
            }
        
        return {"has_access": False, "reason": "No active subscription"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.middleware("http")
async def check_subscription_middleware(request: Request, call_next):
    # Skip check for public routes
    if request.url.path in ["/login", "/api/login", "/api/register"]:
        return await call_next(request)
    
    # For AR routes
    if request.url.path.startswith("/ar"):
        email = request.query_params.get("email") or \
               (await request.json()).get("email", None)
        
        if not email:
            return RedirectResponse(url="/login")
        
        # Verify subscription
        db = SessionLocal()
        try:
            active_sub = db.query(Subscription).filter(
                Subscription.user_email == email,
                Subscription.expiry_date > datetime.now()
            ).first()
            
            if not active_sub:
                return RedirectResponse(url="/payment-required")
        finally:
            db.close()
    
    return await call_next(request)

# ===== AR Experience ===== #
@app.get("/ar", response_class=HTMLResponse)
def ar_viewer(request: Request):
    """AR experience entry point"""
    if not request.cookies.get("session_token"):
        return RedirectResponse(url="/login")
    return FileResponse("index.html")

# ===== Admin Routes ===== #
@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    if not request.cookies.get("session_token"):
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("admin_users.html", {"request": request})


# ===== Logout ===== #
@app.post("/api/logout")
def logout():
    """Logout endpoint"""
    response = RedirectResponse(url="/login")
    response.delete_cookie("session_token")
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)




