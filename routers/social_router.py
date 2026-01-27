from fastapi import APIRouter
from pydantic import BaseModel
from database import db, firestore

router = APIRouter(prefix="/api/social", tags=["Social"])

class ReviewRequest(BaseModel):
    user_id: str
    product_id: int
    rating: int
    comment: str

@router.post("/review")
def post_review(req: ReviewRequest):
    try:
        db.collection('reviews').add({
            "userId": req.user_id,
            "productId": req.product_id,
            "rating": req.rating,
            "comment": req.comment,
            "createdAt": firestore.SERVER_TIMESTAMP
        })
        return {"status": "success", "message": "Cảm ơn bạn đã đánh giá!"}
    except Exception as e:
        return {"status": "failed", "error": str(e)}

@router.get("/reviews/{product_id}")
def get_reviews(product_id: int):
    docs = db.collection('reviews').where('productId', '==', product_id)\
             .order_by('createdAt', direction='DESCENDING').stream()
    
    reviews = []
    for doc in docs:
        d = doc.to_dict()
        reviews.append(d)
        
    return {"product_id": product_id, "reviews": reviews}

@router.post("/wishlist/toggle")
def toggle_wishlist(user_id: str, product_id: int):
    user_ref = db.collection('users').document(user_id)
    doc = user_ref.get()
    
    if doc.exists:
        data = doc.to_dict()
        wishlist = data.get('wishlist', [])
        
        if product_id in wishlist:
            wishlist.remove(product_id)
            action = "removed"
        else:
            wishlist.append(product_id)
            action = "added"
            
        user_ref.update({"wishlist": wishlist})
        return {"status": "success", "action": action, "wishlist": wishlist}
    return {"error": "User not found"}

@router.get("/wishlist/{user_id}")
def get_user_wishlist(user_id: str):
    docs = db.collection('users').document(user_id).collection('wishlist').stream()
    
    wishlist = []
    for doc in docs:
        item = doc.to_dict()
        item['product_id'] = doc.id
        wishlist.append(item)
        
    return {"data": wishlist}