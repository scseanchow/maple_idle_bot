#!/usr/bin/env python3
"""
MapleStory Idle - Party Quest Auto Bot

Usage:
    python main.py              Run the bot
    python main.py --calibrate  Capture screenshots for template setup
    
Press Ctrl+C to stop the bot gracefully.
"""

import time
import signal
import sys
import os
from datetime import datetime
from enum import Enum, auto
from pathlib import Path

from adb_controller import ADBController
from image_detector import ImageDetector
from config import (
    POLL_INTERVAL, CLICK_DELAY, BUTTONS,
    MATCHMAKING_TIMEOUT, DUNGEON_TIMEOUT
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
        
        self.state = BotState.IDLE
        self.clear_count = 0
        self.session_start = datetime.now()
        self.running = True
        
        # Timestamps for timeout tracking
        self.queue_start = 0
        self.dungeon_start = 0
        
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
        """Main bot loop."""
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
                
                # Use fallback detection if no templates
                if self.detector.templates:
                    detected_state = self.detector.detect_state(screenshot, verbose=True)
                else:
                    detected_state = self.detector.detect_state_with_fallback(screenshot)
                
                print(f"  Detected: {detected_state}")
                
                # State machine logic
                if self.state == BotState.IDLE:
                    self._handle_idle(detected_state, screenshot)
                
                elif self.state == BotState.QUEUING:
                    self._handle_queuing(detected_state, screenshot)
                
                elif self.state == BotState.MATCH_FOUND:
                    self._handle_match_found(detected_state, screenshot)
                
                elif self.state == BotState.IN_DUNGEON:
                    self._handle_in_dungeon(detected_state, screenshot)
                
                elif self.state == BotState.CLEAR:
                    self._handle_clear(detected_state, screenshot)
                
                time.sleep(POLL_INTERVAL)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(POLL_INTERVAL * 2)
        
        self._print_final_stats()
    
    def _handle_idle(self, detected_state: str, screenshot):
        """Handle IDLE state - click Auto Match to start queue."""
        if detected_state == "READY":
            print("  → Clicking Auto Match...")
            self.adb.tap(*BUTTONS["auto_match"])
            time.sleep(CLICK_DELAY)
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
            self.adb.tap(*BUTTONS["auto_match"])
            time.sleep(CLICK_DELAY)
    
    def _handle_queuing(self, detected_state: str, screenshot):
        """Handle QUEUING state - wait for match."""
        if detected_state == "MATCH_FOUND":
            print("  ✓ Match found! Clicking Accept immediately...")
            # Click Accept RIGHT AWAY - don't wait for next iteration
            found, x, y, _ = self.detector.find_template(screenshot, "accept_btn")
            if found:
                self.adb.tap(x, y)
            else:
                self.adb.tap(*BUTTONS["accept"])
            time.sleep(CLICK_DELAY)
            self.state = BotState.IN_DUNGEON
            self.dungeon_start = time.time()
        elif detected_state == "READY":
            # Queue might have been cancelled, restart
            print("  → Queue reset, clicking Auto Match again...")
            self.adb.tap(*BUTTONS["auto_match"])
            time.sleep(CLICK_DELAY)
            self.queue_start = time.time()
        elif time.time() - self.queue_start > MATCHMAKING_TIMEOUT:
            print("  ⚠ Queue timeout, restarting...")
            self.state = BotState.IDLE
    
    def _handle_match_found(self, detected_state: str, screenshot):
        """Handle MATCH_FOUND state - click Accept."""
        # Try to find accept button position dynamically
        found, x, y, _ = self.detector.find_template(screenshot, "accept_btn")
        if found:
            print(f"  → Clicking Accept at ({x}, {y})...")
            self.adb.tap(x, y)
        else:
            print("  → Clicking Accept (fixed position)...")
            self.adb.tap(*BUTTONS["accept"])
        
        time.sleep(CLICK_DELAY)
        self.state = BotState.IN_DUNGEON
        self.dungeon_start = time.time()
    
    def _handle_in_dungeon(self, detected_state: str, screenshot):
        """Handle IN_DUNGEON state - wait for clear."""
        if detected_state == "CLEAR":
            print("  ✓ Dungeon cleared! Clicking Leave immediately...")
            # Click Leave RIGHT AWAY - don't wait for next iteration
            found, x, y, _ = self.detector.find_template(screenshot, "leave_btn")
            if found:
                self.adb.tap(x, y)
            else:
                self.adb.tap(*BUTTONS["leave"])
            time.sleep(CLICK_DELAY * 2)  # Slightly longer for screen transition
            self.clear_count += 1
            print(f"  ★ Total clears: {self.clear_count}")
            self.state = BotState.IDLE
        elif detected_state == "READY":
            # Somehow back at ready screen (maybe disconnected?)
            print("  ⚠ Back at ready screen unexpectedly")
            self.state = BotState.IDLE
        elif time.time() - self.dungeon_start > DUNGEON_TIMEOUT:
            print("  ⚠ Dungeon timeout, checking state...")
            self.state = BotState.IDLE
    
    def _handle_clear(self, detected_state: str, screenshot):
        """Handle CLEAR state - confirm and restart."""
        # Try to find leave button position dynamically
        found, x, y, _ = self.detector.find_template(screenshot, "leave_btn")
        if found:
            print(f"  → Clicking Leave at ({x}, {y})...")
            self.adb.tap(x, y)
        else:
            print("  → Clicking Leave (fixed position)...")
            self.adb.tap(*BUTTONS["leave"])
        
        time.sleep(CLICK_DELAY * 2)  # Longer delay for screen transition
        
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

