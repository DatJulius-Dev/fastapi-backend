from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from firebase_admin import firestore

db = firestore.client()

router = APIRouter(prefix="/interaction", tags=["Interaction"])

class InteractionRequest(BaseModel):
    user_id: str
    product_id: str
    interaction_type: str
    duration: Optional[int] = 0
    source: Optional[str] = "mobile"

@router.post("")
def track_interaction(req: InteractionRequest):
    print(f"--- DEBUG START ---")
    print(f"Nhận request cho User: {req.user_id}, Product: {req.product_id}")
    
    try:
        import firebase_admin
        current_project = firebase_admin.get_app().project_id
        print(f"📡 Đang kết nối tới Project ID: {current_project}")

        user_ref = db.collection("users").document(req.user_id)
        
        result = user_ref.collection("interactions").add({
            "item_id": req.product_id,
            "type": req.interaction_type,
            "duration": req.duration,
            "timestamp": firestore.SERVER_TIMESTAMP
        })
        
        new_doc_id = result[1].id
        print(f"Đã ghi vào Firestore! ID bản ghi: {new_doc_id}")
        print(f"--- DEBUG END ---")

        return {
            "status": "success", 
            "project_connected": current_project,
            "doc_id": new_doc_id
        }

    except Exception as e:
        print(f"LỖI THẬT SỰ: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))