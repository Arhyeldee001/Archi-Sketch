import os
from dotenv import load_dotenv
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
from backend.models import User, Subscription
from backend.utils import hash_password
from backend.auth import register_user, login_user
from backend import models
from backend.routes import admin
from backend.paystack import router as paystack_router
from fastapi import Cookie
import random, string, re
from passlib.context import CryptContext
from pydantic import EmailStr
from fastapi import BackgroundTasks
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ===== EMAIL CONFIG ===== #


load_dotenv()

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
# Init FastAPI app
app = FastAPI()

# Mount static files and include routers
app.include_router(paystack_router)
app.include_router(admin.router)

static_dir = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory="static", check_dir=False), name="static")

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

otp_store = {}
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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
    email: EmailStr
    password: str

class SubscriptionData(BaseModel):
    email: str
    expiry_date: str

# Subscription storage file path
SUBSCRIPTIONS_FILE = "subscriptions.txt"

def send_email_otp(recipient_email: str, otp_code: str):
    """Send OTP via email using SMTP"""
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_SENDER
        msg["To"] = recipient_email
        msg["Subject"] = "Your Archi Trace OTP Code"

        body = f"""
        <html>
            <body>
                <h2 style="color:#764ba2;">Archi Trace Verification</h2>
                <p>Use this One-Time Password (OTP) to complete your registration:</p>
                <h1 style="color:#764ba2;">{otp_code}</h1>
                <p>This code will expire in 5 minutes.</p>
            </body>
        </html>
        """
        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        print(f"📧 OTP email sent to {recipient_email}")
    except Exception as e:
        print(f"❌ Failed to send email OTP: {e}")

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
@app.post("/api/send-otp")
async def send_otp(
    user_data: UserRegistration,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    # Check if email or phone already registered
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(User).filter(User.phone == user_data.phone).first():
        raise HTTPException(status_code=400, detail="Phone already registered")

    # Validate password strength
    # Validate password strength
    password_pattern = re.compile(
        r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$"
    )

    if not password_pattern.match(user_data.password):
        raise HTTPException(
            status_code=400,
            detail="Password must have at least 8 characters, including uppercase, lowercase, number, and special symbol"
        )

    otp = ''.join(random.choices(string.digits, k=6))
    otp_store[user_data.email] = {
        "otp": otp,
        "expires_at": datetime.now() + timedelta(minutes=5),
        "pending_user": {
            "fullname": user_data.fullname,
            "email": user_data.email,
            "phone": user_data.phone,
            "hashed_password": pwd_context.hash(user_data.password),
        }
    }

    # Send OTP in background (non-blocking)
    background_tasks.add_task(send_email_otp, user_data.email, otp)

    print(f"📨 OTP for {user_data.email}: {otp}")
    return {"status": "success", "message": "OTP sent successfully"}

@app.post("/api/check-password")
async def check_password(request: Request):
    """Live password strength checker"""
    body = await request.json()
    password = body.get("password")

    # Define password strength pattern
    password_pattern = re.compile(
        r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$"
    )

    # Check each rule
    has_length = len(password) >= 8
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_symbol = any(c in "@$!%*?&" for c in password)

    is_strong = password_pattern.match(password) is not None

    return {
        "valid": is_strong,
        "rules": {
            "length": has_length,
            "uppercase": has_upper,
            "lowercase": has_lower,
            "number": has_digit,
            "symbol": has_symbol
        }
    }

@app.post("/api/verify-otp")
async def verify_otp(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    email = body.get("email")
    otp = body.get("otp")

    if email not in otp_store:
        raise HTTPException(status_code=400, detail="No pending OTP for this email")

    record = otp_store[email]
    if record["otp"] != otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    if datetime.now() > record["expires_at"]:
        del otp_store[email]
        raise HTTPException(status_code=400, detail="OTP expired")

    user_data = record["pending_user"]
    new_user = User(
        fullname=user_data["fullname"],
        email=user_data["email"],
        phone=user_data["phone"],
        hashed_password=user_data["hashed_password"],
        is_first_login=True
    )

    db.add(new_user)
    db.commit()
    del otp_store[email]

    return {"status": "success", "message": "Account created successfully"}
    
@app.post("/api/resend-otp")
async def resend_otp(request: Request):
    body = await request.json()
    phone = body.get("phone")

    if phone not in otp_store:
        raise HTTPException(status_code=404, detail="No pending registration for this phone")

    new_otp = ''.join(random.choices(string.digits, k=6))
    otp_store[phone]["otp"] = new_otp
    otp_store[phone]["expires_at"] = datetime.now() + timedelta(minutes=5)

    print(f"🔁 Resent OTP for {phone}: {new_otp}")
    return {"status": "resent", "message": "OTP resent successfully"}  
    
# ===== Login (phone-based) =====
@app.post("/api/login")
def login(response: Response, payload: dict, db: Session = Depends(get_db)):
    phone = payload.get("phone")
    password = payload.get("password")

    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        raise HTTPException(status_code=401, detail="Phone not registered")

    if not pwd_context.verify(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid password")

    response = JSONResponse({
        "message": "Login successful",
        "redirect_to": f"/onboarding?user_id={user.id}" if user.is_first_login else "/dashboard.html",
        "user_id": str(user.id),
        "email": user.email
    })

    # Set cookies
    response.set_cookie("session_token", f"session_{user.id}", max_age=31536000, httponly=True, secure=True, samesite="Lax", path="/")
    response.set_cookie("user_email", user.email, max_age=31536000, path="/")

    return response
    

@app.post("/complete-onboarding")
async def complete_onboarding(
    request: Request,
    user_id: str = Form(...),
    db: Session = Depends(get_db)
):
    """Endpoint to complete onboarding flow"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Mark onboarding as complete
        user.is_first_login = False
        db.commit()
        
        # Redirect directly to dashboard with authenticated session
        response = RedirectResponse(url="/dashboard.html", status_code=303)
        
        # Set both cookies (session + email)
        response.set_cookie(
            key="session_token",
            value=f"session_{user_id}",
            max_age=31536000,  # 1 year
            httponly=True,
            secure=True,
            samesite='lax',
            path='/'
        )
        response.set_cookie(
            key="user_email",
            value=user.email,
            max_age=31536000,
            path='/'
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# ===== Frontend Routes ===== #
@app.get("/")
def root(request: Request):
    """Root route — used by PWA start_url ("/")"""
    session_token = request.cookies.get("session_token")
    user_email = request.cookies.get("user_email")

    if session_token and user_email:
        # ✅ Logged-in user → go to dashboard
        return RedirectResponse(url="/dashboard.html")
    else:
        # 🧭 Not logged in → go to onboarding/login
        return RedirectResponse(url="/login")
        
@app.get("/dashboard.html", response_class=HTMLResponse)
def dashboard(request: Request):
    """Main dashboard route"""
    if not request.cookies.get("session_token"):
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/tutorials.html", response_class=HTMLResponse)
def tutorials(request: Request):
    """Tutorials route"""
    return templates.TemplateResponse("tutorials.html", {"request": request})

@app.get("/accounts.html", response_class=HTMLResponse)
def accounts(request: Request):
    """accounts route"""
    return templates.TemplateResponse("accounts.html", {"request": request})


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
async def check_access(
    request: Request,
    db: Session = Depends(get_db),
    user_email: str = Cookie(None)
):
    """Check if logged-in user has an active subscription"""
    try:
        if not user_email:
            return {"has_access": False, "reason": "No user email in cookies"}
        
        active_sub = db.query(Subscription).filter(
            Subscription.user_email == user_email,
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
    # Public routes
    PUBLIC_ROUTES = [
        "/", "/login", "/api/login", "/api/register",
        "/payment", "/payment-success", "/static"
    ]
    
    if request.url.path in PUBLIC_ROUTES:
        return await call_next(request)
    
    # Verify authentication
    session_token = request.cookies.get("session_token")
    user_email = request.cookies.get("user_email") or request.query_params.get("email")
    
    if not (session_token and user_email):
        return RedirectResponse(url="/login")
    
    # AR route specific checks
    if request.url.path.startswith("/ar"):
        db = SessionLocal()
        try:
            active_sub = db.query(Subscription).filter(
                Subscription.user_email == user_email,
                Subscription.expiry_date > datetime.now()
            ).first()
            
            if not active_sub:
                return RedirectResponse(url="/payment")
        except Exception as e:
            print(f"Subscription check error: {str(e)}")
            return RedirectResponse(url="/payment")
        finally:
            db.close()
    
    return await call_next(request)

@app.get("/payment")
async def payment_page(request: Request):
    return templates.TemplateResponse("payment.html", {"request": request})


@app.post("/api/payment-success")
async def payment_success(
    request: Request, 
    db: Session = Depends(get_db),
    user_email: str = Cookie(None)
):
    try:
        data = await request.json()

        if not user_email:
            raise HTTPException(status_code=400, detail="User email not found in cookies")

        # Get or create subscription entry
        subscription = db.query(Subscription).filter(
            Subscription.user_email == user_email
        ).first()

        if subscription:
            # Renew or update existing subscription
            subscription.is_active = True
            subscription.start_date = datetime.now()
            subscription.expiry_date = datetime.now() + timedelta(days=30)
        else:
            # Create new subscription entry
            subscription = Subscription(
                user_email=user_email,
                is_active=True,
                start_date=datetime.now(),
                expiry_date=datetime.now() + timedelta(days=30)
            )
            db.add(subscription)

        db.commit()
        db.refresh(subscription)

        return {
            "status": "success",
            "message": "Subscription activated",
            "expiry": subscription.expiry_date.isoformat()
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing payment: {e}")
        

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






