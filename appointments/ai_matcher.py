import math
import re
from collections import Counter
from django.db.models import Avg, Prefetch
from accounts.models import User
from services.models import EngineerExpertise, Service


# Comprehensive stop-word list to eliminate noise from project scoping text
STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down",
    "during", "each", "few", "for", "from", "further", "had", "hadn't", "has",
    "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her",
    "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's",
    "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it",
    "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such", "than",
    "that", "that's", "the", "their", "theirs", "them", "themselves", "then", "there",
    "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't",
    "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's",
    "when", "when's", "where", "where's", "which", "while", "who", "who's", "whom",
    "why", "why's", "with", "won't", "would", "wouldn't", "you", "you'd", "you'll",
    "you're", "you've", "your", "yours", "yourself", "yourselves", "need", "want",
    "looking", "help", "project", "please", "system", "app", "application", "build",
    "create", "develop", "consultation", "session"
}

# Proficiency multipliers reflecting depth of verified expertise
PROFICIENCY_MULTIPLIERS = {
    EngineerExpertise.ProficiencyLevel.BEGINNER: 0.8,
    EngineerExpertise.ProficiencyLevel.INTERMEDIATE: 1.0,
    EngineerExpertise.ProficiencyLevel.EXPERT: 1.25,
    EngineerExpertise.ProficiencyLevel.LEAD: 1.5,
}


def tokenize(text: str) -> list:
    """
    Tokenizes and normalizes input text, extracting alphanumeric and technical terms
    (e.g., 'ci/cd', 'k8s', 'c++', 'aws', 'django') while filtering stop words.
    """
    if not text:
        return []

    text_lower = str(text).lower()
    # Match words, including terms with dots, pluses, hashes, and slashes like c++, c#, .net, ci/cd
    raw_tokens = re.findall(r"[a-z0-9+#/.-]+", text_lower)
    tokens = []

    for token in raw_tokens:
        # Strip edge punctuation
        cleaned = token.strip(".,;:!?\"'()[]{}")
        if not cleaned:
            continue
        # Preserve single-letter technical keywords like 'c' or 'r', otherwise require len > 1
        if (len(cleaned) > 1 or cleaned in {"c", "r"}) and cleaned not in STOP_WORDS:
            tokens.append(cleaned)

    return tokens


def cosine_similarity(vec1: dict, vec2: dict) -> float:
    """
    Calculates the cosine similarity between two weighted term-frequency vectors.
    Formula: dot_product(v1, v2) / (norm(v1) * norm(v2)).
    Returns a float between 0.0 and 1.0.
    """
    if not vec1 or not vec2:
        return 0.0

    intersection = set(vec1.keys()) & set(vec2.keys())
    if not intersection:
        return 0.0

    dot_product = sum(float(vec1[k]) * float(vec2[k]) for k in intersection)
    norm1 = math.sqrt(sum(float(v) ** 2 for v in vec1.values()))
    norm2 = math.sqrt(sum(float(v) ** 2 for v in vec2.values()))

    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0

    similarity = dot_product / (norm1 * norm2)
    return max(0.0, min(1.0, float(similarity)))


