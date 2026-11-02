"""
Google API key rotation for the Sparkleen Krystal Record Keeper.

Supports two Google/Gemini API keys (from two separate Google Cloud
projects) and fails over from the active key to the other one when
the active key's free-tier daily quota is exhausted.

Scope: solo-testing convenience to stretch free-tier limits. In a
real client deployment, the client should use their own paid key.

How it works:
- Two keys are read from env: GOOGLE_API_KEY_1, GOOGLE_API_KEY_2.
- The active key is written to os.environ["GOOGLE_API_KEY"].
  ADK reads that env var at call time (verified on Colab), so
  swapping it is enough — no runner rebuild needed.
- On a 429 / RESOURCE_EXHAUSTED / quota error, the rotator switches
  to the next key and retries the SAME call once.
- On the first call after midnight Pacific Time, the rotator resets
  to key 1 so a fresh daily quota is used.
"""

import os
from datetime import datetime, timezone, timedelta

# Google's daily quota resets at midnight Pacific Time.
# PDT is UTC-7, PST is UTC-8. Using a fixed UTC-7 offset is a safe
# approximation: it means we reset up to 1 hour later than PST
# midnight in winter — harmless (we just wait a bit longer).
PACIFIC = timezone(timedelta(hours=-7))


class KeyRotationExhausted(Exception):
    """Raised when all available keys have hit their quota."""
    pass


def _is_quota_error(exception):
    """Detects a quota / rate-limit error from the Gemini API.

    Prefers structured markers from the SDK/REST response, then
    falls back to looser text markers. Kept defensive on purpose:
    the exact exception class varies across ADK/google-genai
    versions and transports.
    """
    message = str(exception).lower()

    # Structured markers — checked first, they're unambiguous.
    structured = ["429", "resource_exhausted", "resource exhausted"]
    if any(marker in message for marker in structured):
        return True

    # Loose markers — only used if nothing structured matched.
    loose = ["quota exceeded", "rate limit exceeded", "rate_limit_exceeded"]
    if any(marker in message for marker in loose):
        return True

    return False


def _pacific_today():
    """Returns today's date in Pacific Time as 'YYYY-MM-DD'."""
    return datetime.now(PACIFIC).strftime("%Y-%m-%d")


class GoogleKeyRotator:
    """
    Holds two Google API keys and manages which one is active via
    os.environ["GOOGLE_API_KEY"].
    """

    def __init__(self, key_1, key_2):
        if not key_1 and not key_2:
            raise ValueError("At least one Google API key must be provided.")

        # Filter out any missing key so rotation still works with just one.
        self.keys = [k for k in (key_1, key_2) if k]
        self.active_index = 0
        self._rotated_on = None  # Pacific date when we last flipped to key 2
        self._apply_active_key()

    def _apply_active_key(self):
        os.environ["GOOGLE_API_KEY"] = self.keys[self.active_index]

    def current_key_label(self):
        """Human-readable label for logs. Never the key itself."""
        return f"key_{self.active_index + 1}_of_{len(self.keys)}"

    def _maybe_reset_daily(self):
        """If we rotated on an earlier Pacific day, reset to key 1.

        Called at the start of call_with_failover, before any attempt.
        """
        if self._rotated_on is None:
            return
        if _pacific_today() != self._rotated_on:
            self.active_index = 0
            self._rotated_on = None
            self._apply_active_key()

    def rotate(self):
        """Switches to the next key in the list, if one exists.

        Returns True if a different key is now active, False if
        there's no other key to switch to (single-key setup, or
        we've already cycled through all keys).
        """
        if len(self.keys) < 2:
            return False

        self.active_index = (self.active_index + 1) % len(self.keys)
        self._rotated_on = _pacific_today()
        self._apply_active_key()
        return True

    async def call_with_failover(self, async_fn, *args, **kwargs):
        """Calls async_fn(*args, **kwargs), retrying once per additional
        key on a quota-exceeded error.

        Raises KeyRotationExhausted if every key has been tried and
        all failed with quota errors. Any non-quota error is raised
        immediately (rotating keys won't fix a real bug).
        """
        # Roll over to key 1 at the start of a new Pacific day.
        self._maybe_reset_daily()

        attempts = len(self.keys)
        last_error = None

        for attempt in range(attempts):
            try:
                return await async_fn(*args, **kwargs)
            except Exception as e:
                if not _is_quota_error(e):
                    raise  # Not a quota issue — don't waste the other key.

                last_error = e
                if attempt < attempts - 1:
                    self.rotate()

        raise KeyRotationExhausted(
            f"All {attempts} Google API key(s) hit their quota limit. "
            f"Last error: {last_error}"
        )
