"""Healthy Foodie - Preference Analyst (deterministic, synthetic demo).

Reads curated food tags from de-duplicated receipt records as weak hypotheses.
Does not infer food allergies, diagnoses, income, calorie targets, identity,
or lifelong dietary preferences. No raw receipts or payment data leave Python.
"""

from collections import Counter
from typing import Any, Mapping, Sequence


ACCEPTED_CONFIDENCE = frozenset({"high", "medium"})
RECEIPT_TAG_WEIGHT = 1.0  # deliberately weaker than an explicit UI preference
MANUAL_TAG_WEIGHT = 2.0


def analyze_preferences(
    receipts: Sequence[Mapping[str, Any]],
    recipe_tags: Sequence[str],
    *,
    use_receipts: bool = False,
    selected_receipt_tags: Sequence[str] | None = None,
    manual_tags: Sequence[str] = (),
) -> dict[str, Any]:
    """Return transparent, bounded weights for the Cook Agent's recipe scorer.

    Only curated, high/medium-confidence FOOD entries contribute. Payment
    slips and duplicate receipt IDs are ignored. Receipt tags affect ranking
    ONLY after the user enables receipt hints, and the user can deselect any
    tag. Manual preference tags are separate and more influential.

    selected_receipt_tags=None opts into every observed *recipe-matching* tag
    when use_receipts=True. An empty list opts into none.
    """
    available = set(recipe_tags)
    counts: Counter[str] = Counter()
    counted_lines = 0
    ignored_low_confidence_lines = 0
    ignored_duplicate_receipts = 0
    distinct_purchase_events = 0
    processed_ids: set[str] = set()

    for receipt in receipts:
        if receipt.get("duplicate_of"):
            ignored_duplicate_receipts += 1
            continue
        receipt_id = receipt.get("receipt_id")
        if not isinstance(receipt_id, str) or not receipt_id.strip():
            raise ValueError("Receipt lacks a reviewed receipt_id.")
        if receipt_id in processed_ids:
            ignored_duplicate_receipts += 1
            continue
        processed_ids.add(receipt_id)
        distinct_purchase_events += 1
        for food in receipt.get("foods", []):
            if not isinstance(food, Mapping):
                raise ValueError("Invalid curated receipt food entry.")
            confidence = str(food.get("confidence") or "").lower()
            if confidence not in ACCEPTED_CONFIDENCE:
                ignored_low_confidence_lines += 1
                continue
            food_tags = food.get("tags", [])
            if not isinstance(food_tags, list):
                raise ValueError("Curated receipt tags must be a list.")
            counted_lines += 1
            counts.update({tag for tag in food_tags if isinstance(tag, str)})

    recipe_matched = {
        tag: counts[tag]
        for tag in sorted(available)
        if counts[tag] > 0
    }
    suggestion_order = sorted(
        recipe_matched, key=lambda tag: (-recipe_matched[tag], tag)
    )
    receipt_selection = (
        list(suggestion_order) if selected_receipt_tags is None
        else list(selected_receipt_tags)
    ) if use_receipts else []

    unknown_receipt = set(receipt_selection) - set(suggestion_order)
    if unknown_receipt:
        raise ValueError(
            "Unrecognized receipt-derived preference tags: "
            + ", ".join(sorted(unknown_receipt))
        )
    unknown_manual = set(manual_tags) - available
    if unknown_manual:
        raise ValueError(
            "Unrecognized manually selected recipe tags: "
            + ", ".join(sorted(unknown_manual))
        )

    weights: dict[str, float] = {}
    for tag in receipt_selection:
        weights[tag] = RECEIPT_TAG_WEIGHT
    for tag in manual_tags:
        weights[tag] = weights.get(tag, 0) + MANUAL_TAG_WEIGHT

    return {
        "observed_tag_counts": dict(sorted(counts.items())),
        "recipe_matched_tag_counts": recipe_matched,
        "suggested_receipt_tags": suggestion_order,
        "selected_receipt_tags": sorted(set(receipt_selection)),
        "manual_tags": sorted(set(manual_tags)),
        "ranking_weights": dict(sorted(weights.items())),
        "distinct_purchase_events": distinct_purchase_events,
        "counted_food_lines": counted_lines,
        "ignored_low_confidence_food_lines": ignored_low_confidence_lines,
        "ignored_duplicate_receipts": ignored_duplicate_receipts,
        "interpretation": (
            "Receipt tags are weak food-purchase hypotheses, not proven user "
            "preferences, food-allergy evidence, medical instructions or a "
            "basis for a USD budget. Only tags also present in recipe data "
            "can affect recipe ranking."
        ),
    }
