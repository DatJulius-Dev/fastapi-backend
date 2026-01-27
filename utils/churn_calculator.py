def calculate_churn_risk(user_id, total_spent, order_count, engagement_score):
    if order_count == 0:
        return "High"

    if engagement_score < 30 and total_spent < 500_000:
        return "High"

    if engagement_score > 200:
        return "Low"

    return "Medium"
