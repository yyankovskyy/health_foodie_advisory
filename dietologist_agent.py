"""Healthy Foodie - Dietologist Agent (deterministic MVP).

Reads ONLY locally reviewed synthetic profile records from data/profiles.json.
It does not extract new orders from PDFs, prescribe targets, diagnose, or call
an LLM. Unknown, contradictory or unsupported rules block profile processing
until a human reviews the source profile.

Public API:
    report = review_profile(profile, additional_synthetic_allergies=[...])
    observations = review_recipe(recipe, report)

`report['effective_profile']` is the normalized profile passed to engine.recommend.
"""

from copy import deepcopy
from math import isfinite
from typing import Any, Mapping, Sequence


# Tags used by the existing recipe engine. Other allergens require a reviewed
# mapping from ingredient names to clinical allergen categories before use.
SUPPORTED_ALLERGEN_TAGS = frozenset({
    "peanut", "sesame", "milk", "egg", "fish", "wheat", "soy",
    "shellfish", "tree_nuts",
})

# Only rules already represented in the reviewed synthetic profiles are
# supported. We deliberately DO NOT derive potassium, caloric or other limits.
SUPPORTED_ORDERS = {
    ("sodium_mg", "daily"): "max",
    ("carbohydrate_g", "meal"): "target_approx",
}


def _positive_finite_number(value: Any) -> bool:
    return (isinstance(value, (int, float))
            and not isinstance(value, bool)
            and isfinite(value)
            and value > 0)


def _nonnegative_finite_number(value: Any) -> bool:
    return (isinstance(value, (int, float))
            and not isinstance(value, bool)
            and isfinite(value)
            and value >= 0)


def review_profile(
    profile: Mapping[str, Any],
    additional_synthetic_allergies: Sequence[str] = (),
) -> dict[str, Any]:
    """Validate and structure clinician-origin constraints, without invention.

    `additional_synthetic_allergies` contains explicit allergy tags selected
    in the DEMO UI, not allergies inferred from diagnoses or receipts.
    Return `ready=False` with errors for unsupported/ambiguous orders; the
    application must not pass those profiles to `recommend()`.
    """
    if profile.get("synthetic") is not True:
        raise ValueError(
            "Dietologist MVP accepts only pre-reviewed synthetic profiles. "
            "Real medical records must not be loaded into this demo."
        )

    errors: list[str] = []
    profile_id = str(profile.get("id") or "")
    if not profile_id:
        errors.append("Profile ID is missing.")

    original_allergens = profile.get("confirmed_food_allergens", [])
    if not isinstance(original_allergens, list):
        errors.append("Profile food-allergen list has invalid format.")
        original_allergens = []

    allergen_source: dict[str, str] = {}
    for raw, source in (
        [(v, "pre-reviewed synthetic profile") for v in original_allergens]
        + [(v, "explicit synthetic UI selection") for v in additional_synthetic_allergies]
    ):
        if not isinstance(raw, str):
            errors.append("A food allergen has an invalid non-text value.")
            continue
        tag = raw.strip().lower()
        if tag not in SUPPORTED_ALLERGEN_TAGS:
            errors.append(f"Unsupported food-allergen tag {raw!r}; review required.")
            continue
        # Preserve the source in the original profile when both sources occur.
        if tag not in allergen_source:
            allergen_source[tag] = source

    raw_constraints = profile.get("prescribed_constraints", [])
    if not isinstance(raw_constraints, list):
        errors.append("Clinician constraint list has invalid format.")
        raw_constraints = []

    validated_constraints: list[dict[str, Any]] = []
    daily_limits: list[dict[str, Any]] = []
    meal_limits: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for index, raw in enumerate(raw_constraints, start=1):
        if not isinstance(raw, dict):
            errors.append(f"Clinician instruction {index} has invalid format.")
            continue
        metric = raw.get("metric")
        scope = raw.get("scope")
        pair = (metric, scope)
        if pair not in SUPPORTED_ORDERS:
            errors.append(
                f"Unsupported instruction {metric!r} / {scope!r}; "
                "do not infer a limit or change its scope."
            )
            continue
        if pair in seen:
            errors.append(
                f"Duplicate or potentially conflicting clinician rule for "
                f"{metric}/{scope}; source review required."
            )
            continue
        seen.add(pair)
        limit_field = SUPPORTED_ORDERS[pair]
        value = raw.get(limit_field)
        if not _positive_finite_number(value):
            errors.append(
                f"Clinician instruction {metric}/{scope} requires a positive "
                f"numeric {limit_field}."
            )
            continue
        if (limit_field == "max" and "target_approx" in raw) or (
            limit_field == "target_approx" and "max" in raw
        ):
            errors.append(f"Ambiguous maximum/target fields for {metric}/{scope}.")
            continue
        origin = raw.get("origin")
        if not isinstance(origin, str) or not origin.strip():
            errors.append(f"Missing reviewed source for {metric}/{scope}.")
            continue

        constraint = deepcopy(raw)
        validated_constraints.append(constraint)
        entry = {
            "id": constraint.get("id", f"{metric}_{scope}"),
            "metric": metric,
            "scope": scope,
            "origin": origin,
            "value": value,
            "operator": "maximum" if limit_field == "max" else "approximate target",
            "unit": "mg/day" if pair == ("sodium_mg", "daily") else "g/meal",
        }
        if scope == "daily":
            daily_limits.append(entry)
        else:
            meal_limits.append(entry)

    raw_triggers = profile.get("personal_trigger_ingredients", [])
    if not isinstance(raw_triggers, list) or not all(
        isinstance(x, str) for x in raw_triggers
    ):
        errors.append("Personal-trigger list has invalid format.")
        raw_triggers = []

    uncertainties = [
        "Recipe nutrient estimates and ingredient summaries are unverified demo data; "
        "no medical or food-allergy safety conclusion can be made."
    ]
    if not allergen_source:
        uncertainties.append(
            "No food allergens are confirmed in this simulation; this does NOT "
            "prove there are no food allergies."
        )
    if not raw_constraints:
        uncertainties.append(
            "No clinician nutrient targets are documented in this profile; "
            "no targets have been invented."
        )

    effective_profile = deepcopy(dict(profile))
    effective_profile["confirmed_food_allergens"] = sorted(allergen_source)
    effective_profile["prescribed_constraints"] = validated_constraints

    return {
        "profile_id": profile_id,
        "profile_source": profile.get("source", "Unspecified synthetic source"),
        "ready": not errors,
        "review_errors": errors,
        "hard_avoid": [
            {"allergen": tag, "basis": allergen_source[tag]}
            for tag in sorted(allergen_source)
        ],
        "daily_limits": daily_limits,
        "meal_limits": meal_limits,
        "personal_triggers": [x.strip() for x in raw_triggers if x.strip()],
        "guideline_ids": [],  # No retrieved/approved guideline sources in this MVP.
        "clinical_flags": list(profile.get("clinical_flags") or []),
        "uncertainties": uncertainties,
        "effective_profile": effective_profile,
    }


