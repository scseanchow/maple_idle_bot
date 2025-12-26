# MapleStory Idle - Party Quest Auto Bot

An automation bot for the Party Quest feature in MapleStory Idle, running on MuMu Player (Android emulator) on macOS.

## Features

- ✅ **Automatic queue** - Clicks "Auto Match" to join party queue
- ✅ **Auto accept** - Detects and accepts matchmaking popup
- ✅ **Auto clear** - Clicks "Leave" after dungeon completion
- ✅ **Clear counter** - Tracks number of successful dungeon clears
- ✅ **Background operation** - Works via ADB without requiring window focus
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
   git clone https://github.com/YOUR_USERNAME/maple_idle_bot.git
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
3. Crop the buttons and save to `templates/`:
   - `auto_match_btn.png` - The "Auto Match" button
   - `accept_btn.png` - The "Accept" button
   - `leave_btn.png` - The "Leave" button  
   - `clear_screen.png` - The "CLEAR" text banner (optional but recommended)

### 2. Adjust Coordinates (if needed)

If clicks are missing their targets, update button coordinates in `config.py`:

```python
BUTTONS = {
    "auto_match": (3380, 2010),
    "accept": (1920, 1610),
    "leave": (1920, 2040),
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
| `POLL_INTERVAL` | `0.5` | Screen check frequency (seconds) |
| `MATCH_THRESHOLD` | `0.85` | Template matching strictness (0-1) |
| `MATCHMAKING_TIMEOUT` | `120` | Max queue wait time (seconds) |
| `DUNGEON_TIMEOUT` | `360` | Max dungeon time (seconds) |

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│                    State Machine                         │
├─────────────────────────────────────────────────────────┤
│  IDLE → QUEUING → MATCH_FOUND → IN_DUNGEON → CLEAR     │
│    ↑                                            │       │
│    └────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────┘
```

1. **IDLE**: Clicks "Auto Match" to start queue
2. **QUEUING**: Waits for match, clicks "Accept" immediately when found
3. **IN_DUNGEON**: Waits for dungeon to complete
4. **CLEAR**: Clicks "Leave" immediately, increments counter, returns to IDLE

## Troubleshooting

### Bot doesn't detect buttons
- Lower `MATCH_THRESHOLD` in config.py (try 0.75)
- Recapture templates from calibration screenshots

### Clicks are missing targets
- Run calibration mode and note exact button coordinates
- Update `BUTTONS` in config.py

### ADB connection issues
- Ensure MuMu Player is running
- Check `adb devices` shows your emulator
- Try `adb kill-server && adb start-server`

## License

MIT License - Use at your own risk. This is for educational purposes.

## Disclaimer

This bot is for personal use and educational purposes only. Use of automation tools may violate the game's Terms of Service. Use responsibly.

