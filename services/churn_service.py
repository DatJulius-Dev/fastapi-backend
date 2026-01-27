from datetime import datetime
import os
from google.cloud import firestore
from google.oauth2 import service_account

KEY_PATH = "serviceAccountKey.json"

if os.path.exists(KEY_PATH):
    credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
    db = firestore.Client(credentials=credentials, project=credentials.project_id)
else:
    print(f"Warning: Key file not found at {KEY_PATH}. Attempting default auth...")
    db = firestore.Client()

def calculate_churn_risk(user_id, total_spent, order_count):
    try:
        orders = (
            db.collection("orders")
            .where("userId", "==", user_id)
            .order_by("createdAt", direction=firestore.Query.DESCENDING)
            .limit(1)
            .get()
        )

        last_order_date = None
        for o in orders:
            last_order_date = o.to_dict().get("createdAt")

        if not last_order_date:
            return "High"

        if hasattr(last_order_date, "timestamp"):
            last_order_date = datetime.fromtimestamp(last_order_date.timestamp())
        elif isinstance(last_order_date, str):
            last_order_date = datetime.fromisoformat(last_order_date.replace('Z', '+00:00'))

        days_inactive = (datetime.utcnow() - last_order_date.replace(tzinfo=None)).days

        if days_inactive > 60 and total_spent < 1000000:
            return "High"
        if days_inactive > 30:
            return "Medium"
        return "Low"
    except Exception as e:
        print(f"Error calculating churn: {e}")
        return "Unknown"