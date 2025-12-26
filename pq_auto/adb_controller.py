"""
ADB Controller for interacting with MuMu Player emulator.
Handles screenshots, taps, and other input commands.
"""

import subprocess
import io
from PIL import Image
from config import ADB_DEVICE


class ADBController:
    def __init__(self):
        self.device = ADB_DEVICE
        self._verify_connection()
    
    def _verify_connection(self) -> bool:
        """Verify emulator is connected."""
        result = subprocess.run(
            ["adb", "devices"],
            capture_output=True, text=True
        )
        if self.device in result.stdout:
            print(f"✓ Found device: {self.device}")
            return True
        else:
            print(f"✗ Device not found: {self.device}")
            print(f"  Available devices:\n{result.stdout}")
            return False
    
    def screenshot(self) -> Image.Image:
        """Capture screenshot from emulator."""
        result = subprocess.run(
            ["adb", "-s", self.device, "exec-out", "screencap", "-p"],
            capture_output=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"Screenshot failed: {result.stderr.decode()}")
        return Image.open(io.BytesIO(result.stdout))
    
    def tap(self, x: int, y: int):
        """Send tap event to emulator."""
        subprocess.run(
            ["adb", "-s", self.device, "shell", "input", "tap", str(x), str(y)],
            capture_output=True
        )
        print(f"  → Tapped at ({x}, {y})")
    
    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300):
        """Send swipe event to emulator."""
        subprocess.run(
            ["adb", "-s", self.device, "shell", "input", "swipe",
             str(x1), str(y1), str(x2), str(y2), str(duration_ms)],
            capture_output=True
        )
        print(f"  → Swiped from ({x1}, {y1}) to ({x2}, {y2})")
    
    def key_event(self, keycode: int):
        """Send key event to emulator (e.g., KEYCODE_BACK = 4)."""
        subprocess.run(
            ["adb", "-s", self.device, "shell", "input", "keyevent", str(keycode)],
            capture_output=True
        )
        print(f"  → Key event: {keycode}")
    
    def get_screen_size(self) -> tuple:
        """Get screen resolution of the emulator."""
        result = subprocess.run(
            ["adb", "-s", self.device, "shell", "wm", "size"],
            capture_output=True, text=True
        )
        # Output format: "Physical size: 1280x720"
        if "x" in result.stdout:
            size_str = result.stdout.split(":")[-1].strip()
            width, height = size_str.split("x")
            return int(width), int(height)
        return (1280, 720)  # Default fallback

