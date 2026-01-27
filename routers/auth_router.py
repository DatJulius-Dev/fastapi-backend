from difflib import restore
import random
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import requests
from database import db
from passlib.context import CryptContext
from firebase_admin import auth
import uuid
import time
import google.cloud.firestore as firestore

router = APIRouter(prefix="", tags=["Authentication"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    fullName: str = None
    address: str = ""
    phone: str = ""

class ChangePasswordRequest(BaseModel):
    id: str
    oldPassword: str
    newPassword: str

class ResetPasswordRequest(BaseModel):
    id: str
    newPassword: str

@router.post("/login")
def login(creds: LoginRequest):
    clean_email = creds.email.strip().lower()
    clean_password = creds.password.strip()

    users_ref = db.collection('users').where('email', '==', clean_email).stream()
    user_doc = next(users_ref, None)
    
    if not user_doc:
        raise HTTPException(status_code=400, detail="Email does not exist")
    
    user_data = user_doc.to_dict()
    stored_password = user_data.get('password')

    if stored_password != clean_password:
        raise HTTPException(status_code=400, detail="Incorrect password")
    
    return {
        "access_token": f"token-{uuid.uuid4()}",
        "user_id": str(user_doc.id), 
        "name": user_data.get('name'),
        "token_type": "bearer"
    }

@router.post("/register")
def register(req: RegisterRequest):
    clean_email = req.email.strip().lower()
    clean_password = req.password.strip()
    clean_name = req.name.strip()

    try:
        firebase_user = auth.create_user(
            email=clean_email,
            password=clean_password,
            display_name=clean_name,
            phone_number=req.phone if req.phone else None
        )
        
        user_id = firebase_user.uid 
        now = int(time.time())

        user_data = {
            "id": user_id,
            "email": clean_email,
            "name": clean_name,
            "fullName": clean_name,
            "phone": req.phone,
            "address": req.address,
            "avatar": f"https://i.pravatar.cc/150?u={user_id}",
            "role": "user",
            "isActive": True,
            "loyaltyPoints": 0,
            "orderCount": 0,
            "totalSpent": 0,
            "createdAt": now,
            "updatedAt": now
        }

        db.collection("users").document(user_id).set(user_data)

        return {
            "status": "success",
            "user_id": user_id,
            "message": "User successfully created in Auth and Firestore"
        }

    except auth.EmailAlreadyExistsError:
        raise HTTPException(status_code=400, detail="Email is already registered in the system")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/api/change-password")
def change_password(req: ChangePasswordRequest):
    try:
        doc_ref = db.collection("users").document(req.id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="TThis user can't find in Firebase!")
        
        user_data = doc.to_dict()
        stored_password = user_data.get("password")
        
        if stored_password != req.oldPassword:
            raise HTTPException(status_code=400, detail="Incorrect password!")
        
        doc_ref.update({
            "password": req.newPassword
        })

        return {"message": "New Password updated successfully!"}

    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/api/reset-password")
def reset_password(req: ResetPasswordRequest):
    if not req.id or req.id.strip() == "":
        raise HTTPException(status_code=400, detail="User ID is required and cannot be empty")

    try:
        user_id = req.id.strip()
        doc_ref = db.collection("users").document(user_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail=f"User with ID {user_id} not found!")
        
        doc_ref.update({
            "password": req.newPassword,
            "updatedAt": firestore.SERVER_TIMESTAMP
        })

        return {"message": "Password reset successfully!"}

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Server error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
    
@router.post("/api/send-otp")
def send_otp(email: str):
    otp = str(random.randint(1000, 9999))
    db.collection("otps").document(email).set({
        "code": otp,
        "createdAt": firestore.SERVER_TIMESTAMP
    })
    return {"message": "OTP sent successfully", "otp": otp}

@router.post("/api/check-user-email")
async def check_user_email(req: Request):
    try:
        body = await req.json()
        email_input = body.get("email", "").strip().lower()

        if not email_input:
            raise HTTPException(status_code=400, detail="Email is required")

        users_ref = db.collection("users")
        query = users_ref.where("email", "==", email_input).limit(1).get()

        if not query:
            raise HTTPException(status_code=404, detail="User not found")

        user_doc = query[0]
        user_data = user_doc.to_dict()

        return {
            "status": "success",
            "userId": user_doc.id,
            "userName": user_data.get("full_name") or user_data.get("userName") or "User",
            "email": user_data.get("email")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))