def calculate_match_scores(project_text: str) -> dict:
    """
    Analyzes project description text, computes cosine similarity against all active Services
    to identify the best service domain, evaluates all active engineers based on verified expertises,
    proficiency multipliers, experience, and ratings, and outputs 0-100% compatibility scores.
    Engineers with scores >= 80% are marked as is_shortlisted.
    """
    project_tokens = tokenize(project_text)
    project_vec = Counter(project_tokens)

    # 1. Evaluate and Match Closest Service Domain
    services = list(Service.objects.filter(is_active=True))
    best_service = None
    best_service_sim = 0.0
    service_scores = []

    if services:
        for svc in services:
            # Emphasize service title by repeating it in the corpus
            svc_corpus = f"{svc.name} {svc.name} {svc.description}"
            svc_tokens = tokenize(svc_corpus)
            svc_vec = Counter(svc_tokens)
            sim = cosine_similarity(project_vec, svc_vec)

            # Bonus for explicit term matches in service name
            name_tokens = set(tokenize(svc.name))
            if set(project_tokens) & name_tokens:
                sim = min(1.0, sim + 0.2)

            service_scores.append((svc, sim))
            if sim > best_service_sim:
                best_service_sim = sim
                best_service = svc

        # If no service had direct keyword overlap, pick General Architecture or first service
        if not best_service:
            general_svc = next(
                (s for s in services if "general" in s.name.lower() or "scoping" in s.name.lower()),
                services[0]
            )
            best_service = general_svc
            best_service_sim = 0.50

    # 2. Evaluate Active Engineers Against Verified Expertises & Proficiency
    engineers = User.objects.filter(
        role=User.Role.ENGINEER,
        is_active=True
    ).select_related("engineer_profile").prefetch_related(
        Prefetch(
            "engineer_expertises",
            queryset=EngineerExpertise.objects.filter(
                status=EngineerExpertise.VerificationStatus.APPROVED
            ).select_related("expertise")
        )
    ).annotate(
        avg_rating=Avg("engineer_appointments__feedback__rating")
    )

    engineer_results = []
    service_tokens = set(tokenize(f"{best_service.name} {best_service.description}")) if best_service else set()
    combined_query_tokens = set(project_tokens) | service_tokens

    for eng in engineers:
        approved_expertises = list(eng.engineer_expertises.all())
        eng_prof = getattr(eng, "engineer_profile", None)
        designation = eng_prof.designation if eng_prof and eng_prof.designation else "Software Engineer"
        yoe = eng_prof.years_of_experience if eng_prof else 0
        rating = round(eng.avg_rating, 1) if eng.avg_rating else 4.8

        # Build weighted engineer profile vector
        eng_vec = {}
        matched_skills = []
        highest_proficiency_multiplier = 1.0

        for ee in approved_expertises:
            exp_name = ee.expertise.name
            multiplier = PROFICIENCY_MULTIPLIERS.get(ee.proficiency_level, 1.0)
            highest_proficiency_multiplier = max(highest_proficiency_multiplier, multiplier)
            exp_tokens = tokenize(exp_name)

            for token in exp_tokens:
                eng_vec[token] = eng_vec.get(token, 0.0) + (1.5 * multiplier)

            # Check if this verified skill directly matches query or domain
            if set(exp_tokens) & combined_query_tokens:
                matched_skills.append(exp_name)

        # Include designation and bio in engineer representation
        desig_tokens = tokenize(designation)
        for token in desig_tokens:
            eng_vec[token] = eng_vec.get(token, 0.0) + 1.2

        if eng_prof and eng_prof.bio:
            bio_tokens = tokenize(eng_prof.bio)
            for token in bio_tokens:
                eng_vec[token] = eng_vec.get(token, 0.0) + 0.8

        # Compute skill vector cosine similarity
        skill_sim = cosine_similarity(project_vec, eng_vec) if project_vec else 0.0

        # Calculate multi-factor compatibility score (0 - 100%)
        # Base from cosine similarity (up to 55 points)
        base_score = skill_sim * 55.0

        # Direct skill overlap bonus (up to 25 points, scaled by proficiency)
        overlap_count = len(matched_skills)
        overlap_bonus = min(25.0, overlap_count * 12.0 * highest_proficiency_multiplier)

        # Domain service alignment bonus (up to 10 points)
        domain_bonus = 0.0
        if best_service:
            best_svc_lower = best_service.name.lower()
            if "general" in best_svc_lower or "scoping" in best_svc_lower:
                domain_bonus = 8.0
            elif any(s.lower() in best_svc_lower for s in matched_skills):
                domain_bonus = 10.0
            elif any(t in best_svc_lower for t in desig_tokens):
                domain_bonus = 8.0

        # Experience & reputation bonus (up to 10 points)
        exp_bonus = min(5.0, (yoe / 10.0) * 5.0)
        rating_bonus = min(5.0, (rating / 5.0) * 5.0)

        raw_score = base_score + overlap_bonus + domain_bonus + exp_bonus + rating_bonus

        # Normalize score baseline if direct matches occur
        if matched_skills and raw_score < 75.0:
            raw_score = 75.0 + (overlap_count * 5.0 * highest_proficiency_multiplier) + exp_bonus

        # General baseline when query has generic wording
        if not matched_skills and raw_score < 40.0:
            raw_score = 40.0 + exp_bonus + rating_bonus

        final_score = int(max(10, min(99, round(raw_score))))
        is_shortlisted = final_score >= 80

        engineer_results.append({
            "id": eng.id,
            "name": eng.get_full_name() or eng.username,
            "designation": designation,
            "score": final_score,
            "is_shortlisted": is_shortlisted,
            "is_recommended": False,
            "expertises": [ee.expertise.name for ee in approved_expertises],
            "matched_skills": list(dict.fromkeys(matched_skills)),
            "years_of_experience": yoe,
            "rating": rating,
            "rating_str": f"★ {rating}",
            "proficiency_multiplier": highest_proficiency_multiplier,
        })

    # Sort engineers by highest compatibility score first, tie-break with rating & experience
    engineer_results.sort(
        key=lambda x: (x["score"], x["rating"], x["years_of_experience"]),
        reverse=True
    )

    # Mark top engineer(s) as recommended
    if engineer_results:
        top_score = engineer_results[0]["score"]
        for eng in engineer_results:
            if eng["score"] == top_score or (eng["score"] >= 85 and eng["is_shortlisted"]):
                eng["is_recommended"] = True
                break

    return {
        "status": "success",
        "matched_service": {
            "id": best_service.id if best_service else None,
            "name": best_service.name if best_service else "General Architecture",
            "description": best_service.description if best_service else "",
            "similarity_score": round(best_service_sim * 100, 1),
        } if best_service else None,
        "engineers": engineer_results,
        "top_engineer": engineer_results[0] if engineer_results else None,
        "extracted_keywords": project_tokens[:15],
        "total_analyzed_engineers": len(engineer_results),
        "project_text": project_text,
    }
