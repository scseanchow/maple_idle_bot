"""
Image detection using OpenCV template matching.
Detects UI elements and game state from screenshots.
"""

import cv2
import numpy as np
from PIL import Image
from pathlib import Path
from config import MATCH_THRESHOLD


class ImageDetector:
    def __init__(self, templates_dir: str = "templates"):
        self.templates_dir = Path(templates_dir)
        self.templates = {}
        self._load_templates()
    
    def _load_templates(self):
        """Load all template images from directory."""
        if not self.templates_dir.exists():
            self.templates_dir.mkdir(parents=True)
            print(f"  Created templates directory: {self.templates_dir}")
            print("  ⚠ No templates found - run with --calibrate to create them")
            return
        
        for template_path in self.templates_dir.glob("*.png"):
            name = template_path.stem
            img = cv2.imread(str(template_path))
            if img is not None:
                self.templates[name] = img
                print(f"  Loaded template: {name}")
        
        if not self.templates:
            print("  ⚠ No templates found - run with --calibrate to create them")
    
    def find_template(self, screenshot: Image.Image, template_name: str) -> tuple:
        """
        Find a template in the screenshot.
        Returns (found: bool, center_x: int, center_y: int, confidence: float)
        """
        if template_name not in self.templates:
            return (False, 0, 0, 0.0)
        
        # Scale down for faster processing (4x faster at 0.5 scale)
        scale = 0.5
        small_screenshot = screenshot.resize(
            (int(screenshot.width * scale), int(screenshot.height * scale)),
            Image.Resampling.LANCZOS
        )
        
        # Scale down template too
        template = self.templates[template_name]
        small_template = cv2.resize(template, None, fx=scale, fy=scale)
        
        # Convert and match on smaller images
        screen_cv = cv2.cvtColor(np.array(small_screenshot), cv2.COLOR_RGB2BGR)
        
        # Template matching
        result = cv2.matchTemplate(screen_cv, small_template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        
        if max_val >= MATCH_THRESHOLD:
            h, w = small_template.shape[:2]
            # Scale coordinates back to original size
            center_x = int((max_loc[0] + w // 2) / scale)
            center_y = int((max_loc[1] + h // 2) / scale)
            return (True, center_x, center_y, max_val)
        
        return (False, 0, 0, max_val)
    
    def find_all_templates(self, screenshot: Image.Image, template_name: str, 
                           threshold: float = None) -> list:
        """
        Find all occurrences of a template in the screenshot.
        Returns list of (center_x, center_y, confidence)
        """
        if template_name not in self.templates:
            return []
        
        threshold = threshold or MATCH_THRESHOLD
        screen_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        template = self.templates[template_name]
        
        result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)
        
        h, w = template.shape[:2]
        matches = []
        for pt in zip(*locations[::-1]):
            center_x = pt[0] + w // 2
            center_y = pt[1] + h // 2
            confidence = result[pt[1], pt[0]]
            matches.append((center_x, center_y, confidence))
        
        return matches
    
    def detect_state(self, screenshot: Image.Image, verbose: bool = False) -> str:
        """
        Detect current game state from screenshot.
        Returns one of: READY, QUEUING, MATCH_FOUND, IN_DUNGEON, CLEAR, ERROR_DIALOG, SLEEP_SCREEN, UNKNOWN
        """
        # Check for sleep screen FIRST - this blocks everything and must be unlocked
        found_sleep, _, _, conf_sleep = self.find_template(screenshot, "sleep_screen")
        if verbose and "sleep_screen" in self.templates:
            print(f"    [debug] sleep_screen: conf={conf_sleep:.3f} found={found_sleep}")
        if found_sleep:
            return "SLEEP_SCREEN"
        
        # Check for error/notice dialog - these block everything and must be dismissed
        # Detect by the "Notice" banner text (more unique than OK button)
        found_notice, _, _, conf_notice = self.find_template(screenshot, "notice_banner")
        if verbose and "notice_banner" in self.templates:
            print(f"    [debug] notice_banner: conf={conf_notice:.3f} found={found_notice}")
        if found_notice:
            return "ERROR_DIALOG"
        
        # Check Auto Match FIRST - it's the "home" state and has highest confidence
        # This prevents false positives from similar cyan buttons
        found_auto, _, _, conf_auto = self.find_template(screenshot, "auto_match_btn")
        if verbose and "auto_match_btn" in self.templates:
            print(f"    [debug] auto_match_btn: conf={conf_auto:.3f} found={found_auto}")
        if found_auto:
            return "READY"
        
        # Check for CLEAR screen text FIRST (unique "CLEAR" banner only on clear screen)
        found_clear, _, _, conf_clear = self.find_template(screenshot, "clear_screen")
        if verbose and "clear_screen" in self.templates:
            print(f"    [debug] clear_screen: conf={conf_clear:.3f} found={found_clear}")
        if found_clear:
            return "CLEAR"
        
        # Check both Accept and Leave buttons, return whichever has higher confidence
        # This prevents cross-matching between similar cyan buttons
        found_accept, _, _, conf_accept = self.find_template(screenshot, "accept_btn")
        found_leave, _, _, conf_leave = self.find_template(screenshot, "leave_btn")
        
        if verbose and "accept_btn" in self.templates:
            print(f"    [debug] accept_btn: conf={conf_accept:.3f} found={found_accept}")
        if verbose and "leave_btn" in self.templates:
            print(f"    [debug] leave_btn: conf={conf_leave:.3f} found={found_leave}")
        
        # If both match, use the one with higher confidence
        if found_accept and found_leave:
            if conf_accept > conf_leave:
                return "MATCH_FOUND"
            else:
                return "CLEAR"
        elif found_accept:
            return "MATCH_FOUND"
        elif found_leave:
            return "CLEAR"
        
        # Check for matchmaking in progress indicator
        found, _, _, conf = self.find_template(screenshot, "matchmaking")
        if verbose and "matchmaking" in self.templates:
            print(f"    [debug] matchmaking: conf={conf:.3f} found={found}")
        if found:
            return "QUEUING"
        
        # Check for minimap (indicates we're in dungeon)
        found, _, _, conf = self.find_template(screenshot, "minimap")
        if verbose and "minimap" in self.templates:
            print(f"    [debug] minimap: conf={conf:.3f} found={found}")
        if found:
            return "IN_DUNGEON"
        
        return "UNKNOWN"
    
    def detect_state_with_fallback(self, screenshot: Image.Image) -> str:
        """
        Detect state with color-based fallback for when templates aren't set up.
        Uses distinctive colors from the UI elements.
        """
        # First try template matching
        state = self.detect_state(screenshot)
        if state != "UNKNOWN" or self.templates:
            return state
        
        # Fallback: Look for distinctive UI colors
        img_array = np.array(screenshot)
        
        # Check for cyan "CLEAR" text (approximate RGB: 0, 255, 255)
        cyan_mask = (
            (img_array[:, :, 0] < 100) &  # Low red
            (img_array[:, :, 1] > 200) &  # High green
            (img_array[:, :, 2] > 200)    # High blue
        )
        cyan_pixels = np.sum(cyan_mask)
        
        # Check for cyan "Auto Match" or "Accept" buttons
        # These are distinctive cyan/turquoise colored buttons
        
        # If lots of cyan in upper portion = CLEAR screen
        h = img_array.shape[0]
        upper_cyan = np.sum(cyan_mask[:h//3, :])
        if upper_cyan > 5000:  # Threshold for "CLEAR" text
            return "CLEAR"
        
        return "UNKNOWN"

