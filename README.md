# MapleStory Idle - Party Quest Auto Bot

An automation bot for the Party Quest feature in MapleStory Idle, running on Android emulators (tested with MuMu Player) via ADB.

## Features

- ✅ **Automatic queue** - Clicks "Auto Match" to join party queue
- ✅ **Auto accept** - Detects and accepts matchmaking popup instantly
- ✅ **Auto clear** - Clicks "Leave" after dungeon completion
- ✅ **Clear counter** - Tracks number of successful dungeon clears
- ✅ **Error dialog handling** - Auto-dismisses "Failed to connect" and other notice dialogs
- ✅ **Human-like behavior** - Random click offsets and timing variations
- ✅ **Resolution-independent** - Auto-detects screen size and scales button positions
- ✅ **Auto device detection** - Automatically finds and connects to first available ADB device
- ✅ **Background operation** - Works via ADB without requiring window focus
- ✅ **Safety limits** - 30-min inactivity timeout + 8-hour max runtime
- ✅ **Graceful shutdown** - Press Ctrl+C to stop with session statistics

## Requirements

- Windows/macOS/Linux
- Python 3.10+
- Android emulator (MuMu Player, BlueStacks, etc.) with ADB support
- ADB (Android Debug Bridge)

## Installation

1. **Install ADB**:
   - **macOS**: `brew install android-platform-tools`
   - **Windows**: Download [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools) and add to PATH
   - **Linux**: `sudo apt install android-tools-adb` (Ubuntu/Debian)

2. **Clone the repository**:
   ```bash
   git clone https://github.com/scseanchow/maple_idle_bot.git
   cd maple_idle_bot/pq_auto
   ```

3. **Create virtual environment and install dependencies**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. **Verify ADB connection**:
   ```bash
   adb devices
   # Should show your emulator, e.g.: emulator-5574  device
   ```
   The bot will automatically detect and use the first available device.

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

### 2. Button Coordinates (Automatic)

Button coordinates are now **resolution-independent** and automatically scale to your screen size. The bot uses relative positions (percentages) that work on any resolution.

If you need to adjust button positions, edit `BUTTONS_RELATIVE` in `config.py` (values are 0.0-1.0, where 0.0 = top/left, 1.0 = bottom/right):

```python
BUTTONS_RELATIVE = {
    "auto_match": (0.8802, 0.9306),  # 88% from left, 93% from top
    "accept": (0.5, 0.7454),         # 50% from left, 74.5% from top
    "leave": (0.5, 0.9352),          # 50% from left, 93.5% from top
    "ok": (0.5, 0.6546),             # 50% from left, 65.5% from top
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
| `POLL_INTERVAL` | `0.3` | Screen check frequency (seconds) |
| `CLICK_DELAY` | `0.15` | Delay after clicking (seconds) |
| `MATCH_THRESHOLD` | `0.85` | Template matching strictness (0-1) |
| `MATCHMAKING_TIMEOUT` | `120` | Max queue wait time (seconds) |
| `DUNGEON_TIMEOUT` | `360` | Max dungeon time (seconds) |
| `CLICK_FUZZINESS` | `10` | Random click offset in pixels (±value) |
| `TIMING_FUZZINESS` | `0.15` | Random timing variation (±15% of base value) |

**Auto-detected settings** (no configuration needed):
- `ADB_DEVICE` - Automatically detected from first available device
- `SCREEN_WIDTH` / `SCREEN_HEIGHT` - Automatically detected from screenshot
- `BUTTONS` - Automatically calculated from relative positions and screen size

**Safety limits**:
- **Inactivity timeout**: Stops after 30 minutes with no successful clears
- **Max runtime**: Stops after 8 hours of continuous operation

**Human-like behavior**:
- Random click offsets (`CLICK_FUZZINESS`) make clicks less predictable
- Random timing variations (`TIMING_FUZZINESS`) add natural delays

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
│  See Minimap         → In dungeon, wait for CLEAR       │
└─────────────────────────────────────────────────────────┘
```

**Optimization strategy**:
- While queuing: Pre-clicks Accept area to catch match popup instantly
- While in dungeon: Waits passively, only clicks Leave when CLEAR screen is detected
- All clicks have random offsets for human-like behavior
- All timing has random variations to avoid predictable patterns

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
- Button positions auto-scale to your screen resolution
- If positions need adjustment, edit `BUTTONS_RELATIVE` in config.py (use 0.0-1.0 values)
- Run calibration mode to get screen resolution and test coordinates
- Use `spam_tap.py` to test if clicks register
- Increase `CLICK_FUZZINESS` if clicks are too precise (or decrease if too inaccurate)

### ADB connection issues
- Ensure MuMu Player is running
- Check `adb devices` shows your emulator
- Try `adb kill-server && adb start-server`

### Bot misses clicks when window not focused
- Disable "Dynamic Frame Rate" in MuMu settings
- **macOS**: Disable App Nap: `defaults write com.mumuglobal.MuMuPlayer NSAppSleepDisabled -bool YES`
- Lower MuMu's CPU/memory allocation if system is under load
- Ensure emulator is running at consistent resolution (bot auto-detects size)

### Screen resolution detection fails
- The bot auto-detects screen size from screenshots
- If detection fails, it falls back to `wm size` command
- Ensure ADB connection is stable
- Check that emulator is in landscape mode

## License

MIT License - Use at your own risk. This is for educational purposes.

## Disclaimer

This bot is for personal use and educational purposes only. Use of automation tools may violate the game's Terms of Service. Use responsibly.

