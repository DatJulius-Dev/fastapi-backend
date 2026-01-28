import asyncio
import os
import json
import firebase_admin
from firebase_admin import credentials

firebase_config_str = os.getenv("FIREBASE_CONFIG")

if firebase_config_str:
    try:
        cred_dict = json.loads(firebase_config_str)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        print("--- FIREBASE: Khởi tạo thành công từ Environment Variable! ---")
    except Exception as e:
        print(f"--- FIREBASE ERROR: Lỗi định dạng JSON hoặc Credential: {e} ---")
else:
    print("--- FIREBASE WARNING: Không tìm thấy biến FIREBASE_CONFIG. Bỏ qua khởi tạo. ---")

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3' 
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from ml_engine import ml_resources
from routers import system_router
from fastapi.staticfiles import StaticFiles
from routers.user_router import router as persona_router

from routers import (
    product_router, 
    user_router, 
    rec_router, 
    payment_router,
    auth_router,
    cart_router,
    social_router,
    order_router,
    interaction_router
)
from database import r, db

@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    print("--- STARTUP: Server is online. Port opened! ---")

    async def load_models_background():
        await asyncio.sleep(1) 
        print("--- BACKGROUND: Loading ML Models & Resources in progress... ---")
        try:
            ml_resources.load_all()
            print("--- BACKGROUND: ML Models Loaded Successfully! ---")
        except Exception as e:
            print(f"--- BACKGROUND ERROR: Failed to load models: {e} ---")

    asyncio.create_task(load_models_background())
    
    yield
    
    print("--- SHUTDOWN: Cleaning up resources ---")
    if r:
        print("Clearing Redis Cache...")
        try:
            r.flushdb()
            r.close()
        except:
            pass

app = FastAPI(lifespan=lifespan, title="Recomart E-commerce API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if not os.path.exists("storage"):
    os.makedirs("storage")

app.mount("/storage", StaticFiles(directory="storage"), name="storage")

app.include_router(auth_router.router)      # Auth
app.include_router(product_router.router)   # Product
app.include_router(rec_router.router)       # Recommendation
app.include_router(cart_router.router)      # Cart
app.include_router(order_router.router)     # Order
app.include_router(payment_router.router)   # Payment
app.include_router(user_router.router)      # User
app.include_router(social_router.router)    # Social
app.include_router(system_router.router)    # Health
app.include_router(interaction_router.router)      # Interaction
app.include_router(persona_router)

@app.get("/")
@app.head("/")
def home():
    return {"message": "Welcome to Recomart API Service v3.0"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)