#!/usr/bin/env python3
"""
Spam Tap - Rapidly tap all button locations until Ctrl+C

Usage:
    python spam_tap.py              # Default 0.2s interval
    python spam_tap.py 0.1          # Custom interval (0.1s)
    python spam_tap.py 0.5          # Slower (0.5s)
"""

import sys
import time
import signal
from adb_controller import ADBController

running = True

def signal_handler(sig, frame):
    global running
    print("\n\n⚠ Stopping spam tap...")
    running = False

def main():
    global running
    
    # Parse interval from command line
    interval = 0.2  # Default
    if len(sys.argv) > 1:
        try:
            interval = float(sys.argv[1])
        except ValueError:
            print(f"Invalid interval: {sys.argv[1]}")
            print("Usage: python spam_tap.py [interval_seconds]")
            sys.exit(1)
    
    # Setup
    signal.signal(signal.SIGINT, signal_handler)
    adb = ADBController()
    buttons = adb.BUTTONS  # Get auto-scaled button coordinates
    
    print()
    print("╔════════════════════════════════════════╗")
    print("║         Spam Tap All Buttons           ║")
    print("╠════════════════════════════════════════╣")
    print(f"║  Interval: {interval}s                         ║")
    print("║  Press Ctrl+C to stop                  ║")
    print("╚════════════════════════════════════════╝")
    print()
    print(f"Tapping: Accept {buttons['accept']}")
    print(f"         Leave  {buttons['leave']}")
    print(f"         Auto   {buttons['auto_match']}")
    print()
    
    tap_count = 0
    
    while running:
        # Tap all three buttons
        adb.tap(*buttons["accept"])
        adb.tap(*buttons["leave"])
        adb.tap(*buttons["auto_match"])
        
        tap_count += 1
        print(f"\r  Tap cycles: {tap_count}", end="", flush=True)
        
        time.sleep(interval)
    
    print(f"\n\nTotal tap cycles: {tap_count}")
    print("Done!")

if __name__ == "__main__":
    main()

