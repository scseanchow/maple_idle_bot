"""
Configuration for MapleStory Idle Party Quest Bot
"""

# ADB Configuration
# Use the device name from 'adb devices' output
ADB_DEVICE = "emulator-5554"

# Timing Configuration (in seconds)
POLL_INTERVAL = 0.5          # How often to check screen state (faster for Accept popup)
MATCHMAKING_TIMEOUT = 120    # Max time to wait for match (2 min)
DUNGEON_TIMEOUT = 360        # Max time for dungeon completion (6 min)
CLICK_DELAY = 0.2            # Delay after clicking

# Screen Resolution (actual MuMu emulator resolution - landscape mode)
SCREEN_WIDTH = 3840
SCREEN_HEIGHT = 2160

# Button coordinates (calibrate these using --calibrate mode)
# For 3840x2160 landscape resolution
BUTTONS = {
    "auto_match": (3380, 2010),  # Auto Match button (bottom right, cyan) 
    "accept": (1920, 1610),      # Accept button in matchmaking popup (centered)
    "leave": (1920, 2040),       # Leave button on clear screen (centered, near bottom)
}

# Template matching threshold (0-1, higher = stricter matching)
# Lower this if detection is missing buttons, raise if getting false positives
MATCH_THRESHOLD = 0.85

