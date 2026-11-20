"""Healthy Foodie - Master Orchestrator (offline, deterministic).

Sequence: reviewed synthetic clinician constraints -> weak optional taste hints
-> existing deterministic Cook Agent recommendations -> source-grounded notes.
No model calls occur here; optional LLM explanations happen only on user click.
"""

from typing import Any, Mapping, Sequence

from cook_agent import recommend
from dietologist_agent import review_profile, review_recipe
from preference_agent import analyze_preferences


def recipe_key(recipe: Mapping[str, Any]) -> str:
    """Use the real starter-kit 'recipe_id' field, without assuming 'id'."""
    identifier = recipe.get("recipe_id") or recipe.get("source_url") or recipe.get("name")
    if not identifier:
        raise ValueError("Recipe is missing a stable identifier and source.")
    return str(identifier)


def run_meal_request(
    *,
    profile: Mapping[str, Any],
    recipes: Sequence[dict[str, Any]],
    receipts: Sequence[Mapping[str, Any]],
    meal_type: str,
    budget_usd: float,
    max_minutes: int,
    servings: int = 1,
    selected_cuisines: Sequence[str] = (),
    avoid_ingredients: Sequence[str] = (),
    additional_synthetic_allergies: Sequence[str] = (),
    use_receipt_hints: bool = False,
    selected_receipt_tags: Sequence[str] | None = None,
    manual_preference_tags: Sequence[str] = (),
) -> dict[str, Any]:
    """Return one stable, auditable result for the Streamlit app.

    Non-reviewed clinician instructions block the recommendation stage;
    receipt and manual preferences can never cancel an exclusion.
    """
    trace = []
    clinical = review_profile(
        profile, additional_synthetic_allergies=additional_synthetic_allergies
    )
    trace.append({
        "stage": "Dietologist",
        "status": "ready" if clinical["ready"] else "review_required",
        "detail": "Reviewed synthetic clinician orders; scope preserved.",
    })

    if not clinical["ready"]:
        return {
            "status": "review_required",
            "dietologist": clinical,
            "preferences": None,
            "recommendations": {"candidates": [], "excluded": [], "taste_hints": {"tags": {}}},
            "recipe_reviews": {},
            "trace": trace,
        }

    recipe_tags = sorted({t for recipe in recipes for t in recipe["preference_tags"]})
    preference_report = analyze_preferences(
        receipts,
        recipe_tags,
        use_receipts=use_receipt_hints,
        selected_receipt_tags=selected_receipt_tags,
        manual_tags=manual_preference_tags,
    )
    trace.append({
        "stage": "Preference Analyst",
        "status": "ready",
        "detail": (
            f"{len(preference_report['ranking_weights'])} user-approved "
            "preference tag(s); no medical inference."
        ),
    })

    # Pass only bounded numeric taste weights to Cook Agent, never raw receipts.
    result = recommend(
        profile=clinical["effective_profile"],
        recipes=recipes,
        meal_type=meal_type,
        budget_usd=budget_usd,
        max_minutes=max_minutes,
        servings=servings,
        selected_cuisines=selected_cuisines,
        avoid_ingredients=avoid_ingredients,
        use_receipt_hints=False,
        receipts=None,
        preference_weights=preference_report["ranking_weights"],
    )
    result["taste_hints"] = {
        "tags": preference_report["observed_tag_counts"],
        "selected_receipt_tags": preference_report["selected_receipt_tags"],
        "manual_tags": preference_report["manual_tags"],
    }
    reviews = {
        recipe_key(item["recipe"]): review_recipe(item["recipe"], clinical)
        for item in result["candidates"]
    }
    trace.append({
        "stage": "Cook Agent",
        "status": "ready",
        "detail": (
            f"{len(result['candidates'])} preliminary candidate(s), "
            f"{len(result['excluded'])} identified ingredient/allergen exclusion(s); "
            "nutrition and cost remain demo estimates."
        ),
    })
    trace.append({
        "stage": "Master",
        "status": "ready",
        "detail": (
            "Collected source-linked recipe options; optional Superlinked "
            "explanation is requested separately on button click."
        ),
    })
    return {
        "status": "ready",
        "dietologist": clinical,
        "preferences": preference_report,
        "recommendations": result,
        "recipe_reviews": reviews,
        "trace": trace,
    }
