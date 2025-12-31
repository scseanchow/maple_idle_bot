"""
ADB Controller for interacting with MuMu Player emulator.
Handles screenshots, taps, and other input commands.
"""

import subprocess
import io
import random
from PIL import Image
from config import CLICK_FUZZINESS_X, CLICK_FUZZINESS_Y, BUTTONS_RELATIVE


class ADBController:
    def __init__(self):
        self.device = self._auto_detect_device()
        if not self.device:
            raise RuntimeError("No ADB device found. Please connect an emulator/device and run 'adb devices' to verify.")
        
        # Auto-detect screen size from screenshot
        self.screen_width, self.screen_height = self._detect_screen_size()
        print(f"✓ Detected screen size: {self.screen_width}x{self.screen_height}")
        
        # Convert relative button coordinates to absolute coordinates
        self.buttons = self._calculate_button_coordinates()
    
    def _auto_detect_device(self) -> str:
        """Auto-detect the first available ADB device."""
        result = subprocess.run(
            ["adb", "devices"],
            capture_output=True, text=True
        )
        
        # Parse output: "List of devices attached\nemulator-5574\tdevice\n"
        lines = result.stdout.strip().split('\n')[1:]  # Skip header
        devices = []
        for line in lines:
            if line.strip() and '\tdevice' in line:
                device = line.split('\t')[0].strip()
                if device:
                    devices.append(device)
        
        if devices:
            device = devices[0]  # Use first available device
            print(f"✓ Auto-detected device: {device}")
            if len(devices) > 1:
                print(f"  Note: Multiple devices found, using {device}")
            return device
        else:
            print("✗ No ADB devices found")
            print(f"  ADB output:\n{result.stdout}")
            return None
    
    def _detect_screen_size(self) -> tuple:
        """Detect screen size from screenshot (most accurate method)."""
        # First try screenshot method
        try:
            result = subprocess.run(
                ["adb", "-s", self.device, "exec-out", "screencap", "-p"],
                capture_output=True, timeout=5
            )
            if result.returncode == 0:
                screenshot = Image.open(io.BytesIO(result.stdout))
                width, height = screenshot.size
                return width, height
        except Exception as e:
            print(f"⚠ Could not detect screen size from screenshot: {e}")
        
        # Fallback to wm size
        print("  Falling back to 'wm size' command...")
        result = subprocess.run(
            ["adb", "-s", self.device, "shell", "wm", "size"],
            capture_output=True, text=True
        )
        # Output format: "Physical size: 1920x1080"
        if "x" in result.stdout:
            size_str = result.stdout.split(":")[-1].strip()
            width, height = size_str.split("x")
            return int(width), int(height)
        raise RuntimeError("Could not detect screen size")
    
    def _calculate_button_coordinates(self) -> dict:
        """Convert relative button coordinates to absolute coordinates based on screen size."""
        buttons = {}
        for name, (rel_x, rel_y) in BUTTONS_RELATIVE.items():
            abs_x = int(rel_x * self.screen_width)
            abs_y = int(rel_y * self.screen_height)
            buttons[name] = (abs_x, abs_y)
        return buttons
    
    @property
    def BUTTONS(self):
        """Get button coordinates dictionary (for backward compatibility)."""
        return self.buttons
    
    def screenshot(self) -> Image.Image:
        """Capture screenshot from emulator."""
        result = subprocess.run(
            ["adb", "-s", self.device, "exec-out", "screencap", "-p"],
            capture_output=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"Screenshot failed: {result.stderr.decode()}")
        return Image.open(io.BytesIO(result.stdout))
    
    def tap(self, x: int, y: int, click_fuzziness_x: int = CLICK_FUZZINESS_X, click_fuzziness_y: int = CLICK_FUZZINESS_Y):
        """Send tap event to emulator with random offset for human-like behavior."""
        # Add random offset to coordinates (±CLICK_FUZZINESS pixels)
        offset_x = random.randint(-click_fuzziness_x, click_fuzziness_x)
        offset_y = random.randint(-click_fuzziness_y, click_fuzziness_y)
        fuzzy_x = max(0, min(self.screen_width - 1, x + offset_x))  # Clamp to screen bounds
        fuzzy_y = max(0, min(self.screen_height - 1, y + offset_y))  # Clamp to screen bounds
        
        subprocess.run(
            ["adb", "-s", self.device, "shell", "input", "tap", str(fuzzy_x), str(fuzzy_y)],
            capture_output=True
        )
        print(f"  → Tapped at ({fuzzy_x}, {fuzzy_y})")
    
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

