"""Healthy Foodie Streamlit meal advisor with coordinated agents."""

import hashlib
import json
import os

import streamlit as st

from engine import load_json
from cook_agent import explain_recipe
from preference_agent import analyze_preferences
from master_agent import run_meal_request

from datetime import datetime


st.set_page_config(page_title="Healthy Foodie | Meal Advisor", layout="wide")
st.title("Healthy Foodie | Meal Advisor")
st.caption(f"Last application execution: {datetime.now().strftime('%H:%M:%S')}")
st.caption(
    "Health profiles are derived from simulated user's medical records;"
    "Nutrition and prices are unverified estimates;"
    "This application does not establish medical or allergy safety."
)

profiles = load_json("profiles.json")
recipes = load_json("recipes_demo.json")
receipts = load_json("receipts_curated.json")
profile_by_id = {profile["id"]: profile for profile in profiles}
recipe_tag_vocabulary = sorted({tag for recipe in recipes for tag in recipe["preference_tags"]})
receipt_preview = analyze_preferences(receipts, recipe_tag_vocabulary)

with st.sidebar:
    st.header("Your meal preferences")
    profile_id = st.selectbox(
        "Health profile",
        [profile["id"] for profile in profiles],
        format_func=lambda profile_id: profile_by_id[profile_id]["display_name"],
    )
    profile = profile_by_id[profile_id]
    meal = st.selectbox("Meal", ["Any", "breakfast", "lunch", "dinner"])
    budget = st.number_input(
        "Total food budget (USD; estimated)",
        min_value=2.0,
        max_value=200.0,
        value=12.0,
        step=1.0,
    )
    maximum = st.slider("Maximum cooking time (minutes)", 10, 120, 45, 5)
    servings = st.number_input("Portions", min_value=1, max_value=8, value=1)
    cuisines = st.multiselect(
        "Cuisine (optional)", sorted({recipe["cuisine"] for recipe in recipes})
    )
    allergies = st.multiselect(
        "Additional food allergies to exclude",
        ["peanut", "sesame", "milk", "egg", "fish", "wheat", "soy", "shellfish", "tree_nuts"],
    )
    avoid = st.text_input(
        "Avoid ingredient(s), separated by commas",
        placeholder="e.g. tomato, garlic",
    )
    use_purchases = st.checkbox(
        "Use sample purchases as weak taste hints", value=False
    )
    if use_purchases:
        selected_receipt_tags = st.multiselect(
            "Receipt-derived tags to include in ranking",
            options=receipt_preview["suggested_receipt_tags"],
            default=receipt_preview["suggested_receipt_tags"],
            help=("Only high/medium-confidence reviewed food tags that also "
                  "match the recipe dataset. Deselect any uncertain taste hint."),
        )
    else:
        selected_receipt_tags = []
    manual_preference_tags = st.multiselect(
        "My preferred food categories (optional)",
        options=recipe_tag_vocabulary,
        help="Optional user preferences. These never override allergy or medical rules.",
    )

# Master Agent coordinates the reviewed Dietologist rules, Preference Analyst,
# and deterministic Cook Agent. It does not invoke an external model.
plan = run_meal_request(
    profile=profile,
    recipes=recipes,
    receipts=receipts,
    meal_type=meal,
    budget_usd=budget,
    max_minutes=maximum,
    servings=int(servings),
    selected_cuisines=cuisines,
    avoid_ingredients=[part.strip() for part in avoid.split(",")],
    additional_synthetic_allergies=allergies,
    use_receipt_hints=use_purchases,
    selected_receipt_tags=selected_receipt_tags,
    manual_preference_tags=manual_preference_tags,
)

dietologist_report = plan["dietologist"]
if plan["status"] != "ready":
    st.error(
        "Dietologist Agent: the selected profile has unsupported or "
        "conflicting instructions. Clinical review is required."
    )
    for error in dietologist_report["review_errors"]:
        st.warning(error)
    st.stop()  # Never bypass unreviewed clinical orders.

effective_profile = dietologist_report["effective_profile"]
preference_report = plan["preferences"]
result = plan["recommendations"]

