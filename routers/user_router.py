import os
import shutil
from typing import Dict, List, Optional
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel
from services.churn_service import calculate_churn_risk
from database import db
from services.persona_service import build_user_features
from services.tags_service import build_tags
from firebase_admin import firestore
from datetime import datetime, timezone
import cloudinary.uploader

router = APIRouter(prefix="/api", tags=["Users"])

class ProfileUpdate(BaseModel):
    user_id: str
    name: str = None
    phone: str = None
    address: str = None
    avatar: str = None

class InteractionRequest(BaseModel):
    user_id: str
    product_id: str
    interaction_type: str
    timestamp: Optional[int] = None

class UserUpdate(BaseModel):
    fullName: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    avatar: Optional[str] = None

class UserPersona(BaseModel):
    user_id: str
    total_spent: float
    order_count: int
    avg_order_value: float
    favorite_categories: Dict[str, float]
    tags: List[str]
    churn_risk: str

@router.get("/users")
def get_all_users():
    docs = db.collection('users').stream()
    users = []
    for doc in docs:
        data = doc.to_dict()
        data['id'] = doc.id
        if 'password' in data: del data['password']
        users.append(data)
    return {"data": users}

@router.put("/{user_id}/status")
def toggle_user_status(user_id: str, is_active: bool):
    user_ref = db.collection('users').document(user_id)
    
    if not user_ref.get().exists:
        raise HTTPException(status_code=404, detail="User not found")
        
    user_ref.update({"isActive": is_active})
    return {"message": "Status updated successfully", "isActive": is_active}

@router.put("/users/{user_id}")
def update_user_profile(user_id: str, data: UserUpdate):
    user_ref = db.collection('users').document(user_id)

    if not user_ref.get().exists:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = {k: v for k, v in data.dict().items() if v is not None}

    if update_data:
        user_ref.update(update_data)

    return {
        "message": "User updated successfully",
        "data": update_data
    }

@router.put("/profile/update")
def update_profile(profile: ProfileUpdate):
    try:
        data = {k: v for k, v in profile.dict().items() if v and k != 'user_id'}
        if not data: return {"status": "no_change"}
        db.collection('users').document(profile.user_id).set(data, merge=True)
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@router.get("/orders/{user_id}")
def get_order_history(user_id: str):
    try:
        orders = db.collection('orders').where('userId', '==', user_id)\
                   .order_by('createdAt', direction='DESCENDING').stream()
        return {"orders": [o.to_dict() for o in orders]}
    except Exception as e: return {"error": str(e)}

UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

@router.post("/users/{user_id}/avatar")
async def upload_avatar(user_id: str, file: UploadFile = File(...)):
    user_ref = db.collection("users").document(user_id)

    if not user_ref.get().exists:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        # Upload lên Cloudinary
        result = cloudinary.uploader.upload(
            file.file,
            folder="avatars",
            public_id=f"user_{user_id}",
            overwrite=True,
            resource_type="image"
        )

        avatar_url = result["secure_url"]

        # Lưu URL vào Firestore
        user_ref.update({
            "avatar": avatar_url
        })

        return {
            "status": "success",
            "avatar": avatar_url
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/users/{user_id}/persona")
def get_user_persona(user_id: str):
    features = build_user_features(user_id)

    tags = build_tags(
        features["total_spent"],
        features["order_count"],
        features["favorite_categories"]
    )

    risk = calculate_churn_risk(
        user_id,
        features["total_spent"],
        features["order_count"]
    )

    top_favorites = features.get("top_items", [])[:3]

    ai_recommendations = []
    if risk == "High":
        ai_recommendations.append(f"Send a {(features['avg_order'] * 0.15):.0f} VND discount coupon")
        ai_recommendations.append("Prioritize customer support for next interaction")
    elif features["total_spent"] > 5000000:
        ai_recommendations.append("Promote to VIP Membership tier")
        ai_recommendations.append("Upsell premium bundle products")
    
    if features["favorite_categories"]:
        fav_cat = max(features["favorite_categories"], key=features["favorite_categories"].get)
        ai_recommendations.append(f"Notify about new stock in '{fav_cat}' category")

    now = datetime.now(timezone.utc)

    persona = {
        "user_id": user_id,
        "total_spent": features["total_spent"],
        "order_count": features["order_count"],
        "avg_order_value": features["avg_order"],
        "favorite_categories": features["favorite_categories"],
        "tags": tags,
        "churn_risk": risk,
        "top_favorites": top_favorites,
        "ai_recommendations": ai_recommendations,
        "updatedAt": now
    }

    db.collection("user_persona").document(user_id).set({
        **persona,
        "updatedAt": firestore.SERVER_TIMESTAMP
    })

    return persona