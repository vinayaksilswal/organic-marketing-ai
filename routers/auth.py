from fastapi import APIRouter, Request, Form, Response, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from config import settings
from auth import create_access_token
import secrets
import jwt

router = APIRouter(tags=["Authentication"])
templates = Jinja2Templates(directory="templates")

@router.get("/admin/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")

@router.post("/admin/login")
async def login(response: Response, username: str = Form(...), password: str = Form(...)):
    correct_username = secrets.compare_digest(
        username.encode("utf8"), settings.admin_username.encode("utf8")
    )
    correct_password = secrets.compare_digest(
        password.encode("utf8"), settings.admin_password.encode("utf8")
    )
    
    if not (correct_username and correct_password):
        # Redirect back to login with error
        return RedirectResponse(url="/admin/login?error=1", status_code=303)
        
    token = create_access_token(data={"sub": username})
    
    redirect = RedirectResponse(url="/admin", status_code=303)
    redirect.set_cookie(
        key="admin_session",
        value=token,
        httponly=True,
        max_age=86400, # 1 day
        samesite="lax",
        secure=(settings.environment == "production")
    )
    return redirect

def verify_user(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id: str = payload.get("sub")
        token_type = payload.get("type")
        if not user_id or token_type != "user":
            raise HTTPException(status_code=401, detail="Invalid user session")
        return user_id
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid session")

@router.get("/admin/logout")
async def logout():
    redirect = RedirectResponse(url="/admin/login", status_code=303)
    redirect.delete_cookie("admin_session")
    return redirect

from pydantic import BaseModel
from typing import Optional
import bcrypt

class UserRegister(BaseModel):
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

@router.post("/api/v1/auth/register")
async def api_register(data: UserRegister, request: Request):
    if hasattr(request.app.state, "prisma_error"):
        return {"success": False, "message": f"CRITICAL: Prisma failed to initialize on server startup: {request.app.state.prisma_error}"}
    
    try:
        prisma = request.app.state.prisma
        existing = await prisma.user.find_unique(where={"email": data.email})
    if existing:
        return {"success": False, "message": "Email already registered"}
    
    hashed = bcrypt.hashpw(data.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user = await prisma.user.create(data={"email": data.email, "password": hashed})
    token = create_access_token(data={"sub": user.id, "type": "user"})
    return {"success": True, "token": token, "user": {"id": user.id, "email": user.email}}

@router.post("/api/v1/auth/login")
async def api_login(data: UserLogin, request: Request):
    if hasattr(request.app.state, "prisma_error"):
        return {"success": False, "message": f"CRITICAL: Prisma failed to initialize on server startup: {request.app.state.prisma_error}"}

    try:
        prisma = request.app.state.prisma
        user = await prisma.user.find_unique(where={"email": data.email})
    if not user or not bcrypt.checkpw(data.password.encode("utf-8"), user.password.encode("utf-8")):
        return {"success": False, "message": "Invalid email or password"}
    
    token = create_access_token(data={"sub": user.id, "type": "user"})
    return {"success": True, "token": token, "user": {"id": user.id, "email": user.email}}
