def normalize_categories(counts: dict):
    total = sum(counts.values()) or 1
    return {
        k: round(v / total * 100, 1)
        for k, v in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:5]
    }