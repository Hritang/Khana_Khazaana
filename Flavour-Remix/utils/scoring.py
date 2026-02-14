def _normalize_profile(profile: list[str]) -> set[str]:
    normalized: set[str] = set()
    for value in profile:
        if isinstance(value, str):
            cleaned = value.strip().lower()
            if cleaned:
                normalized.add(cleaned)
    return normalized


def calculate_similarity(profile1: list[str], profile2: list[str]) -> dict:
    set1 = _normalize_profile(profile1)
    set2 = _normalize_profile(profile2)

    if not set1 or not set2:
        return {
            "overlap_count": 0,
            "jaccard": 0.0,
            "dice": 0.0,
            "overlap_terms": [],
        }

    overlap = set1.intersection(set2)
    union = set1.union(set2)

    jaccard = round(len(overlap) / len(union), 4)
    dice = round((2 * len(overlap)) / (len(set1) + len(set2)), 4)

    return {
        "overlap_count": len(overlap),
        "jaccard": jaccard,
        "dice": dice,
        "overlap_terms": sorted(overlap),
    }
