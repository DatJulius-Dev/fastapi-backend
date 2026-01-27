def build_tags(total_spent, order_count, favorite_categories):
    tags = []

    # Giá trị chi tiêu
    if total_spent >= 50_000_000:
        tags.append("VIP Diamond")
    elif total_spent >= 10_000_000:
        tags.append("Gold Member")
    elif total_spent >= 3_000_000:
        tags.append("Silver Member")

    # Hành vi mua
    if order_count == 1:
        tags.append("Newbie")
    elif order_count >= 10:
        tags.append("Loyal Customer")

    # Sở thích nổi bật
    for cat, percent in favorite_categories.items():
        if percent >= 40:
            tags.append(f"{cat} Lover")

    return tags