st.subheader("Profile summary")
st.write("**Selected profile:**", profile["display_name"])
if profile["diagnoses"]:
    st.write(
        "**Health conditions (example profile):**", "; ".join(profile["diagnoses"])
    )
st.subheader("Dietologist Agent | Clinician instructions")
with st.expander("View dietary restrictions and uncertainties", expanded=profile_id != "guest"):
    st.caption(
        "Source: " + str(dietologist_report["profile_source"])
        + ". Only pre-reviewed example-profile instructions are used; no new medical limits are generated."
    )
    if dietologist_report["daily_limits"]:
        for limit in dietologist_report["daily_limits"]:
            st.write(
                f"**Daily limit (not per meal):** {limit['metric']} "
                f"{limit['operator']} {limit['value']:g} {limit['unit']} "
                f"— {limit['origin']}"
            )
    if dietologist_report["meal_limits"]:
        for limit in dietologist_report["meal_limits"]:
            st.write(
                f"**Per-meal instruction:** {limit['metric']} "
                f"{limit['operator']} {limit['value']:g} {limit['unit']} "
                f"— {limit['origin']}"
            )
    if not (dietologist_report["daily_limits"] or dietologist_report["meal_limits"]):
        st.write("No clinician-prescribed nutrient targets in this profile.")
    if dietologist_report["hard_avoid"]:
        st.write("**Food-allergy exclusions:**")
        for exclusion in dietologist_report["hard_avoid"]:
            basis = exclusion["basis"]
            if basis == "explicit synthetic UI selection":
                basis = "selected in this session"
            elif basis == "pre-reviewed synthetic profile":
                basis = "documented in the example profile"
            st.write(f"- {exclusion['allergen']} ({basis})")
    if dietologist_report["personal_triggers"]:
        st.write(
            "**Individually recorded potential triggers:** "
            + ", ".join(dietologist_report["personal_triggers"])
        )
    for flag in dietologist_report["clinical_flags"]:
        st.write(f"**Clinical handling note:** {flag}")
    for uncertainty in dietologist_report["uncertainties"]:
        st.caption("Uncertainty: " + uncertainty)

st.subheader("Preference Analyst | User-controlled tastes")
if use_purchases:
    st.write("**Receipt-derived ranking tags:**", preference_report["selected_receipt_tags"])
else:
    st.write("Receipt-derived ranking is turned off.")
if preference_report["manual_tags"]:
    st.write("**Manually selected preferences:**", preference_report["manual_tags"])
with st.expander("See receipt evidence and ranking weights", expanded=False):
    st.write(
        "**Distinct purchase events:**", preference_report["distinct_purchase_events"]
    )
    st.write(
        "**Duplicate slips ignored:**", preference_report["ignored_duplicate_receipts"]
    )
    st.write(
        "**Low/unknown-confidence food lines ignored:**",
        preference_report["ignored_low_confidence_food_lines"],
    )
    st.write(
        "**Receipt tags matching available recipes:**",
        preference_report["recipe_matched_tag_counts"],
    )
    st.write("**Ranking weights:**", preference_report["ranking_weights"])
    st.caption(preference_report["interpretation"])
    st.caption(
        "Observed tags like sushi or Japanese may not match a recipe tag and "
        "therefore do not affect ranking. Receipt purchase prices are never "
        "used to infer the meal budget."
    )

st.subheader(f"Meal options ({len(result['candidates'])})")
if not result["candidates"]:
    st.warning(
        "No meal options match the current filters. Try another meal, budget, "
        "or cooking time; keep confirmed allergy exclusions in place."
    )

