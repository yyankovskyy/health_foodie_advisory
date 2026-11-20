"""Demo-only deterministic recommendation engine. Not medical advice."""
import json
import re
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


def load_json(filename):
    return json.loads((DATA_DIR / filename).read_text(encoding="utf-8"))


def taste_hints_from_receipts(receipts):
    """Never infer diagnoses or diet restrictions from purchases."""
    counts = Counter()
    examples = 0
    purchase_events = 0
    for receipt in receipts:
        if receipt.get("duplicate_of"):
            continue
        purchase_events += 1
        for food in receipt.get("foods", []):
            examples += 1
            for tag in set(food.get("tags", [])):
                counts[tag] += 1
    return {"sampled_food_lines": examples, "distinct_purchase_events": purchase_events, "tags": dict(counts), "confidence": "low; purchases alone cannot establish an enduring preference, allergy or diagnosis"}


def recommend(profile, recipes, meal_type, budget_usd, max_minutes, servings=1,
              selected_cuisines=None, avoid_ingredients=None, use_receipt_hints=False,
              receipts=None, preference_weights=None):
    """Produces preliminary discovery suggestions, NEVER a medical 'safe' verdict.
    Allergy exclusion is strict for identified allergens; incomplete labels trigger review.
    """
    servings = max(1, int(servings))
    selected_cuisines = set(selected_cuisines or [])
    avoid_ingredients = {x.strip().lower() for x in (avoid_ingredients or []) if x.strip()}
    food_allergies = {x.lower() for x in profile.get("confirmed_food_allergens", [])}
    hints = (taste_hints_from_receipts(receipts or [])
             if use_receipt_hints and preference_weights is None
             else {"tags": {}})
    considered, excluded = [], []
    for r in recipes:
        if meal_type != "Any" and r["meal_type"] != meal_type.lower():
            continue
        if selected_cuisines and r["cuisine"] not in selected_cuisines:
            continue
        cost = r["cost_usd_per_serving_demo"] * servings
        if r["time_minutes_demo"] > max_minutes or cost > budget_usd:
            continue
        text = (r.get("ingredient_summary") or "").lower()
        allergen_tags = {x.lower().replace("_possible", "") for x in r["allergens_identified_from_summary"]}
        hits = sorted(food_allergies.intersection(allergen_tags))
        user_avoids = sorted([a for a in avoid_ingredients if a in allergen_tags or re.search(r'(?<!\w)' + re.escape(a) + r'(?!\w)', text)])
        if hits or user_avoids:
            excluded.append({"recipe":r, "reason":"Identified forbidden ingredient/allergen: " + ", ".join(hits + user_avoids)})
            continue
        cautions = []
        if food_allergies and (not r["ingredient_list_complete"] or not r["preparation_cross_contact_verified"]):
            cautions.append("Allergy safety not established; full ingredients and cross-contact must be verified")
        if r["nutrition_data_status"] != "VERIFIED":
            cautions.append("Nutrition numbers are DEMO estimates; cannot establish clinical compliance")
        if r["price_data_status"] != "VERIFIED":
            cautions.append("Price is a demo estimate; not a current grocery quote")
        if "GERD" in profile.get("diagnoses", []) or "GERD" in ' '.join(profile.get('diagnoses', [])):
            if "tomato" in text or "pepper" in text:
                cautions.append("Possible reflux-related ingredients; use only if personally tolerated")
        clinical = profile.get("prescribed_constraints", [])
        for c in clinical:
            if c["metric"] == "carbohydrate_g" and c.get("scope") == "meal":
                amount = r["carbohydrate_g_per_serving_demo"]  # Per-meal target compares to one meal serving, not batch size
                if amount > c.get("target_approx", float("inf")):
                    cautions.append("Demo carbohydrate estimate is above simulated per-meal target; requires review")
            if c["metric"] == "sodium_mg" and c.get("scope") == "daily":
                cautions.append("Daily sodium limit is not a per-meal allowance; consider the whole day's intake")
        score = 0.0
        preference_bonus = 0.0
        matched_preference_tags = []
        if preference_weights is not None:
            # Explicit user-approved weights from Preference Analyst.
            # Medical/allergy exclusions above have already been applied.
            matched_preference_tags = sorted(
                tag for tag in r["preference_tags"]
                if preference_weights.get(tag, 0) > 0
            )
            preference_bonus = 2.0 * sum(
                preference_weights[tag] for tag in matched_preference_tags
            )
        elif use_receipt_hints:
            matched_preference_tags = sorted(
                tag for tag in r["preference_tags"] if hints["tags"].get(tag, 0) > 0
            )
            preference_bonus = sum(
                hints["tags"].get(tag, 0) for tag in matched_preference_tags
            ) * 2.0
        score += preference_bonus
        score += max(0, max_minutes-r["time_minutes_demo"]) / max(max_minutes,1)
        score += max(0, budget_usd-cost) / max(budget_usd,1)
        considered.append({"recipe":r,"estimated_total_cost_usd":round(cost,2),"score":round(score,3),"preference_score":round(preference_bonus,3),"matched_preference_tags":matched_preference_tags,"cautions":cautions,"allergy_review_required":bool(food_allergies and (not r["ingredient_list_complete"] or not r["preparation_cross_contact_verified"]))})
    return {"candidates":sorted(considered,key=lambda x:-x["score"]),"excluded":excluded,"taste_hints":hints}
