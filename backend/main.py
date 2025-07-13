import os
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from pydantic import BaseModel
from .template_handler import router as template_router  # Note the dot prefix

from backend.db import SessionLocal, init_db
from backend.models import User
from backend.utils import hash_password
from backend.auth import register_user, login_user
from backend import models
from backend.routes import admin  # Admin route import
import json  # Add at top of file

# Init FastAPI app
app = FastAPI()

# ↓ Add these 2 lines right after app creation ↓
app.mount("/static", StaticFiles(directory="../static"), name="static")  # Adjusted path
app.include_router(template_router)

# Templates
templates = Jinja2Templates(directory="templates")

# CORS (open access for now)
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

# Auth payload model
class AuthData(BaseModel):
    email: str
    password: str

# User registration model
class UserRegistration(BaseModel):
    fullname: str
    phone: str
    email: str
    password: str

# API Endpoints
@app.post("/api/register")
def register(user_data: UserRegistration, db: Session = Depends(get_db)):
    hashed_password = hash_password(user_data.password)

    user = User(
        fullname=user_data.fullname,
        phone=user_data.phone,
        email=user_data.email,
        hashed_password=hashed_password,
        is_first_login=True  # Mark as first-time user
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
    email = payload.email
    password = payload.password
    user = login_user(db, email, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    print(f"LOGIN 🚨 User {user.id} first login: {user.is_first_login}")
    
    if user.is_first_login:
        return {
            "message": "Login successful - redirect to onboarding",
            "user_id": user.id,
            "redirect_to": f"/onboarding?user_id={user.id}"
        }
    return {
        "message": "Login successful",
        "user_id": user.id,
        "redirect_to": "/dashboard"
    }


@app.post("/complete-onboarding")
async def complete_onboarding(request: Request, response: Response, db: Session = Depends(get_db)):
    try:
        # Add error handling for JSON parsing
        data = await request.json()
        user_id = data.get("user_id")
        
        if not user_id:
            print("⚠️ No user_id received in request")
            return {"status": "error", "message": "user_id required"}
            
        # Update user status
        db.query(User).filter(User.id == user_id).update({"is_first_login": False})
        db.commit()
        
        # Set cookies
        session_token = f"session_{user_id}"  # Simple token for testing
        response.set_cookie(
            key="session_token",
            value=session_token,
            max_age=31536000,
            httponly=True,
            secure=False,  # Disable for local testing
            samesite='lax'
        )
        response.set_cookie(
            key="onboarding_complete",
            value="true",
            max_age=31536000,
            httponly=True,
            secure=False,  # Disable for local testing
            samesite='lax'
        )
        
        print(f"✅ Onboarding completed for user {user_id}")
        return {"status": "success", "session_token": session_token}
        
    except json.JSONDecodeError:
        print("❌ Invalid JSON received")
        return {"status": "error", "message": "Invalid JSON"}
    except Exception as e:
        print(f"❌ Server error: {str(e)}")
        return {"status": "error", "message": "Server error"}
    
# Static Files
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
static_dir = os.path.join(BASE_DIR, "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Include admin router
app.include_router(admin.router)

# Frontend Routes
@app.get("/")
def root(request: Request, db: Session = Depends(get_db)):
    # First check session token cookie
    if request.cookies.get("session_token"):
        return RedirectResponse(url="/login")
    
    # Then check user_id cookie (your existing check)
    user_id = request.cookies.get("user_id")
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if user and not user.is_first_login:
            return RedirectResponse(url="/ar")
    
    # Fallback to onboarding
    return RedirectResponse(url="/onboarding")

@app.get("/onboarding", response_class=HTMLResponse)
def show_onboarding(request: Request, db: Session = Depends(get_db)):
    user_id = request.query_params.get("user_id")
    
    if user_id:  # Coming from registration/login
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return RedirectResponse(url="/login")
        
        print(f"ONBOARDING 🚨 User {user.id} first login status: {user.is_first_login}")
        
        if not user.is_first_login:
            return RedirectResponse(url="/ar")
        
        return templates.TemplateResponse("onboarding.html", {
            "request": request,
            "user_id": user_id
        })
    
    # Coming from root as new visitor
    return templates.TemplateResponse("onboarding.html", {
        "request": request,
        "user_id": None  # No user associated yet
    })

@app.get("/login", response_class=HTMLResponse)
def serve_login():
    login_path = os.path.join(BASE_DIR, "templates", "login.html")
    with open(login_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/ar", response_class=HTMLResponse)
def serve_ar(request: Request):
    template_id = request.query_params.get("template")
    
    # Read your existing index.html
    index_path = os.path.join(BASE_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Inject template ID into the page (optional)
    if template_id:
        content = content.replace(
            '<body>', 
            f'<body data-template="{template_id}">'
        )
    
    return HTMLResponse(content)

@app.get("/admin", response_class=HTMLResponse)
def show_admin_dashboard(request: Request):
    return templates.TemplateResponse("admin_users.html", {"request": request})

# Onboarding image endpoint
@app.get("/onboarding-image")
def get_onboarding_image():
    return FileResponse("static/onboarding/onboarding1.jpg")

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})
# Add new route for templates
@app.get("/templates", response_class=HTMLResponse)
def template_gallery(request: Request):
    return templates.TemplateResponse("templates.html", {"request": request})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True
    )
