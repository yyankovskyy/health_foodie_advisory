"""Opt-in, anonymous Amplitude event tracking for Healthy Foodie.

No profiles, allergens, diagnoses, receipts, recipe choices, prompts, or model
outputs are ever sent by this module. Only approved fixed event names and a
random, temporary Streamlit-session device ID are transmitted.
"""

import os
from functools import lru_cache

# Optional local .env configuration; exported variables always take priority.
try:
    from dotenv import load_dotenv
except ImportError:
    pass
else:
    load_dotenv()

# Fixed, audited event taxonomy. Deliberately no event properties.
ALLOWED_EVENTS = frozenset({
    "HF Session Started",
    "HF Meal Options Displayed",
    "HF Cook Advice Requested",
    "HF Cook Advice Succeeded",
    "HF Cook Advice Failed",
})


@lru_cache(maxsize=2)
def _amplitude_client(api_key: str):
    # Lazy import keeps recommendation workflow working without this package.
    from amplitude import Amplitude

    client = Amplitude(api_key)
    client.configuration.flush_queue_size = 1  # Fast uploads for demo events.
    return client


def track_event(event_type: str, *, device_id: str, consent: bool) -> bool:
    """Queue a fixed anonymous event; return False if tracking is unavailable.

    Never let optional telemetry interrupt meal recommendations. API key
    and consent are both required. A generated ephemeral ID is preferred.
    """
    if not consent:
        return False
    if event_type not in ALLOWED_EVENTS:
        raise ValueError(f"Unapproved analytics event: {event_type}")
    if not device_id:
        raise ValueError("Anonymous session device_id is required")

    api_key = os.getenv("AMPLITUDE_API_KEY", "").strip()
    if not api_key:
        return False

    try:
        from amplitude import BaseEvent

        _amplitude_client(api_key).track(
            BaseEvent(event_type=event_type, device_id=device_id)
        )
    except Exception:
        # Telemetry is intentionally best effort; no sensitive detail logged.
        return False
    return True
