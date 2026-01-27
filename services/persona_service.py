import os
from google.cloud import firestore
from google.oauth2 import service_account
from google.cloud.firestore import SERVER_TIMESTAMP

KEY_PATH = "serviceAccountKey.json" 

if os.path.exists(KEY_PATH):
    credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
    db = firestore.Client(credentials=credentials)
else:
    print(f"Lỗi: Không tìm thấy file key tại {KEY_PATH}")
    db = firestore.Client() 

def build_user_features(user_id: str):
    orders = db.collection('orders').where('userId', '==', user_id).stream()

    total_spent = 0
    order_count = 0
    category_counts = {}

    for o in orders:
        data = o.to_dict()
        price = data.get('totalAmout', 0)
        total_spent += price
        order_count += 1

        for item in data.get('items', []):
            cat = item.get('categoryName', 'Other')
            category_counts[cat] = category_counts.get(cat, 0) + 1

    avg_order = total_spent / order_count if order_count > 0 else 0
    total_items = sum(category_counts.values()) or 1

    affinity = {
        k: round((v / total_items) * 100, 1)
        for k, v in category_counts.items()
    }

    return {
        "total_spent": total_spent,
        "order_count": order_count,
        "avg_order": avg_order,
        "favorite_categories": affinity
    }

def enrich_from_interactions(user_id: str, features: dict):
    interactions = (
        db.collection("interactions")
        .where("userId", "==", user_id)
        .stream()
    )

    view_seconds = 0
    click_count = 0
    add_to_cart = 0
    buy_now = 0

    for doc in interactions:
        data = doc.to_dict()
        t = data.get("type")

        if t == "longView":
            view_seconds += data.get("duration", 0)
        elif t == "click":
            click_count += 1
        elif t == "addToCart":
            add_to_cart += 1
        elif t == "buyNow":
            buy_now += 1

    features["engagement_score"] = (
        view_seconds * 0.5 +
        click_count * 5 +
        add_to_cart * 15 +
        buy_now * 25
    )

    features["interaction_stats"] = {
        "view_seconds": view_seconds,
        "clicks": click_count,
        "add_to_cart": add_to_cart,
        "buy_now": buy_now,
    }

def build_tags(total_spent, order_count, categories, engagement_score):
    tags = []

    if total_spent > 50_000_000:
        tags.append("VIP Diamond")
    elif total_spent > 10_000_000:
        tags.append("Gold Member")

    if order_count == 1:
        tags.append("Newbie")

    if engagement_score > 300:
        tags.append("Highly Engaged")

    if "Laptop" in categories and categories["Laptop"] > 40:
        tags.append("Tech Lover")

    return tags

def calculate_churn_risk(total_spent, order_count, engagement_score):
    if order_count == 0:
        return "High"

    if engagement_score < 30 and total_spent < 500_000:
        return "High"

    if engagement_score > 200:
        return "Low"

    return "Medium"

def update_user_persona(user_id: str):
    features = build_user_features(user_id)

    enrich_from_interactions(user_id, features)

    tags = build_tags(
        features["total_spent"],
        features["order_count"],
        features["favorite_categories"],
        features["engagement_score"]
    )

    churn_risk = calculate_churn_risk(
        features["total_spent"],
        features["order_count"],
        features["engagement_score"]
    )

    persona = {
        "user_id": user_id,
        **features,
        "tags": tags,
        "churn_risk": churn_risk,
        "updatedAt": SERVER_TIMESTAMP
    }

    db.collection("user_persona").document(user_id).set(persona)

    return persona