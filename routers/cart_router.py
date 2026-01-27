from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import r, db
from config import CACHE_TTL
import json

router = APIRouter(prefix="/api/cart", tags=["Cart"])

class CartItem(BaseModel):
    user_id: str
    product_id: int
    quantity: int
    
class CartItemUpdate(BaseModel):
    user_id: str
    product_id: str
    quantity: int

@router.put("/update")
def update_cart_item(item: CartItemUpdate):
    cart_ref = db.collection('users').document(item.user_id).collection('cart').document(item.product_id)
    
    doc = cart_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Product not found in cart")
    
    if item.quantity <= 0:
        cart_ref.delete()
        return {"message": "Product removed from cart"}
    
    cart_ref.update({"quantity": item.quantity})
    return {"message": "Quantity updated successfully", "quantity": item.quantity}

@router.delete("/remove/{user_id}/{product_id}")
def remove_cart_item(user_id: str, product_id: str):
    cart_ref = db.collection('users').document(user_id).collection('cart').document(product_id)
    cart_ref.delete()
    return {"message": "Product removed"}

@router.get("/{user_id}")
def get_cart(user_id: str):
    if not r: return {"cart": [], "total": 0}
    
    cart_key = f"cart:{user_id}"
    items = r.hgetall(cart_key)
    
    result = []
    total_price = 0
    
    if items:
        for pid, qty in items.items():
            p_docs = db.collection('products').where('id', '==', int(pid)).stream()
            for doc in p_docs:
                p_data = doc.to_dict()
                q = int(qty)
                price = float(p_data.get('price', 0))
                total_price += price * q
                result.append({
                    "product_id": int(pid),
                    "name": p_data.get('name'),
                    "price": price,
                    "image": p_data.get('imageUrl'),
                    "quantity": q
                })
                
    return {"user_id": user_id, "items": result, "total_price": total_price}

@router.post("/add")
def add_to_cart(item: CartItem):
    if not r: return {"error": "Redis not connected"}
    
    cart_key = f"cart:{item.user_id}"
    new_qty = r.hincrby(cart_key, str(item.product_id), item.quantity)
    
    if new_qty <= 0:
        r.hdel(cart_key, str(item.product_id))
        
    r.expire(cart_key, 60*60*24*7)
    
    return {"status": "success", "message": "Cart updated", "current_qty": new_qty}

@router.delete("/clear/{user_id}")
def clear_cart(user_id: str):
    if r: r.delete(f"cart:{user_id}")
    return {"status": "success", "message": "Cart cleared"}