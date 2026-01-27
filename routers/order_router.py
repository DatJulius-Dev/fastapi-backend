from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime
from uuid import uuid4
from pydantic import BaseModel

import firebase_admin
from firebase_admin import credentials, firestore

from services.churn_service import calculate_churn_risk
from services.persona_service import build_user_features
from services.tags_service import build_tags

if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

class ImageModel(BaseModel):
    url: Optional[str] = None


class OrderItemCreate(BaseModel):
    productId: str
    productName: str
    quantity: int
    unitPrice: float
    discount: float = 0
    images: Optional[ImageModel] = None


class OrderItem(OrderItemCreate):
    pass


class OrderTracking(BaseModel):
    status: str
    date: datetime


class OrderCreate(BaseModel):
    userId: str
    address: str
    paymentMethod: str
    discount: int = 0
    loyaltyPointsUsed: int = 0
    items: List[OrderItemCreate]


class Order(BaseModel):
    id: str
    userId: str
    userName: str
    email: str
    address: str
    totalAmount: float
    discountAmount: float
    loyaltyPointsUsed: int
    loyaltyPointsEarned: float
    status: str
    paymentMethod: str
    paymentStatus: str
    items: List[OrderItem]
    orderTracking: List[OrderTracking]
    createdAt: datetime
    updatedAt: datetime

def update_user_persona(user_id: str):
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

    persona = {
        "user_id": user_id,
        "total_spent": features["total_spent"],
        "order_count": features["order_count"],
        "avg_order_value": features["avg_order"],
        "favorite_categories": features["favorite_categories"],
        "tags": tags,
        "churn_risk": risk,
        "updatedAt": firestore.SERVER_TIMESTAMP
    }

    db.collection("user_persona").document(user_id).set(persona)

router = APIRouter(prefix="/orders", tags=["Orders"])

@router.post("", response_model=Order)
def create_order(payload: OrderCreate):
    if not payload.userId:
        raise HTTPException(status_code=400, detail="userId is required")

    user_ref = db.collection("users").document(payload.userId).get()
    if not user_ref.exists:
        raise HTTPException(status_code=404, detail="User not found")

    user = user_ref.to_dict()
    user_name = user.get("name", "Guest")
    email = user.get("email", "")

    now = datetime.utcnow()
    order_id = str(uuid4())

    total_amount = sum(
        (item.unitPrice - item.discount) * item.quantity
        for item in payload.items
    )

    order_data = {
        "id": order_id,
        "userId": payload.userId,
        "userName": user_name,
        "email": email,
        "address": payload.address,
        "totalAmount": total_amount,
        "discountAmount": payload.discount,
        "loyaltyPointsUsed": payload.loyaltyPointsUsed,
        "loyaltyPointsEarned": round(total_amount * 0.01, 2),
        "status": "PENDING",
        "paymentMethod": payload.paymentMethod,
        "paymentStatus": "UNPAID",
        "items": [item.model_dump() for item in payload.items],
        "orderTracking": [
            {"status": "PENDING", "date": now}
        ],
        "createdAt": now,
        "updatedAt": now,
    }

    db.collection("orders").document(order_id).set(order_data)
    update_user_persona(payload.userId)
    return Order(**order_data)

@router.get("/history", response_model=List[Order])
def get_order_history(userId: str = Query(...)):
    try:
        docs = (
            db.collection("orders")
            .where("userId", "==", userId)
            .order_by("createdAt", direction=firestore.Query.DESCENDING)
            .stream()
        )

        orders = []

        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id

            mapped_items = []
            for item in data.get("items", []):
                mapped_items.append({
                    "productId": str(
                        item.get("productId")
                        or item.get("product_id")
                        or item.get("id")
                        or ""
                    ),
                    "productName": str(
                        item.get("productName")
                        or item.get("name")
                        or ""
                    ),
                    "quantity": int(item.get("quantity", 1)),
                    "unitPrice": float(
                        item.get("unitPrice")
                        or item.get("unit_price")
                        or 0
                    ),
                    "discount": float(item.get("discount", 0)),
                    "images": item.get("images"),
                })

            data["items"] = mapped_items

            orders.append(Order(**data))

        return orders

    except Exception as e:
        print("Order history error:", e)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{order_id}", response_model=Order)
def get_order_detail(order_id: str):
    doc = db.collection("orders").document(order_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Order not found")
    return Order(**doc.to_dict())

@router.put("/{order_id}/cancel")
def cancel_order(order_id: str):
    ref = db.collection("orders").document(order_id)
    doc = ref.get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="Order not found")

    data = doc.to_dict()
    if data["status"] not in ["PENDING", "CONFIRMED"]:
        raise HTTPException(status_code=400, detail="Order cannot be cancelled")

    now = datetime.utcnow()
    data["status"] = "CANCELLED"
    data["updatedAt"] = now
    data["orderTracking"].append({"status": "CANCELLED", "date": now})

    ref.set(data)
    return {"message": "Order cancelled successfully"}