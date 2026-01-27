from fastapi import APIRouter, BackgroundTasks, HTTPException
import numpy as np
import json
from database import db, r
from config import *
from ml_engine import ml_resources, train_model_process
from routers.user_router import get_user_persona

router = APIRouter(prefix="/api", tags=["Recommendation"])

def get_all_products_from_db():
    docs = db.collection('products').stream()
    products = []
    for doc in docs:
        d = doc.to_dict()
        if d.get('isActive', True): 
            products.append({
                'id': doc.id, 
                'int_id': d.get('id_int', 0),
                'category': d.get('categoryName', 'General'),
                'rating': d.get('averageRating', 0),
                'sold': d.get('soldCount', 0)
            })
    return products

def get_user_history(uid):
    try:
        docs = db.collection('users').document(str(uid)).collection('interactions')\
                 .order_by('timestamp', direction='DESCENDING').limit(20).stream()
        history = [d.to_dict().get('product_id_int', 0) for d in docs]
    except: return []

def prepare_inputs(user_id_int, history, candidates):
    seq = history[-SEQ_LEN:]
    padded_seq = [0]*(SEQ_LEN-len(seq)) + seq
    num_cands = len(candidates)
    
    X_u = np.array([user_id_int] * num_cands)
    X_i = np.array(candidates)
    X_s = np.tile(padded_seq, (num_cands, 1))
    X_c = np.random.randn(num_cands, CONTENT_DIM)
    return [X_u, X_i, X_s, X_c]

@router.get("/recommend/{user_id}")
async def get_recommendation(user_id: str):
    try:
        cache_key = f"rec:{user_id}"
        if r:
            cached = r.get(cache_key)
            if cached: return json.loads(cached)

        all_products = get_all_products_from_db()
        if not all_products:
            return {"user_id": user_id, "recommendations": [], "source": "empty_inventory"}

        persona = get_user_persona(user_id)
        fav_cats = persona.get('favorite_categories', {})
        history = get_user_history(user_id)
        
        user_id_int = abs(hash(user_id)) % USER_COUNT 

        final_recommendations = []
        source_type = "ai_personalized"

        if not history:
            source_type = "cold_start_persona"            
            sorted_products = sorted(all_products, key=lambda x: x['sold'], reverse=True)
            
            for p in sorted_products:
                score = p['rating'] * 10 + p['sold'] * 0.5
                
                if p['category'] in fav_cats:
                    score += fav_cats[p['category']] * 2 
                
                final_recommendations.append({
                    "id": p['id'],
                    "name": p.get('name', ''),
                    "score": score,
                    "reason": "Popular & Matches Persona" if p['category'] in fav_cats else "Best Seller"
                })

        else:
            if not ml_resources.model:
                 raise HTTPException(status_code=500, detail="Model AI not loaded")

            candidate_ids_int = [p['int_id'] for p in all_products if p['int_id'] > 0]
            
            candidates_pool = candidate_ids_int if len(candidate_ids_int) < 200 else np.random.choice(candidate_ids_int, 200, replace=False)

            inputs = prepare_inputs(user_id_int, history, candidates_pool)
            ai_scores = ml_resources.model.predict(inputs, verbose=0).flatten()

            for idx, item_id_int in enumerate(candidates_pool):
                prod_info = next((p for p in all_products if p['int_id'] == item_id_int), None)
                if not prod_info: continue

                base_score = float(ai_scores[idx])
                
                boost_factor = 1.0
                if prod_info['category'] in fav_cats:
                    affinity_val = fav_cats[prod_info['category']]
                    boost_factor = 1 + (affinity_val / 200) 
                
                final_score = base_score * boost_factor
                
                final_recommendations.append({
                    "id": prod_info['id'],
                    "score": final_score,
                    "reason": "AI Prediction"
                })
        final_recommendations.sort(key=lambda x: x['score'], reverse=True)
        top_recs = final_recommendations[:10]
        
        result_data = [
            {"id": item['id'], "rank": idx + 1, "debug_score": round(item['score'], 4)} 
            for idx, item in enumerate(top_recs)
        ]

        result = {
            "user_id": user_id,
            "recommendations": result_data,
            "source": source_type
        }

        if r: r.setex(cache_key, CACHE_TTL, json.dumps(result))
        
        return result

    except Exception as e:
        print(f"Error Recommendation: {e}")
        return {"user_id": user_id, "recommendations": [], "source": "error_fallback"}

@router.post("/admin/retrain")
async def trigger_retraining(
    admin_secret: str, 
    background_tasks: BackgroundTasks
):
    if admin_secret != "admin123": 
        raise HTTPException(status_code=403, detail="Invalid Admin Password")
    background_tasks.add_task(handle_retrain_process)
    return {
        "status": "accepted", 
        "message": "Retraining process started in the background. The model will be updated shortly."
    }

def handle_retrain_process():
    print("--- STARTING RETRAIN ---")
    
    try:
        train_stats = train_model_process() 
        print(f"Training completed: {train_stats}")
        ml_resources.load_all() 
        if r: 
            r.flushdb()
            print("Redis cache cleared.")
            
        print("--- RETRAIN DONE ---")
        
    except Exception as e:
        print(f"CRITICAL ERROR during retraining: {e}")