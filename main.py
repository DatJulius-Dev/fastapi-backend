import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2' 
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
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
async def lifespan(app: FastAPI):
    print("--- STARTUP: Loading ML Models & Resources ---")
    ml_resources.load_all()    
    yield
    print("--- SHUTDOWN: Cleaning up resources ---")
    if r:
        print("Clearing Redis Cache...")
        r.flushdb()
        r.close()

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
def home():
    return {"message": "Welcome to Recomart API Service v3.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)