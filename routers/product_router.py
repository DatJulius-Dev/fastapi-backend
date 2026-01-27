import datetime
import os
import random
import google.generativeai as genai
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from database import db
from ml_engine import ml_resources, find_similar_items

from routers.user_router import get_user_persona

genai.configure(api_key="AIzaSyAx3ttAWZCZrKJY92H4dq__K87CZrZoBhw") 
model = genai.GenerativeModel('gemini-2.5-flash')

router = APIRouter(prefix="/api/products", tags=["Products"])

class ChatRequest(BaseModel):
    query: str
    user_id: str = "guest"

class ChatResponse(BaseModel):
    response: str
    type: str
    data: List[dict] = []

class ProductBase(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    description: Optional[str] = None
    imageUrl: Optional[str] = None

    # ✅ ID (dùng cho admin / logic)
    categoryId: Optional[str] = None
    brandId: Optional[str] = None

    # ✅ Name (dùng cho search / AI / hiển thị)
    categoryName: Optional[str] = None
    brandName: Optional[str] = None

    averageRating: Optional[float] = 0.0
    stock: Optional[int] = None
    discount: Optional[float] = None
    isActive: Optional[bool] = None

def search_product_in_firestore(keyword: str):
    keyword = keyword.lower()
    products_ref = db.collection('products')
    docs = products_ref.stream()
    
    found_products = []
    
    for doc in docs:
        data = doc.to_dict()
        p_name = str(data.get('name', '')).lower()
        p_desc = str(data.get('description', '')).lower()
        
        if keyword in p_name or keyword in p_desc:
            data['id'] = doc.id
            found_products.append(data)
            if len(found_products) >= 5:
                break
                
    return found_products

def get_recent_orders(user_id):
    try:
        docs = db.collection('orders').where('userId', '==', user_id)\
                 .order_by('createdAt', direction='DESCENDING').limit(3).stream()
        orders = []
        for doc in docs:
            d = doc.to_dict()
            orders.append({
                "id": doc.id,
                "status": d.get('status', 'Processing'),
                "total": d.get('totalPrice', 0),
                "date": d.get('createdAt', datetime.datetime.now()).strftime("%d/%m/%Y"),
                "items": [i.get('name') for i in d.get('items', [])]
            })
        return orders
    except: return []

@router.get("")
def get_products(
    page: int = 1, 
    limit: int = 20, 
    sort: Optional[str] = None
):
    try:
        print(f"INFO: Fetching products - Page: {page}, Limit: {limit}")
        products_ref = db.collection('products')
        
        if sort == 'price_asc':
            query = products_ref.order_by('price', direction='ASCENDING')
        elif sort == 'price_desc':
            query = products_ref.order_by('price', direction='DESCENDING')
        elif sort == 'name_asc':
            query = products_ref.order_by('name', direction='ASCENDING')
        elif sort == 'name_desc':
            query = products_ref.order_by('name', direction='DESCENDING')
        else:
            query = products_ref.order_by('name', direction='ASCENDING')

        docs = query.limit(limit).offset((page - 1) * limit).stream()
        
        results = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            results.append(data)
            
        return {"data": results}
    except Exception as e:
        print(f"DATABASE ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/categories")
def get_categories():
    try:
        cats = db.collection('categories').stream()
        return {"categories": [c.to_dict() for c in cats]}
    except Exception as e:
        print(f"CATEGORY ERROR: {e}")
        return {"categories": []}

@router.get("/search")
def search_products(keyword: str = "", sort: Optional[str] = "name_asc"):
    if not keyword: 
        return {"results": []}
    
    keyword = keyword.lower().strip()
    results = []
    
    try:
        products = db.collection('products').stream()
        
        for doc in products:
            data = doc.to_dict()
            
            name = str(data.get('name', '')).lower()
            brand = str(data.get('brandName', '')).lower()
            cat = str(data.get('categoryName', '')).lower()
            
            if keyword in name or keyword in brand or keyword in cat:
                normalized_item = {
                    "id": doc.id,
                    "name": data.get('name', 'Sản phẩm không tên'),
                    "price": float(data.get('price', 0)),
                    "imageUrl": data.get('imageUrl') or data.get('image') or "https://via.placeholder.com/150", 
                    "category": data.get('categoryName', 'Khác'),
                    "rating": str(data.get('rating', '0')),
                    "brand": data.get('brandName', '')
                }
                results.append(normalized_item)
        
        if sort == 'name_asc':
            results.sort(key=lambda x: x['name'].lower())
        elif sort == 'name_desc':
            results.sort(key=lambda x: x['name'].lower(), reverse=True)
        elif sort == 'price_asc':
            results.sort(key=lambda x: x['price'])
        elif sort == 'price_desc':
            results.sort(key=lambda x: x['price'], reverse=True)
        elif sort == 'rating_desc':
            results.sort(key=lambda x: float(x['rating']), reverse=True)
            
    except Exception as e:
        print(f"SEARCH ERROR: {e}")
        return {"error": str(e), "results": []}

    return {
        "query": keyword, 
        "total": len(results),
        "results": results
    }

@router.get("/filter")
def filter_products(
    category: Optional[str] = None, 
    min_price: Optional[float] = None, 
    max_price: Optional[float] = None, 
    brand: Optional[str] = None
):
    try:
        query = db.collection('products')
        if category and category != "All": 
            query = query.where("categoryName", "==", category)
        if brand and brand != "All": 
            query = query.where("brandName", "==", brand)
        
        results = []
        for doc in query.stream():
            d = doc.to_dict()
            d['id'] = doc.id
            p = float(d.get('price', 0))
            if min_price is not None and p < min_price: continue
            if max_price is not None and p > max_price: continue
            results.append(d)
        return {"count": len(results), "results": results}
    except Exception as e:
        return {"error": str(e)}

@router.post("/chat", response_model=ChatResponse)
async def chat_with_ai(request: ChatRequest):
    user_query = request.query.lower()
    user_id = request.user_id
    
    try:
        persona_data = get_user_persona(user_id)
        
        user_tags = ", ".join(persona_data.get('tags', []))
        user_favs = ", ".join(persona_data.get('favorite_categories', {}).keys())
        total_spent = persona_data.get('total_spent', 0)
        
        persona_instruction = f"""
        USER CONTEXT:
        - Tags: [{user_tags}]
        - Interests: [{user_favs}]
        - VIP Level: {'High' if total_spent > 10000000 else 'Standard'}
        
        ADAPTIVE BEHAVIOR:
        - If user has 'VIP' or 'High Spender' tags: Use polite, professional tone, suggest premium options.
        - If user has specific interests (e.g. 'Laptop'): Prioritize mentioning products matching those interests first.
        - If user is 'Newbie': Explain simply and helpful.
        """
    except Exception:
        persona_instruction = "User is a Guest. Be polite and helpful."

    context_data = ""
    response_type = "text"
    response_data = []

    order_keywords = ["order", "shipping", "status", "track", "delivery", "đơn hàng", "giao hàng", "vận chuyển", "ship", "mua chưa"]

    if any(k in user_query for k in order_keywords):
        orders = get_recent_orders(user_id)
        if orders:
            response_type = "order_list"
            response_data = orders
            context_data = "USER ORDER HISTORY (Use this to answer status):\n"
            for o in orders:
                context_data += f"- Order ID: {o['id']} | Status: {o['status']} | Total: {o['total']} | Items: {o['items']}\n"
        else:
            context_data = "System: User has no recent orders found."

    else:
        products = search_product_in_firestore(request.query)
        if products:
            response_type = "product_list"
            response_data = products
            context_data = "PRODUCTS FOUND IN INVENTORY:\n"
            for p in products:
                price = "{:,.0f}".format(p.get('price', 0)).replace(",", ".")
                name = p.get('name', 'Unknown')
                rating = p.get('averageRating', 'N/A')
                category = p.get('categoryName', 'General') 
                context_data += f"- Name: {name} | Price: {price} VND | Rating: {rating} | Cat: {category}\n"
        else:
            context_data = "System: No matching products found."

    prompt = f"""
    You are RecoAI, a smart virtual assistant for RecoMart.
    
    {persona_instruction}
    
    CONTEXT DATA:
    {context_data}
    
    USER QUESTION: "{user_query}"
    
    TASKS:
    1. If Order Data is present: Inform the user about their order status clearly based on the context.
    2. If Product Data is present: Introduce them. If a product matches User's Interests/Tags, highlight it specifically.
    3. If NO Data found: Apologize sincerely and offer general help.
    4. Answer briefly, friendly, and use English.
    """

    try:
        response = model.generate_content(prompt)
        return {
            "response": response.text,
            "type": response_type,
            "data": response_data
        }
    except Exception as e:
        print(f"GEMINI ERROR: {e}") 
        return {"response": f"AI Error: {e}", "type": "text", "data": []}

@router.get("/similar/{item_id}")
def get_similar_products(item_id: str):
    try:
        if ml_resources.item_embeddings is None or len(ml_resources.item_embeddings) == 0: 
            return {"results": []}
        
        real_id = int(item_id)
        if real_id >= len(ml_resources.item_embeddings): 
            return {"results": []}
             
        query_vec = ml_resources.item_embeddings[real_id]
        results = find_similar_items(query_vec, ml_resources.item_embeddings)
        
        return {
            "query_id": real_id, 
            "results": [r for r in results if str(r['id']) != item_id]
        }
    except Exception as e:
        print(f"ML ERROR: {e}")
        return {"results": []}

@router.get("/logs")
def get_system_logs():
    try:        
        current_time = datetime.datetime.now()
        dummy_logs = []
        
        actions = ["INFO: System Check", "ERROR: Payment Gateway", "WARN: High CPU Usage", "DEBUG: Cache Miss", "INFO: New Order Placed"]
        users = ["System", "Admin", "User_101", "Guest", "Bot_Crawler"]
        
        for i in range(15):
            time_offset = current_time - datetime.timedelta(minutes=i*20)
            
            action_raw = random.choice(actions)
            level = action_raw.split(":")[0] 
            msg = action_raw.split(":")[1].strip()
            
            dummy_logs.append({
                "time": time_offset.isoformat(),
                "action": action_raw,
                "user": random.choice(users),
                "message": f"{msg} detected at {time_offset.strftime('%H:%M:%S')}"
            })

        return {"logs": dummy_logs}
        
    except Exception as e:
        return {"logs": [
            {
                "time": datetime.datetime.now().isoformat(),
                "action": "ERROR",
                "user": "System",
                "message": str(e)
            }
        ]}

@router.get("/{product_id}")
def get_product_detail(product_id: str):
    doc = db.collection('products').document(product_id).get()
    if not doc.exists: 
        raise HTTPException(status_code=404, detail="Product not found")
    data = doc.to_dict()
    data['id'] = doc.id
    return {"data": data}

@router.post("/create")
def create_product(product: ProductBase):
    try:
        data = product.dict()
        db.collection('products').add(data)
        return {"message": "Product created successfully"}
    except Exception as e: 
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{product_id}")
def update_product(product_id: str, product: ProductBase):
    try:
        data = product.dict(exclude_none=True)
        print("🔥 UPDATE PRODUCT DATA:", data)

        db.collection('products').document(product_id).update(data)

        return {"message": "Product updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{product_id}")
def delete_product(product_id: str):
    try:
        db.collection('products').document(product_id).delete()
        return {"message": "Product deleted successfully"}
    except Exception as e: 
        raise HTTPException(status_code=500, detail=str(e))