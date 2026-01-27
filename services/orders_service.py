from core.firestore_client import db
from utils.category_utils import normalize_categories

def build_order_features(user_id: str):
    orders = db.collection("orders").where("userId", "==", user_id).get()

    total_spent = 0
    order_count = 0
    category_counts = {}

    print(f"--- DEBUG TOTAL SPENT: User {user_id} has {len(orders)} orders ---")

    for o in orders:
        data = o.to_dict()

        raw_amount = (
            data.get("totalAmount") or 
            data.get("totalPrice") or 
            data.get("unitPrice") or 
            0
        )

        try:
            amount = float(raw_amount)
            total_spent += amount
            order_count += 1
            print(f"Order ID {o.id}: cộng thêm {amount}")
        except (ValueError, TypeError):
            print(f"Order ID {o.id}: Lỗi kiểu dữ liệu tiền ({raw_amount})")

        items = data.get("items", [])
        if isinstance(items, list):
            for item in items:
                cat = (
                    item.get("categoryName") or 
                    item.get("category") or 
                    item.get("cat") or 
                    "Other"
                )
                category_counts[cat] = category_counts.get(cat, 0) + 1

    avg_order = total_spent / order_count if order_count > 0 else 0

    print(f"RESULT FINAL: Total Spent = {total_spent}")

    return {
        "total_spent": total_spent,
        "order_count": order_count,
        "avg_order": round(avg_order, 2),
        "favorite_categories": normalize_categories(category_counts),
    }