for item in result["candidates"][:6]:
    recipe = item["recipe"]
    with st.expander(
        f"{recipe['name']} · {recipe['cuisine']} · "
        f"{recipe['time_minutes_demo']} min · "
        f"${item['estimated_total_cost_usd']:.2f} estimated",
        expanded=True,
    ):
        st.write(
            "**Nutrition / serving (estimated):**",
            f"~{recipe['energy_kcal_per_serving_demo']} kcal, "
            f"~{recipe['carbohydrate_g_per_serving_demo']} g carbohydrate, "
            f"~{recipe['sodium_mg_per_serving_demo']} mg sodium",
        )
        st.write(
            "**Ingredient overview (not complete):**", recipe["ingredient_summary"]
        )
        st.markdown(
            f"[Open original complete recipe]({recipe['source_url']})"
        )

        # Original warnings remain visible whether or not AI is used.
        for caution in item["cautions"]:
            st.warning(caution)
        if item["allergy_review_required"]:
            st.error(
                "NOT VERIFIED FOR FOOD ALLERGY. Do not interpret as safe to eat."
            )

        # Clinician rules are reviewed once above and enforced by the Master
        # Agent before ranking. Retain recipe-specific safety warnings, but do
        # not duplicate the Dietologist section within each meal option.

        if item.get("matched_preference_tags"):
            st.caption(
                "Taste-ranking matches (not safety evidence): "
                + ", ".join(item["matched_preference_tags"])
                + f" | preference score: {item['preference_score']:.1f}"
            )

        # Keyed to current user inputs to avoid showing stale explanations
        # after a profile, allergy, portion, or recipe-setting change.

        # Identify the recipe without assuming an "id" exists.
        explanation_context = {
            "recipe_id": (
                recipe.get("recipe_id")
                or recipe.get("source_url")
                or recipe.get("name")
            ),
            "profile_id": profile_id,
            "allergies": effective_profile["confirmed_food_allergens"],
            "avoid": avoid,
            "meal": meal,
            "budget": budget,
            "servings": int(servings),
            "maximum": maximum,
            "cautions": item["cautions"],
            "clinician_rules": effective_profile["prescribed_constraints"],
            "user_approved_preference_weights": preference_report["ranking_weights"],
            "model": os.getenv("SIE_MODEL", "Qwen/Qwen3.5-4B"),
        }

        fingerprint = hashlib.sha256(
            json.dumps(
                explanation_context,
                sort_keys=True
            ).encode("utf-8")
        ).hexdigest()[:16]

        cache_key = f"cook_explanation_{fingerprint}"

        if st.button(
            "Ask Cook Agent for cooking advice",
            key=f"cook_agent_{fingerprint}",
        ):
            if not os.getenv("SIE_API_KEY"):
                st.error(
                    "Superlinked API key is not configured."
                )
            else:
                try:
                    with st.spinner(
                        "Cook Agent is preparing an explanation..."
                    ):
                        st.session_state[cache_key] = explain_recipe(
                            recipe=recipe,
                            cautions=item["cautions"],
                            meal=meal,
                            budget=budget,
                            servings=int(servings),
                            preference_context={
                                "receipt_derived_hypotheses": preference_report[
                                    "selected_receipt_tags"
                                ],
                                "explicit_user_preferences": preference_report[
                                    "manual_tags"
                                ],
                            },
                        )
                except Exception as exc:
                    st.error(
                        "Cook Agent request failed "
                        f"({type(exc).__name__}). "
                        "Check model access and API configuration."
                    )

        if cache_key in st.session_state:
            st.subheader("Cook Agent | AI cooking advice")
            st.write(st.session_state[cache_key])
            st.caption(
                "AI-generated explanation only. "
                "All medical and allergy warnings remain applicable."
            )


with st.expander("Master Agent | Execution trace", expanded=False):
    for step in plan["trace"]:
        detail = step["detail"].replace(
            "Reviewed synthetic clinician orders; scope preserved.",
            "Reviewed clinician instructions from the example profile; scope preserved.",
        ).replace("preliminary candidate(s)", "meal option(s)")
        st.write(f"**{step['stage']} — {step['status']}:** {detail}")

if result["excluded"]:
    with st.expander(
        f"Excluded for identified restricted ingredients "
        f"({len(result['excluded'])})"
    ):
        for item in result["excluded"]:
            st.write(item["recipe"]["name"] + ": " + item["reason"])

st.divider()
st.caption(
    "No uploaded real health records, payment identifiers, or receipt photos "
    "are stored by this application. The optional AI request shares recipe summaries, "
    "estimated figures and existing cautions with Superlinked, not patient files. "
    "Seek a clinician or registered dietitian for patient-specific dietary decisions."
)
