from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import pyotp
from uuid import uuid4
from typing import Dict
from database import get_db, User
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["authentication"])

class LoginRequest(BaseModel):
    email: str
    password: str

class MFAVerifyRequest(BaseModel):
    email: str
    token: str

class MFASetupRequest(BaseModel):
    email: str

@router.post("/login")
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.mfa_enabled:
        mfa_token = create_mfa_token({"email": user.email})
        return {"mfa_required": True, "temp_token": mfa_token}

    return {"mfa_required": False, "token": "jwt_access_token", "user": {"email": user.email, "role": user.role}}

@router.post("/mfa-setup")
async def mfa_setup(req: MFASetupRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    secret = pyotp.random_base32()
    user.mfa_secret = secret
    db.commit()

    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(name=user.email, issuer_name="LandSync")

    return {"provisioning_uri": provisioning_uri}

@router.post("/mfa-verify")
async def mfa_verify(req: MFAVerifyRequest, db: Session = Depends(get_db)):
    # In a real app, we would verify the temp_token from header here
    # For now, we ensure the user exists and OTP is correct
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not user.mfa_secret:
        raise HTTPException(status_code=400, detail="MFA not set up")

    totp = pyotp.TOTP(user.mfa_secret)
    if not totp.verify(req.token):
        raise HTTPException(status_code=401, detail="Invalid OTP token")

    return {"status": "verified", "token": "jwt_access_token"}

@router.post("/mfa-enable")
async def mfa_enable(req: MFASetupRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.mfa_enabled = True
    db.commit()
    return {"status": "MFA enabled successfully"}
