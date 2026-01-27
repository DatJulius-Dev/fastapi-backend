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
