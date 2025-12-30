#!/usr/bin/env python3
"""
MapleStory Idle - Party Quest Auto Bot

Usage:
    python main.py              Run the bot
    python main.py --calibrate  Capture screenshots for template setup
    
Press Ctrl+C to stop the bot gracefully.
"""

import time
import random
import signal
import sys
import os
from datetime import datetime
from enum import Enum, auto
from pathlib import Path

from adb_controller import ADBController
from image_detector import ImageDetector
from config import (
    POLL_INTERVAL, CLICK_DELAY,
    MATCHMAKING_TIMEOUT, DUNGEON_TIMEOUT,
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
    def __init__(self):
        self._print_banner()
        
        self.adb = ADBController()
        self.detector = ImageDetector()
        # Get buttons from ADBController (auto-scaled to current screen size)
        self.BUTTONS = self.adb.BUTTONS
        
        self.state = BotState.IDLE
        self.clear_count = 0
        self.session_start = datetime.now()
        self.running = True
        
        # Timestamps for timeout tracking
        self.queue_start = 0
        self.dungeon_start = 0
        self.last_clear_time = time.time()  # Track last successful clear
        self.unknown_state_start_time = 0  # Track time spent in UNKNOWN state
        
        # Flag to prevent double-counting clears
        self.last_clear_counted = False
        
        # Inactivity timeout (around 30 minutes with no clears = stop bot)
        self.inactivity_timeout = fuzzy_time(30 * 60)  # 30 minutes in seconds
        
        # Maximum runtime (around 8 hours = stop bot)
        self.max_runtime = fuzzy_time(8 * 60 * 60)  # 8 hours in seconds
        
        # Handle Ctrl+C gracefully
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _print_banner(self):
        print()
        print("╔" + "═" * 48 + "╗")
        print("║   MapleStory Idle - Party Quest Auto Bot      ║")
        print("╠" + "═" * 48 + "╣")
        print("║   Press Ctrl+C to stop                        ║")
        print("╚" + "═" * 48 + "╝")
        print()
    
    def _signal_handler(self, sig, frame):
        print("\n\n⚠ Stopping bot gracefully...")
        self.running = False
        self.state = BotState.STOPPED
    
    def tap_all_buttons(self):
        """Tap all three button locations in quick succession."""
        self.adb.tap(*self.BUTTONS["accept"])
        self.adb.tap(*self.BUTTONS["leave"])
        self.adb.tap(*self.BUTTONS["auto_match"])
    
    def _print_status(self):
        elapsed = datetime.now() - self.session_start
        elapsed_str = str(elapsed).split('.')[0]
        
        # Create a nice status line
        status_icon = {
            BotState.IDLE: "⏸",
            BotState.QUEUING: "🔍",
            BotState.MATCH_FOUND: "✓",
            BotState.IN_DUNGEON: "⚔",
            BotState.CLEAR: "🎉",
            BotState.STOPPED: "⏹",
        }.get(self.state, "?")
        
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] "
              f"{status_icon} {self.state.name:12} | "
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
        
        while self.running:
            try:
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
                
                # Check for max runtime (8 hours)
                elapsed = (datetime.now() - self.session_start).total_seconds()
                if elapsed > self.max_runtime and detected_state == "IN_DUNGEON":
                    print(f"\n⏰ Maximum runtime of {self.max_runtime // 3600} hours reached!")
                    fuzzy_sleep = fuzzy_time(14400)
                    print(f"  Stopping bot... for {fuzzy_sleep // 3600} hours")
                    time.sleep(fuzzy_sleep)
                    print("  Resuming bot...")
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
        
        self._print_final_stats()
    
    def _react_to_state(self, detected_state: str, screenshot):
        """React to detected state - click the appropriate next action."""
        
        # Reset unknown state timer if we are in a known state
        if detected_state != "UNKNOWN":
            self.unknown_state_start_time = 0

        if detected_state == "READY":
            # We see Auto Match button - click it to queue
            # But first check if we came from a dungeon (spam-click worked, skipped CLEAR)
            if self.state == BotState.IN_DUNGEON and not self.last_clear_counted:
                dungeon_time = time.time() - self.dungeon_start
                if dungeon_time > 30:  # Only count if we were in dungeon for a reasonable time
                    print("  ★ Clear detected via state transition (spam-click worked)")
                    self._complete_dungeon()
            
            print("  → Clicking Auto Match...")
            self.adb.tap(*self.BUTTONS["auto_match"])
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
            # Matchmaking in progress - just wait, don't pre-click
            self.state = BotState.QUEUING
            
        elif detected_state == "IN_DUNGEON":
            # In dungeon - just wait, don't pre-click Leave
            if random.randint(0, 100) <= 8:
                print("  → Clicking Jump...")
                self.adb.tap(*self.BUTTONS["jump"])
                if random.randint(0, 100) <= 30:
                    time.sleep(fuzzy_time(0.1))
                    print("  → Clicking Double Jump...")
                    self.adb.tap(*self.BUTTONS["jump"])
            self.state = BotState.IN_DUNGEON
            
        elif detected_state == "UNKNOWN":
            # Check for unknown state timeout
            if self.unknown_state_start_time == 0:
                print("  ? Unknown state detected, starting 10-minute timeout...")
                self.unknown_state_start_time = time.time()
            else:
                time_in_unknown = time.time() - self.unknown_state_start_time
                if time_in_unknown > (10 * 60):  # 10 minutes
                    print("\n⚠ Stuck in UNKNOWN state for over 10 minutes!")
                    print("  Stopping bot as a safety measure.")
                    self.running = False
                    return

            # Can't identify screen - try to detect likely states based on context
            if self.state == BotState.QUEUING:
                # While queuing: could be READY (queue cancelled) or MATCH_FOUND (transitioning)
                # Check for READY state first (most likely if queue cancelled)
                found_auto, _, _, _ = self.detector.find_template(screenshot, "auto_match_btn")
                if found_auto:
                    print("  → Unknown state (queuing) - detected READY, clicking Auto Match...")
                    self.adb.tap(*self.BUTTONS["auto_match"])
                    self.state = BotState.QUEUING
                    self.queue_start = time.time()
                else:
                    # Check for Accept button (match found but template missed)
                    found_accept, _, _, _ = self.detector.find_template(screenshot, "accept_btn")
                    if found_accept:
                        print("  → Unknown state (queuing) - detected MATCH_FOUND, clicking Accept...")
                        self.adb.tap(*self.BUTTONS["accept"])
                        self.state = BotState.IN_DUNGEON
                        self.dungeon_start = time.time()
            elif self.state == BotState.IN_DUNGEON:
                # While in dungeon: could be CLEAR (dungeon finished) or READY (returned to lobby)
                # Check for CLEAR first (most likely if dungeon finished)
                found_clear, _, _, _ = self.detector.find_template(screenshot, "clear_screen")
                if found_clear:
                    print("  → Unknown state (in dungeon) - detected CLEAR, clicking Leave...")
                    if not self.last_clear_counted:
                        self._complete_dungeon()
                    self.adb.tap(*self.BUTTONS["leave"])
                else:
                    # Check for READY (returned to lobby, maybe dungeon ended quickly)
                    found_auto, _, _, _ = self.detector.find_template(screenshot, "auto_match_btn")
                    if found_auto:
                        dungeon_time = time.time() - self.dungeon_start
                        if dungeon_time > 30:  # Only count if we were in dungeon for a while
                            print("  → Unknown state (in dungeon) - detected READY, counting clear...")
                            self._complete_dungeon()
                        else:
                            print("  → Unknown state (in dungeon) - detected READY (too early), resetting...")
                            self.state = BotState.IDLE
            else:
                # IDLE or other state - most likely we're at READY but template missed it
                found_auto, _, _, _ = self.detector.find_template(screenshot, "auto_match_btn")
                if found_auto:
                    print("  → Unknown state - detected READY, clicking Auto Match...")
                    self.adb.tap(*self.BUTTONS["auto_match"])
                    self.state = BotState.QUEUING
                    self.queue_start = time.time()
                else:
                    # Last resort: try clicking Auto Match anyway (if we're stuck)
                    self.adb.tap(*self.BUTTONS["auto_match"])
    
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
        # Otherwise, just wait - don't pre-click Accept until MATCH_FOUND is detected
    
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
        elapsed = datetime.now() - self.session_start
        elapsed_str = str(elapsed).split('.')[0]
        
        print("\n")
        print("╔" + "═" * 48 + "╗")
        print("║              Session Complete!                 ║")
        print("╠" + "═" * 48 + "╣")
        print(f"║  Total Clears:    {self.clear_count:<28}║")
        print(f"║  Session Time:    {elapsed_str:<28}║")
        if self.clear_count > 0:
            avg_time = elapsed.total_seconds() / self.clear_count
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


def main():
    # Change to script directory so relative paths work
    script_dir = Path(__file__).parent.absolute()
    os.chdir(script_dir)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--calibrate":
        calibration_mode()
    else:
        bot = PartyQuestBot()
        bot.run()


if __name__ == "__main__":
    main()

