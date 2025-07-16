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
    allow_credentials=True,  # Critical for cookies
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
async def auth_middleware(request: Request, call_next):
    # Skip auth for these paths
    if request.url.path in ["/", "/login", "/api/login", "/api/register", "/static", "/onboarding"]:
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
        "redirect_to": redirect_url
    })
    
    response.set_cookie(
        key="session_token",
        value=f"session_{user.id}",
        max_age=31536000,  # 1 year
        httponly=True,
        secure=False,  # Set True in production with HTTPS
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
        "redirect_to": f"/onboarding?user_id={user.id}"
    }

@app.post("/complete-onboarding")
async def complete_onboarding(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        user_id = data.get("user_id")
        
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id required")
            
        db.query(User).filter(User.id == user_id).update({"is_first_login": False})
        db.commit()
        
        response = RedirectResponse(url="/dashboard.html", status_code=303)
        response.set_cookie(
            key="session_token",
            value=f"session_{user_id}",
            max_age=31536000,
            httponly=True,
            secure=False,
            samesite='lax',
            path='/'
        )
        return response
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

# ===== Frontend Routes ===== #
@app.get("/")
def root(request: Request):
    if request.cookies.get("session_token"):
        return RedirectResponse(url="/dashboard.html")
    return RedirectResponse(url="/onboarding")

@app.get("/dashboard.html", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
def login_page():
    return FileResponse("templates/login.html")

@app.get("/onboarding", response_class=HTMLResponse)
def onboarding(request: Request):
    user_id = request.query_params.get("user_id")
    return templates.TemplateResponse("onboarding.html", {
        "request": request,
        "user_id": user_id
    })

# ===== Other Routes ===== #
@app.get("/ar", response_class=HTMLResponse)
def ar_viewer(request: Request):
    if not request.cookies.get("session_token"):
        return RedirectResponse(url="/login")
    return FileResponse("index.html")

@app.post("/api/logout")
def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("session_token")
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
