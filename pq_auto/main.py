#!/usr/bin/env python3
"""
MapleStory Idle - Party Quest Auto Bot

Usage:
    python main.py                  Run the bot (solo queue - Auto Match)
    python main.py --group          Run the bot (group/premade - Enter button)
    python main.py --device <id>    Run on a specific device
    python main.py --list-devices   List all connected devices
    python main.py --calibrate      Capture screenshots for template setup
    
Press Ctrl+C to stop the bot gracefully.
Press P to pause/unpause the bot.
"""

import time
import signal
import sys
import os
import select
import termios
import tty
import threading
from datetime import datetime
from enum import Enum, auto
from pathlib import Path

from adb_controller import ADBController
from image_detector import ImageDetector
from config import (
    POLL_INTERVAL, CLICK_DELAY,
    MATCHMAKING_TIMEOUT, DUNGEON_TIMEOUT, QUEUE_TIMEOUT,
    fuzzy_time
)


class BotState(Enum):
    IDLE = auto()
    QUEUING = auto()
    MATCH_FOUND = auto()
    IN_DUNGEON = auto()
    CLEAR = auto()
    STOPPED = auto()


class PartyQuestBot:
    def __init__(self, group_mode: bool = False, device_id: str = None):
        self.group_mode = group_mode
        self.device_id = device_id
        self._print_banner()
        
        self.adb = ADBController(device_id=device_id)
        self.detector = ImageDetector()
        # Get buttons from ADBController (auto-scaled to current screen size)
        self.BUTTONS = self.adb.BUTTONS
        
        # Set the queue button based on mode
        self.queue_button = "enter" if group_mode else "auto_match"
        
        self.state = BotState.IDLE
        self.clear_count = 0
        self.session_start = datetime.now()
        self.running = True
        self.paused = False
        
        # Pause time tracking
        self.total_paused_seconds = 0.0
        self.pause_start_time = None
        
        # Timestamps for timeout tracking
        self.queue_start = 0
        self.dungeon_start = 0
        self.last_clear_time = time.time()  # Track last successful clear
        
        # Flag to prevent double-counting clears
        self.last_clear_counted = False
        
        # Inactivity timeout (30 minutes with no clears = stop bot)
        self.inactivity_timeout = 30 * 60  # 30 minutes in seconds
        
        # Maximum runtime (8 hours = stop bot)
        self.max_runtime = 8 * 60 * 60  # 8 hours in seconds
        
        # Terminal settings for non-blocking input
        self.old_settings = None
        
        # Handle Ctrl+C gracefully
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _print_banner(self):
        mode_str = "GROUP MODE" if self.group_mode else "SOLO MODE"
        device_str = self.device_id[:20] if self.device_id else "auto-detect"
        print()
        print("╔" + "═" * 48 + "╗")
        print("║   MapleStory Idle - Party Quest Auto Bot      ║")
        print("╠" + "═" * 48 + "╣")
        print(f"║   Mode:   {mode_str:36} ║")
        print(f"║   Device: {device_str:36} ║")
        print("║   Press P to pause/unpause                    ║")
        print("║   Press Ctrl+C to stop                        ║")
        print("╚" + "═" * 48 + "╝")
        print()
    
    def _signal_handler(self, sig, frame):
        print("\n\n⚠ Stopping bot gracefully...")
        self._restore_terminal()
        self.running = False
        self.state = BotState.STOPPED
    
    def _setup_terminal(self):
        """Set terminal to raw mode and start keyboard listener thread."""
        try:
            self.old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
        except Exception:
            self.old_settings = None
        
        # Start keyboard listener thread
        self._keyboard_thread = threading.Thread(target=self._keyboard_listener, daemon=True)
        self._keyboard_thread.start()
    
    def _restore_terminal(self):
        """Restore terminal to original settings."""
        if self.old_settings:
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
            except Exception:
                pass
    
    def _keyboard_listener(self):
        """Background thread that listens for keyboard input."""
        while self.running:
            try:
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    key = sys.stdin.read(1).lower()
                    if key == 'p':
                        self.paused = not self.paused
                        if self.paused:
                            self.pause_start_time = time.time()
                            print("\n\n⏸ PAUSED - Press P to resume...")
                        else:
                            # Add paused duration to total
                            if self.pause_start_time:
                                pause_duration = time.time() - self.pause_start_time
                                self.total_paused_seconds += pause_duration
                                # Adjust last_clear_time so inactivity timeout doesn't trigger
                                self.last_clear_time += pause_duration
                                self.pause_start_time = None
                            print("\n\n▶ RESUMED\n")
            except Exception:
                pass
    
    def tap_all_buttons(self):
        """Tap all three button locations in quick succession."""
        self.adb.tap(*self.BUTTONS["accept"])
        self.adb.tap(*self.BUTTONS["leave"])
        self.adb.tap(*self.BUTTONS[self.queue_button])
    
    def _get_active_elapsed_seconds(self) -> float:
        """Get elapsed time excluding paused time."""
        total_elapsed = (datetime.now() - self.session_start).total_seconds()
        paused = self.total_paused_seconds
        # If currently paused, add current pause duration
        if self.paused and self.pause_start_time:
            paused += time.time() - self.pause_start_time
        return total_elapsed - paused
    
    def _print_status(self):
        # Use active time (excluding paused time)
        active_seconds = self._get_active_elapsed_seconds()
        hours, remainder = divmod(int(active_seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        elapsed_str = f"{hours}:{minutes:02d}:{seconds:02d}"
        
        # Create a nice status line
        if self.paused:
            status_icon = "⏸"
            state_name = "PAUSED"
        else:
            status_icon = {
                BotState.IDLE: "▶",
                BotState.QUEUING: "🔍",
                BotState.MATCH_FOUND: "✓",
                BotState.IN_DUNGEON: "⚔",
                BotState.CLEAR: "🎉",
                BotState.STOPPED: "⏹",
            }.get(self.state, "?")
            state_name = self.state.name
        
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] "
              f"{status_icon} {state_name:12} | "
              f"Clears: {self.clear_count} | "
              f"Session: {elapsed_str}")
    
    def run(self):
        """Main bot loop - fully reactive to what we see."""
        print("🎮 Bot started!\n")
        
        # Check if we have templates
        if not self.detector.templates:
            print("⚠ WARNING: No templates found in templates/ directory.")
            print("  The bot will use fallback detection which may be less accurate.")
            print("  Run 'python main.py --calibrate' to set up templates.\n")
        
        # Set up terminal for non-blocking keyboard input
        self._setup_terminal()
        
        try:
            while self.running:
                try:
                    # If paused, just wait (keyboard thread handles unpause)
                    if self.paused:
                        time.sleep(0.1)
                        continue
                    
                    self._print_status()
                    screenshot = self.adb.screenshot()
                    
                    # Detect what's on screen
                    if self.detector.templates:
                        detected_state = self.detector.detect_state(screenshot, verbose=True)
                    else:
                        detected_state = self.detector.detect_state_with_fallback(screenshot)
                    
                    print(f"  Detected: {detected_state}")
                    
                    # Check for inactivity timeout (no clears in 30 min)
                    time_since_clear = time.time() - self.last_clear_time
                    if time_since_clear > self.inactivity_timeout:
                        print(f"\n⚠ No successful clears in {self.inactivity_timeout // 60} minutes!")
                        print("  Stopping bot due to inactivity...")
                        self.running = False
                        break
                    
                    # Check for max runtime (8 hours of active time, excluding pauses)
                    elapsed = self._get_active_elapsed_seconds()
                    if elapsed > self.max_runtime:
                        print(f"\n⏰ Maximum runtime of {self.max_runtime // 3600} hours reached!")
                        print("  Stopping bot...")
                        self.running = False
                        break
                    
                    # REACTIVE LOGIC - respond to what we SEE, not what we expect
                    self._react_to_state(detected_state, screenshot)
                    
                    time.sleep(fuzzy_time(POLL_INTERVAL))
                    
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"❌ Error: {e}")
                    import traceback
                    traceback.print_exc()
                    time.sleep(fuzzy_time(POLL_INTERVAL * 2))
        finally:
            self._restore_terminal()
        
        self._print_final_stats()
    
    def _react_to_state(self, detected_state: str, screenshot):
        """React to detected state - click the appropriate next action."""
        
        if detected_state == "READY" or detected_state == "READY_GROUP":
            # We see queue button - click it to queue
            # But first check if we came from a dungeon (spam-click worked, skipped CLEAR)
            if self.state == BotState.IN_DUNGEON and not self.last_clear_counted:
                dungeon_time = time.time() - self.dungeon_start
                if dungeon_time > 30:  # Only count if we were in dungeon for a reasonable time
                    print("  ★ Clear detected via state transition (spam-click worked)")
                    self._complete_dungeon()
            
            button_name = "Enter" if self.group_mode else "Auto Match"
            print(f"  → Clicking {button_name}...")
            self.adb.tap(*self.BUTTONS[self.queue_button])
            self.state = BotState.QUEUING
            self.queue_start = time.time()
            self.last_clear_counted = False  # Reset for new run
            
        elif detected_state == "MATCH_FOUND":
            # Accept popup visible - click Accept immediately
            print("  → Clicking Accept...")
            self.adb.tap(*self.BUTTONS["accept"])
            self.state = BotState.IN_DUNGEON
            self.dungeon_start = time.time()
            self.last_clear_counted = False  # Reset for new dungeon
            
        elif detected_state == "CLEAR":
            # Clear screen visible - click Leave and count
            if not self.last_clear_counted:
                self._complete_dungeon()
            print("  → Clicking Leave...")
            self.adb.tap(*self.BUTTONS["leave"])
            
        elif detected_state == "ERROR_DIALOG":
            # Error/notice dialog visible - click OK to dismiss and re-queue
            print("  ⚠ Error dialog detected, clicking OK...")
            self.adb.tap(*self.BUTTONS["ok"])
            time.sleep(fuzzy_time(CLICK_DELAY * 2))  # Wait for dialog to close
            self.state = BotState.IDLE  # Reset to try again
            
        elif detected_state == "QUEUING":
            # Try to read actual matchmaking time from screen
            screen_time = self.detector.read_matchmaking_time(screenshot)
            
            if screen_time > 0:
                # Use screen-detected time
                if screen_time > QUEUE_TIMEOUT:
                    print(f"  ⚠ Queue timeout (screen shows {screen_time}s > {QUEUE_TIMEOUT}s), cancelling...")
                    self.adb.tap(*self.BUTTONS["cancel_queue"])  # Click X on matchmaking popup
                    time.sleep(fuzzy_time(CLICK_DELAY * 3))  # Wait for popup to close
                    self.state = BotState.IDLE  # Reset to re-queue
                else:
                    # Show screen time and pre-click Accept
                    mins, secs = divmod(screen_time, 60)
                    print(f"  → Pre-clicking Accept area... (queue: {mins}:{secs:02d})")
                    self.adb.tap(*self.BUTTONS["accept"])
                    self.state = BotState.QUEUING
            else:
                # Fallback to internal timer if OCR fails
                queue_time = time.time() - self.queue_start
                if queue_time > QUEUE_TIMEOUT:
                    print(f"  ⚠ Queue timeout ({int(queue_time)}s), cancelling...")
                    self.adb.tap(*self.BUTTONS["cancel_queue"])
                    time.sleep(fuzzy_time(CLICK_DELAY * 3))
                    self.state = BotState.IDLE
                else:
                    print(f"  → Pre-clicking Accept area... (queue: {int(queue_time)}s)")
                    self.adb.tap(*self.BUTTONS["accept"])
                    self.state = BotState.QUEUING
            
        elif detected_state == "IN_DUNGEON":
            # In dungeon - just wait, don't pre-click Leave
            self.state = BotState.IN_DUNGEON
            
        elif detected_state == "UNKNOWN":
            # Can't identify screen - but try to read queue time anyway
            # If we can read a matchmaking time, we're probably in queue
            screen_time = self.detector.read_matchmaking_time(screenshot)
            
            if screen_time > 0:
                # We can read a queue time - treat this as QUEUING state
                if screen_time > QUEUE_TIMEOUT:
                    mins, secs = divmod(screen_time, 60)
                    print(f"  ⚠ Queue timeout (screen shows {mins}:{secs:02d} > 3:00), cancelling...")
                    self.adb.tap(*self.BUTTONS["cancel_queue"])
                    time.sleep(fuzzy_time(CLICK_DELAY * 3))
                    self.state = BotState.IDLE
                else:
                    mins, secs = divmod(screen_time, 60)
                    print(f"  → Unknown state but queue detected ({mins}:{secs:02d}), clicking Accept...")
                    self.adb.tap(*self.BUTTONS["accept"])
                    self.state = BotState.QUEUING
            elif self.state == BotState.QUEUING:
                # Probably waiting for match, spam Accept
                print("  → Unknown state (queuing), clicking Accept...")
                self.adb.tap(*self.BUTTONS["accept"])
            elif self.state == BotState.IN_DUNGEON:
                # In dungeon but unknown state - just wait, don't pre-click
                print("  → Unknown state (in dungeon), waiting...")
            else:
                # Not sure, try both
                print("  → Unknown state, clicking Accept + Leave...")
                self.adb.tap(*self.BUTTONS["accept"])
                self.adb.tap(*self.BUTTONS["leave"])
    
    def _handle_idle(self, detected_state: str, screenshot):
        """Handle IDLE state - click Auto Match to start queue."""
        if detected_state == "READY":
            print("  → Clicking Auto Match...")
            self.adb.tap(*self.BUTTONS["auto_match"])
            time.sleep(fuzzy_time(CLICK_DELAY))
            self.state = BotState.QUEUING
            self.queue_start = time.time()
        elif detected_state == "CLEAR":
            # We're on the clear screen, handle it
            self.state = BotState.CLEAR
        elif detected_state == "MATCH_FOUND":
            # Match already found
            self.state = BotState.MATCH_FOUND
        elif detected_state == "UNKNOWN":
            # Try clicking Auto Match anyway if we've been idle
            print("  → State unknown, trying Auto Match...")
            self.adb.tap(*self.BUTTONS["auto_match"])
            time.sleep(fuzzy_time(CLICK_DELAY))
    
    def _handle_queuing(self, detected_state: str, screenshot):
        """Handle QUEUING state - wait for match."""
        if detected_state == "MATCH_FOUND":
            print("  ✓ Match found! Clicking Accept...")
            found, x, y, _ = self.detector.find_template(screenshot, "accept_btn")
            if found:
                self.adb.tap(x, y)
            else:
                self.adb.tap(*self.BUTTONS["accept"])
            time.sleep(fuzzy_time(CLICK_DELAY))
            self.state = BotState.IN_DUNGEON
            self.dungeon_start = time.time()
        elif detected_state == "CLEAR":
            # We somehow got to clear screen (spam-click worked through dungeon)
            print("  ✓ Clear screen detected! Clicking Leave...")
            self.adb.tap(*self.BUTTONS["leave"])
            time.sleep(fuzzy_time(CLICK_DELAY * 2))
            self._complete_dungeon()
        elif detected_state == "READY":
            # Queue might have been cancelled, restart
            print("  → Queue reset, clicking Auto Match again...")
            self.adb.tap(*self.BUTTONS["auto_match"])
            time.sleep(fuzzy_time(CLICK_DELAY))
            self.queue_start = time.time()
        elif time.time() - self.queue_start > fuzzy_time(MATCHMAKING_TIMEOUT):
            print("  ⚠ Queue timeout, restarting...")
            self.state = BotState.IDLE
        else:
            # Spam-click Accept area while waiting - catches popup instantly
            print("  → Pre-clicking Accept area...")
            self.adb.tap(*self.BUTTONS["accept"])
    
    def _handle_match_found(self, detected_state: str, screenshot):
        """Handle MATCH_FOUND state - click Accept."""
        # Try to find accept button position dynamically
        found, x, y, _ = self.detector.find_template(screenshot, "accept_btn")
        if found:
            print(f"  → Clicking Accept at ({x}, {y})...")
            self.adb.tap(x, y)
        else:
            print("  → Clicking Accept (fixed position)...")
            self.adb.tap(*self.BUTTONS["accept"])
        
        time.sleep(fuzzy_time(CLICK_DELAY))
        self.state = BotState.IN_DUNGEON
        self.dungeon_start = time.time()
    
    def _handle_in_dungeon(self, detected_state: str, screenshot):
        """Handle IN_DUNGEON state - wait for clear."""
        dungeon_time = time.time() - self.dungeon_start
        
        if detected_state == "CLEAR":
            print("  ✓ Dungeon cleared! Clicking Leave...")
            self.adb.tap(*self.BUTTONS["leave"])
            time.sleep(fuzzy_time(CLICK_DELAY * 2))
            self._complete_dungeon()
        elif detected_state == "READY":
            # Back at ready screen - dungeon was cleared (spam-click worked)
            if dungeon_time > 30:  # Only count if we were in dungeon for a while
                self._complete_dungeon()
            else:
                print("  ⚠ Back at ready screen early")
                self.state = BotState.IDLE
        elif dungeon_time > fuzzy_time(DUNGEON_TIMEOUT):
            print("  ⚠ Dungeon timeout, checking state...")
            self.state = BotState.IDLE
        # Otherwise, just wait - don't pre-click Leave until CLEAR is detected
    
    def _complete_dungeon(self):
        """Mark dungeon as complete and increment counter."""
        self.clear_count += 1
        self.last_clear_time = time.time()  # Reset inactivity timer
        self.last_clear_counted = True  # Prevent double-counting this dungeon
        print(f"  ★ Dungeon complete! Total clears: {self.clear_count}")
        self.state = BotState.IDLE
    
    def _handle_clear(self, detected_state: str, screenshot):
        """Handle CLEAR state - confirm and restart."""
        print("  → Clicking Leave...")
        self.adb.tap(*self.BUTTONS["leave"])
        
        time.sleep(fuzzy_time(CLICK_DELAY * 2))  # Longer delay for screen transition
        
        self.clear_count += 1
        print(f"  ★ Total clears: {self.clear_count}")
        
        self.state = BotState.IDLE
    
    def _print_final_stats(self):
        """Print session statistics."""
        # Calculate active time (excluding pauses)
        active_seconds = self._get_active_elapsed_seconds()
        hours, remainder = divmod(int(active_seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        active_str = f"{hours}:{minutes:02d}:{seconds:02d}"
        
        # Calculate total time
        total_elapsed = datetime.now() - self.session_start
        total_str = str(total_elapsed).split('.')[0]
        
        print("\n")
        print("╔" + "═" * 48 + "╗")
        print("║              Session Complete!                 ║")
        print("╠" + "═" * 48 + "╣")
        print(f"║  Total Clears:    {self.clear_count:<28}║")
        print(f"║  Active Time:     {active_str:<28}║")
        if self.total_paused_seconds > 0:
            print(f"║  Total Time:      {total_str:<28}║")
        if self.clear_count > 0:
            avg_time = active_seconds / self.clear_count
            avg_str = f"{avg_time:.1f} seconds"
            print(f"║  Avg Time/Clear:  {avg_str:<28}║")
        print("╚" + "═" * 48 + "╝")
        print()


def calibration_mode():
    """Helper mode to capture button positions and templates."""
    print()
    print("╔" + "═" * 48 + "╗")
    print("║            Calibration Mode                    ║")
    print("╚" + "═" * 48 + "╝")
    print()
    print("This will help you capture screenshots and set up templates.")
    print()
    
    adb = ADBController()
    templates_dir = Path("templates")
    templates_dir.mkdir(exist_ok=True)
    
    while True:
        print("\n" + "-" * 40)
        print("Options:")
        print("  1. Take screenshot")
        print("  2. Get screen resolution")
        print("  3. Test tap at coordinates")
        print("  4. Exit calibration")
        print("-" * 40)
        
        try:
            choice = input("\nChoice: ").strip()
        except EOFError:
            break
        
        if choice == "1":
            screenshot = adb.screenshot()
            timestamp = datetime.now().strftime('%H%M%S')
            filename = f"calibration_{timestamp}.png"
            screenshot.save(filename)
            print(f"\n  ✓ Saved: {filename}")
            print(f"  Resolution: {screenshot.size}")
            print("\n  Next steps:")
            print("  1. Open this image in an image editor")
            print("  2. Crop out the buttons you need:")
            print("     - auto_match_btn.png  (the 'Auto Match' button)")
            print("     - accept_btn.png      (the 'Accept' button)")
            print("     - leave_btn.png       (the 'Leave' button)")
            print("     - clear_screen.png    (the 'CLEAR' text/banner)")
            print("     - matchmaking.png     (matchmaking indicator)")
            print(f"  3. Save cropped images to: {templates_dir.absolute()}")
            
        elif choice == "2":
            # Get resolution from actual screenshot (more accurate than wm size)
            screenshot = adb.screenshot()
            width, height = screenshot.size
            print(f"\n  Screenshot resolution: {width}x{height}")
            print(f"  (This is the actual game resolution in landscape mode)")
            
        elif choice == "3":
            try:
                coords = input("  Enter coordinates (x,y): ").strip()
                x, y = map(int, coords.replace(" ", "").split(","))
                print(f"  Tapping at ({x}, {y})...")
                adb.tap(x, y)
            except ValueError:
                print("  Invalid format. Use: x,y (e.g., 640,360)")
                
        elif choice == "4":
            print("\nExiting calibration mode.")
            break
        else:
            print("  Invalid choice")


def select_device_menu() -> str:
    """Interactive menu to select a device from available options."""
    print("  Scanning for devices...")
    devices = ADBController.list_devices()
    
    if not devices:
        print("✗ No ADB devices found.")
        print("  Make sure your emulator is running and ADB is connected.")
        print("  Try: adb devices")
        return None
    
    if len(devices) == 1:
        desc = f" ({devices[0][2]})" if devices[0][2] else ""
        print(f"✓ Found 1 device: {devices[0][0]}{desc}")
        return devices[0][0]
    
    # Multiple devices - show selection menu
    print()
    print("╔" + "═" * 52 + "╗")
    print("║              Select Device                         ║")
    print("╠" + "═" * 52 + "╣")
    
    for i, (device_id, status, desc) in enumerate(devices, 1):
        if desc:
            # Show name prominently, device ID smaller
            line = f"{i}. {desc} [{device_id}]"
        else:
            line = f"{i}. {device_id}"
        print(f"║  {line:48} ║")
    
    print("╚" + "═" * 52 + "╝")
    print()
    
    while True:
        try:
            choice = input(f"Select device (1-{len(devices)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(devices):
                return devices[idx][0]
            print(f"  Please enter a number between 1 and {len(devices)}")
        except ValueError:
            print("  Please enter a valid number")
        except EOFError:
            return None


def list_devices_cmd():
    """List all connected devices and exit."""
    print("Scanning for devices...")
    devices = ADBController.list_devices()
    
    if not devices:
        print("No ADB devices found.")
        print("Make sure your emulator is running and ADB is connected.")
        return
    
    print()
    print(f"Found {len(devices)} device(s):")
    print("-" * 55)
    for device_id, status, desc in devices:
        if desc:
            print(f"  {desc}")
            print(f"    ID: {device_id}")
        else:
            print(f"  {device_id}")
        print()
    print("-" * 55)
    print("Usage: python main.py --device <device_id>")


def main():
    # Change to script directory so relative paths work
    script_dir = Path(__file__).parent.absolute()
    os.chdir(script_dir)
    
    # Handle --list-devices
    if "--list-devices" in sys.argv:
        list_devices_cmd()
        return
    
    # Handle --calibrate
    if "--calibrate" in sys.argv:
        calibration_mode()
        return
    
    # Parse arguments
    group_mode = "--group" in sys.argv
    device_id = None
    
    # Check for --device argument
    if "--device" in sys.argv:
        try:
            idx = sys.argv.index("--device")
            device_id = sys.argv[idx + 1]
        except (IndexError, ValueError):
            print("Error: --device requires a device ID")
            print("Usage: python main.py --device <device_id>")
            print("Run 'python main.py --list-devices' to see available devices")
            return
    else:
        # Check if multiple devices available - show selection menu
        devices = ADBController.list_devices()
        if len(devices) > 1:
            device_id = select_device_menu()
            if not device_id:
                return
    
    # Run the bot
    bot = PartyQuestBot(group_mode=group_mode, device_id=device_id)
    bot.run()


if __name__ == "__main__":
    main()

