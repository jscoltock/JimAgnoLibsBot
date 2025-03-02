"""
List all available screen capture options with their properties.

This script will:
1. Detect all available monitors/screens
2. Display their properties (resolution, position)
3. Show a small preview of each screen

Usage:
    python list_screen_devices.py
"""

import mss
import mss.tools
import numpy as np
import cv2
import argparse
from PIL import Image
import io

def list_screen_devices(show_preview=False, preview_time=2000):
    """
    List all available screen capture options with their properties.
    
    Args:
        show_preview: If True, shows a brief preview of each screen
        preview_time: Time in milliseconds to show the preview (if enabled)
    
    Returns:
        A list of dictionaries containing screen information
    """
    print("\n=== SCREEN DEVICE SCANNER ===")
    print("Scanning for available screen devices...\n")
    
    # Store information about found screens
    available_screens = []
    
    # Create MSS instance
    with mss.mss() as sct:
        # Get all monitors
        for i, monitor in enumerate(sct.monitors):
            # Skip the "All in One" monitor (index 0) if there are other monitors
            if i == 0 and len(sct.monitors) > 1:
                print(f"Monitor {i}: All monitors combined ({monitor['width']}x{monitor['height']})")
                continue
                
            # Get monitor properties
            width = monitor['width']
            height = monitor['height']
            left = monitor['left']
            top = monitor['top']
            
            # Store screen info
            screen_info = {
                "index": i,
                "resolution": f"{width}x{height}",
                "position": f"({left},{top})",
                "monitor": monitor
            }
            available_screens.append(screen_info)
            
            print(f"Monitor {i}: {width}x{height} at position {left},{top}")
            
            # Show preview if requested
            if show_preview:
                # Capture the screen
                screenshot = sct.grab(monitor)
                
                # Convert to an OpenCV compatible numpy array
                img = np.array(screenshot)
                
                # Convert BGRA to BGR (remove alpha channel)
                img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                
                # Resize for preview if too large
                if width > 1280 or height > 720:
                    scale = min(1280 / width, 720 / height)
                    new_width = int(width * scale)
                    new_height = int(height * scale)
                    img_bgr = cv2.resize(img_bgr, (new_width, new_height))
                
                # Show preview
                window_name = f"Monitor {i} Preview"
                cv2.imshow(window_name, img_bgr)
                cv2.waitKey(preview_time)
                cv2.destroyWindow(window_name)
    
    return available_screens

def main():
    parser = argparse.ArgumentParser(description="List available screen capture options")
    parser.add_argument("--preview", action="store_true", help="Show a preview of each screen")
    parser.add_argument("--preview-time", type=int, default=2000, 
                        help="Time in milliseconds to show each preview")
    args = parser.parse_args()
    
    # List screen devices
    screens = list_screen_devices(args.preview, args.preview_time)
    
    # Print summary
    print("\n=== SCREEN DEVICE SUMMARY ===")
    if screens:
        print(f"Found {len(screens)} screen device(s):")
        for screen in screens:
            print(f"  Monitor {screen['index']}: {screen['resolution']} at position {screen['position']}")
        
        print("\nTo use screen capture with the Live API, use:")
        print("  --mode screen")
        
        # Note about which monitor is used
        print("\nNote: The Live API currently captures the primary monitor (usually index 1)")
        print("      The script doesn't support selecting specific monitors yet")
    else:
        print("No screen devices found.")
    
    print("===========================")

if __name__ == "__main__":
    main() 