def review_recipe(recipe: Mapping[str, Any], profile_review: Mapping[str, Any]) -> list[str]:
    """Source-grounded observations for ONE recipe serving; no safety verdict.

    Household `servings` is deliberately NOT used to scale a per-meal target.
    A daily target is never converted to a per-meal allowance.
    """
    if not profile_review.get("ready", False):
        raise ValueError("Cannot assess recipes against an unreviewed profile.")

    notes: list[str] = []
    for limit in profile_review["daily_limits"]:
        # Only a supported daily sodium rule is possible after validation.
        sodium = recipe.get("sodium_mg_per_serving_demo")
        amount = f"~{sodium:g} mg/serving" if _nonnegative_finite_number(sodium) else "unknown"
        notes.append(
            f"Simulated clinician rule: sodium maximum {limit['value']:g} mg/DAY "
            f"(source: {limit['origin']}). This recipe's sodium is {amount} "
            "(unverified DEMO); no per-meal allowance or daily compliance is inferred."
        )

    for limit in profile_review["meal_limits"]:
        carbs = recipe.get("carbohydrate_g_per_serving_demo")
        target = limit["value"]
        if _nonnegative_finite_number(carbs):
            comparison = (
                "above" if carbs > target
                else "below or equal to"
            )
            notes.append(
                f"Simulated clinician target: approximately {target:g} g "
                f"carbohydrate/MEAL (source: {limit['origin']}). "
                f"Unverified DEMO estimate: ~{carbs:g} g per recipe serving "
                f"({comparison} the target); clinical compliance cannot be determined."
            )
        else:
            notes.append(
                f"Simulated clinician target: approximately {target:g} g "
                "carbohydrate/MEAL; recipe carbohydrate data are unavailable."
            )

    if profile_review["hard_avoid"]:
        notes.append(
            "The Cook Agent excludes identified allergens using incomplete "
            "recipe summaries. Full ingredient and cross-contact verification "
            "is still required; no allergy-safe claim is made."
        )
    if profile_review["personal_triggers"]:
        notes.append(
            "Profile lists personal trigger ingredients; review the complete "
            "recipe and individual tolerability instead of assuming a universal prohibition."
        )
    return notes
