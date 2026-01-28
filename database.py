import redis
import firebase_admin
from firebase_admin import credentials, firestore
import os
from config import *

# --- Redis Connection ---
try:
    r = redis.Redis(
        host=REDIS_HOST, 
        port=REDIS_PORT, 
        password=REDIS_PASSWORD,
        db=REDIS_DB, 
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1
    )
    r.ping()
    print(f"Redis: Connected to {REDIS_HOST}")
except Exception as e:
    print(f"Redis Error: {e} -> Running without Redis")
    r = None

# --- Firebase Connection ---
if not firebase_admin._apps:
    if os.path.exists(KEY_PATH):
        cred = credentials.Certificate(KEY_PATH)
        firebase_admin.initialize_app(cred)
        print("Firebase: Connected")
    else:
        print("Firebase Error: Key file not found!")

try:
    db = firestore.client()
except Exception as e:
    print(f"Firestore Client Error: {e}")
    db = None