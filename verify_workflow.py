"""Manual offline smoke check for Healthy Foodie B + C + D + E agents.

Run from the project root: python verify_workflow.py
No Superlinked credentials or network connection required.
"""

from engine import load_json
from master_agent import run_meal_request

profiles = load_json("profiles.json")
recipes = load_json("recipes_demo.json")
receipts = load_json("receipts_curated.json")

for profile in profiles:
    plan = run_meal_request(
        profile=profile,
        recipes=recipes,
        receipts=receipts,
        meal_type="Any",
        budget_usd=12.0,
        max_minutes=45,
        servings=1,
        additional_synthetic_allergies=["peanut"],
        use_receipt_hints=True,
        selected_receipt_tags=["vegetables"],
        manual_preference_tags=["soup"],
    )
    print("\n---", profile["display_name"], "---")
    print("Status:", plan["status"])
    if plan["status"] != "ready":
        print("Review errors:", plan["dietologist"]["review_errors"])
        continue
    print("Observed purchase events:", plan["preferences"]["distinct_purchase_events"])
    print("Ignored duplicate slips:", plan["preferences"]["ignored_duplicate_receipts"])
    print("Selected preference weights:", plan["preferences"]["ranking_weights"])
    print("Daily clinician rules:", len(plan["dietologist"]["daily_limits"]))
    print("Per-meal clinician rules:", len(plan["dietologist"]["meal_limits"]))
    print("Excluded known allergens:", [
        item["recipe"]["name"]
        for item in plan["recommendations"]["excluded"]
    ])
    for item in plan["recommendations"]["candidates"][:3]:
        print(
            "  *", item["recipe"]["name"],
            "score:", item["score"],
            "preference bonus:", item["preference_score"],
            "source:", item["recipe"]["source_url"],
        )
    print("Trace:", " -> ".join(stage["stage"] for stage in plan["trace"]))
