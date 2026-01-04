"""
ADB Controller for interacting with MuMu Player emulator.
Handles screenshots, taps, and other input commands.
"""

import subprocess
import io
import random
from PIL import Image
from config import CLICK_FUZZINESS, BUTTONS_RELATIVE


class ADBController:
    def __init__(self, device_id: str = None):
        """
        Initialize ADB controller.
        
        Args:
            device_id: Specific device ID to use. If None, auto-detects first available.
        """
        if device_id:
            self.device = device_id
            print(f"✓ Using specified device: {device_id}")
        else:
            self.device = self._auto_detect_device()
            if not self.device:
                raise RuntimeError("No ADB device found. Please connect an emulator/device and run 'adb devices' to verify.")
        
        # Auto-detect screen size from screenshot
        self.screen_width, self.screen_height = self._detect_screen_size()
        print(f"✓ Detected screen size: {self.screen_width}x{self.screen_height}")
        
        # Convert relative button coordinates to absolute coordinates
        self.buttons = self._calculate_button_coordinates()
    
    @staticmethod
    def get_device_name(device_id: str) -> str:
        """Get a friendly name for a device by querying its properties."""
        try:
            # Try to get device name from settings (works on most Android devices)
            result = subprocess.run(
                ["adb", "-s", device_id, "shell", "settings", "get", "global", "device_name"],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0 and result.stdout.strip() and result.stdout.strip() != "null":
                return result.stdout.strip()
            
            # Try product model
            result = subprocess.run(
                ["adb", "-s", device_id, "shell", "getprop", "ro.product.model"],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            
            # Try product name
            result = subprocess.run(
                ["adb", "-s", device_id, "shell", "getprop", "ro.product.name"],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
                
        except Exception:
            pass
        
        return ""
    
    @staticmethod
    def list_devices() -> list:
        """
        List all connected ADB devices.
        Returns list of tuples: (device_id, status, description)
        """
        result = subprocess.run(
            ["adb", "devices", "-l"],
            capture_output=True, text=True
        )
        
        devices = []
        lines = result.stdout.strip().split('\n')[1:]  # Skip header
        for line in lines:
            if line.strip() and '\t' in line:
                parts = line.split()
                device_id = parts[0]
                status = parts[1] if len(parts) > 1 else "unknown"
                
                if status == "device":  # Only include connected devices
                    # Try to get a friendly name
                    description = ADBController.get_device_name(device_id)
                    
                    # Fallback to model from adb output
                    if not description:
                        for part in parts[2:]:
                            if part.startswith("model:"):
                                description = part.replace("model:", "").replace("_", " ")
                                break
                            elif part.startswith("device:"):
                                description = part.replace("device:", "").replace("_", " ")
                    
                    devices.append((device_id, status, description))
        
        return devices
    
    def _auto_detect_device(self) -> str:
        """Auto-detect the first available ADB device."""
        devices = self.list_devices()
        
        if devices:
            device = devices[0][0]  # Use first available device
            print(f"✓ Auto-detected device: {device}")
            if len(devices) > 1:
                print(f"  Note: {len(devices)} devices found, using {device}")
                print(f"  Use --device <id> to select a specific device")
            return device
        else:
            print("✗ No ADB devices found")
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
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
    
    def tap(self, x: int, y: int):
        """Send tap event to emulator with random offset for human-like behavior."""
        # Add random offset to coordinates (±CLICK_FUZZINESS pixels)
        offset_x = random.randint(-CLICK_FUZZINESS, CLICK_FUZZINESS)
        offset_y = random.randint(-CLICK_FUZZINESS, CLICK_FUZZINESS)
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

