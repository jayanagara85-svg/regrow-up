"""
USER STATE MACHINE — Redis-backed
Tracks where each user is in the conversation flow.

States:
  idle         → fresh / no active flow
  booking      → inside pickup booking flow
  marketplace  → inside sell listing flow
  community    → browsing community
  channel      → reading channel posts
"""
import json
from typing import Optional
from app.services.queue import get_redis

# TTL for conversation state: 30 minutes of inactivity resets to idle
STATE_TTL = 60 * 30


def _key(user_phone: str) -> str:
    return f"loopchat:state:{user_phone}"


def set_user_state(user_phone: str, state: str, extra: Optional[dict] = None) -> None:
    """Store user conversation state in Redis."""
    r = get_redis()
    payload = {"state": state, "data": extra or {}}
    r.setex(_key(user_phone), STATE_TTL, json.dumps(payload))


def get_user_state(user_phone: str) -> dict:
    """
    Retrieve user conversation state.
    Returns {"state": "idle", "data": {}} if no state found.
    """
    r = get_redis()
    raw = r.get(_key(user_phone))
    if raw:
        return json.loads(raw)
    return {"state": "idle", "data": {}}


def clear_user_state(user_phone: str) -> None:
    """Reset user back to idle."""
    r = get_redis()
    r.delete(_key(user_phone))


def update_state_data(user_phone: str, extra: dict) -> None:
    """Merge new data into existing state without changing the state name."""
    current = get_user_state(user_phone)
    current["data"].update(extra)
    set_user_state(user_phone, current["state"], current["data"])
