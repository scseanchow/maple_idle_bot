# MapleStory Idle - Party Quest Auto Bot

An automation bot for the Party Quest feature in MapleStory Idle, running on MuMu Player (Android emulator) on macOS.

## Features

- ✅ **Automatic queue** - Clicks "Auto Match" to join party queue
- ✅ **Auto accept** - Detects and accepts matchmaking popup instantly
- ✅ **Auto clear** - Clicks "Leave" after dungeon completion
- ✅ **Clear counter** - Tracks number of successful dungeon clears
- ✅ **Error dialog handling** - Auto-dismisses "Failed to connect" and other notice dialogs
- ✅ **Spam-click optimization** - Pre-clicks Accept/Leave areas to catch popups faster
- ✅ **Background operation** - Works via ADB without requiring window focus
- ✅ **Safety limits** - 30-min inactivity timeout + 8-hour max runtime
- ✅ **Graceful shutdown** - Press Ctrl+C to stop with session statistics

## Requirements

- macOS
- Python 3.10+
- MuMu Player (or compatible Android emulator with ADB support)
- ADB (Android Debug Bridge)

## Installation

1. **Install ADB**:
   ```bash
   brew install android-platform-tools
   ```

2. **Clone the repository**:
   ```bash
   git clone https://github.com/scseanchow/maple_idle_bot.git
   cd maple_idle_bot/pq_auto
   ```

3. **Create virtual environment and install dependencies**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Verify ADB connection**:
   ```bash
   adb devices
   # Should show: emulator-5554  device
   ```

## Setup

### 1. Calibrate Templates

The bot uses image template matching to detect UI elements. You need to capture templates from your game:

```bash
python main.py --calibrate
```

1. Navigate to the Party Quest screen in game
2. Take a screenshot (option 1)
3. Crop the UI elements and save to `templates/`:
   - `auto_match_btn.png` - The "Auto Match" button
   - `accept_btn.png` - The "Accept" button in matchmaking popup
   - `leave_btn.png` - The "Leave" button on clear screen
   - `clear_screen.png` - The "CLEAR" text banner
   - `matchmaking.png` - Matchmaking indicator (when queuing)
   - `minimap.png` - The "MINI MAP" text (visible during dungeon)
   - `notice_banner.png` - The "Notice" header on error dialogs
   - `ok_btn.png` - The "OK" button on error dialogs

### 2. Adjust Coordinates (if needed)

If clicks are missing their targets, update button coordinates in `config.py`:

```python
BUTTONS = {
    "auto_match": (3380, 2010),
    "accept": (1920, 1610),
    "leave": (1920, 2020),
    "ok": (1920, 1415),
}
```

## Usage

1. **Start MuMu Player** and launch MapleStory Idle

2. **Navigate to Party Quest** screen (where "Auto Match" button is visible)

3. **Run the bot**:
   ```bash
   cd pq_auto
   source venv/bin/activate
   python main.py
   ```

4. **Stop the bot**: Press `Ctrl+C` for graceful shutdown with statistics

## Configuration

Edit `config.py` to customize:

| Setting | Default | Description |
|---------|---------|-------------|
| `ADB_DEVICE` | `emulator-5554` | ADB device identifier |
| `POLL_INTERVAL` | `0.3` | Screen check frequency (seconds) |
| `CLICK_DELAY` | `0.15` | Delay after clicking (seconds) |
| `MATCH_THRESHOLD` | `0.85` | Template matching strictness (0-1) |
| `MATCHMAKING_TIMEOUT` | `120` | Max queue wait time (seconds) |
| `DUNGEON_TIMEOUT` | `360` | Max dungeon time (seconds) |

The bot also has built-in safety limits:
- **Inactivity timeout**: Stops after 30 minutes with no successful clears
- **Max runtime**: Stops after 8 hours of continuous operation

## How It Works

The bot uses a **reactive state machine** - it responds to what it sees on screen rather than following a rigid sequence:

```
┌─────────────────────────────────────────────────────────┐
│              Reactive State Detection                    │
├─────────────────────────────────────────────────────────┤
│  See Auto Match btn  → Click it → QUEUING               │
│  See Accept btn      → Click it → IN_DUNGEON            │
│  See CLEAR screen    → Click Leave → Count clear        │
│  See Notice dialog   → Click OK → Reset to queue        │
│  See Minimap         → In dungeon, pre-click Leave      │
└─────────────────────────────────────────────────────────┘
```

**Spam-click optimization**: While queuing, the bot pre-clicks the Accept area. While in dungeon (after 30s), it pre-clicks the Leave area. This catches popups instantly.

## Utilities

### Spam Tap (for debugging)

Continuously taps all button locations:

```bash
python spam_tap.py [interval]
# e.g., python spam_tap.py 0.1  (taps every 0.1 seconds)
```

## Troubleshooting

### Bot doesn't detect buttons
- Lower `MATCH_THRESHOLD` in config.py (try 0.75)
- Recapture templates from calibration screenshots
- Run calibration mode option 4 to test template matching

### Clicks are missing targets
- Run calibration mode and note exact button coordinates
- Update `BUTTONS` in config.py
- Use `spam_tap.py` to test if clicks register

### ADB connection issues
- Ensure MuMu Player is running
- Check `adb devices` shows your emulator
- Try `adb kill-server && adb start-server`

### Bot misses clicks when window not focused
- Disable "Dynamic Frame Rate" in MuMu settings
- Disable App Nap for MuMu: `defaults write com.mumuglobal.MuMuPlayer NSAppSleepDisabled -bool YES`
- Lower MuMu's CPU/memory allocation if system is under load

## License

MIT License - Use at your own risk. This is for educational purposes.

## Disclaimer

This bot is for personal use and educational purposes only. Use of automation tools may violate the game's Terms of Service. Use responsibly.

