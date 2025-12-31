"""
Configuration for MapleStory Idle Party Quest Bot
"""

# ADB Configuration
# ADB_DEVICE will be auto-detected from the first available device
# Screen dimensions will be auto-detected from the screenshot

# Timing Configuration (in seconds)
POLL_INTERVAL = 0.3          # How often to check screen state (faster for Accept popup)
MATCHMAKING_TIMEOUT = 120    # Max time to wait for match (2 min) - legacy
QUEUE_TIMEOUT = 180          # Max time in queue before cancelling and re-queuing (3 min)
DUNGEON_TIMEOUT = 360        # Max time for dungeon completion (6 min)
CLICK_DELAY = 0.15           # Delay after clicking

# Click Configuration
CLICK_FUZZINESS_X = 100         # Random offset range for clicks (±pixels) to make clicks more human-like
CLICK_FUZZINESS_Y = 20         # Random offset range for clicks (±pixels) to make clicks more human-like

# Timing Fuzziness Configuration
TIMING_FUZZINESS = 0.15      # Random variation for timing (±15% of base value) to make behavior more human-like

# Button coordinates (stored as relative positions 0.0-1.0 for resolution independence)
# These were calibrated for 1920x1080 and will scale to any resolution
# Format: (x_percentage, y_percentage) where 0.0 = left/top, 1.0 = right/bottom
BUTTONS_RELATIVE = {
    "auto_match": (0.8802, 0.9306),  # Auto Match button (bottom right, green) - solo queue
    "enter": (0.6328, 0.9028),       # Enter button (cyan) - group/premade party
    "accept": (0.5, 0.7454),         # Accept button in matchmaking popup (centered)
    "leave": (0.5, 0.9352),          # Leave button on clear screen
    "ok": (0.5, 0.6546),             # OK button on error/notice dialogs (centered)
    "close": (0.958, 0.039),         # X button to close screen (top right corner)
    "cancel_queue": (0.617, 0.116),  # X button on matchmaking popup to cancel queue
}

# Template matching threshold (0-1, higher = stricter matching)
# Lower this if detection is missing buttons, raise if getting false positives
# 0.90 prevents false positives from similar-looking cyan buttons
MATCH_THRESHOLD = 0.90


def fuzzy_time(base_time: float) -> float:
    """
    Add random variation to timing values for more human-like behavior.
    Returns base_time with ±TIMING_FUZZINESS% variation.
    """
    import random
    variation = base_time * TIMING_FUZZINESS
    return max(0.0, base_time + random.uniform(-variation, variation))

