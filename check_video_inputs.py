"""
Check all available video inputs (cameras and screens) for the Live API.

This script will:
1. Detect all available camera devices
2. Detect all available screen capture options
3. Display their properties and provide command-line options to use with Live API

Usage:
    python check_video_inputs.py [--camera-preview] [--screen-preview]
"""

import cv2
import mss
import mss.tools
import numpy as np
import argparse
import sys
from PIL import Image
import io

def check_camera_devices(show_preview=False, preview_time=2000):
    """
    Check all available camera devices with their properties.
    
    Args:
        show_preview: If True, shows a brief preview from each working camera
        preview_time: Time in milliseconds to show the preview (if enabled)
    
    Returns:
        A list of dictionaries containing camera information
    """
    print("\n=== CAMERA DEVICE SCANNER ===")
    print("Scanning for available camera devices...\n")
    
    # Store information about found cameras
    available_cameras = []
    
    # Try a range of indices (0-9 should cover most systems)
    for index in range(10):
        print(f"Checking camera index {index}...", end="", flush=True)
        
        # Try to open the camera with different backends
        cap = None
        working_backend = None
        
        # Try DirectShow first (Windows-specific)
        try:
            cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    working_backend = "DirectShow"
        except Exception:
            pass
        
        # If DirectShow failed, try the default backend
        if working_backend is None:
            try:
                if cap is not None:
                    cap.release()
                
                cap = cv2.VideoCapture(index)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret:
                        working_backend = "Default"
            except Exception:
                pass
        
        # Check if we found a working camera
        if working_backend is not None:
            # Get camera properties
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            # Store camera info
            camera_info = {
                "index": index,
                "backend": working_backend,
                "resolution": f"{width}x{height}",
                "fps": fps
            }
            available_cameras.append(camera_info)
            
            print(f" ✓ FOUND - {working_backend} backend, {width}x{height} @ {fps:.1f} FPS")
            
            # Show preview if requested
            if show_preview and ret:
                window_name = f"Camera {index} Preview"
                cv2.imshow(window_name, frame)
                cv2.waitKey(preview_time)
                cv2.destroyWindow(window_name)
        else:
            print(" ✗ Not available")
        
        # Release the capture object
        if cap is not None:
            cap.release()
    
    return available_cameras

def check_screen_devices(show_preview=False, preview_time=2000):
    """
    Check all available screen capture options with their properties.
    
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

def print_live_api_usage_examples(cameras, screens):
    """Print example commands for using the Live API with different inputs."""
    print("\n=== LIVE API USAGE EXAMPLES ===")
    
    # Camera examples
    if cameras:
        print("\n[CAMERA MODE EXAMPLES]")
        for cam in cameras[:3]:  # Limit to first 3 cameras
            print(f"Camera {cam['index']} ({cam['resolution']}):")
            print(f"  python live_api_starter.py --mode camera --camera-index {cam['index']}")
    
    # Screen examples
    if screens:
        print("\n[SCREEN MODE EXAMPLES]")
        print("Screen capture (primary monitor):")
        print("  python live_api_starter.py --mode screen")
    
    # Audio only example
    print("\n[AUDIO ONLY EXAMPLE]")
    print("Audio only (no video):")
    print("  python live_api_starter.py --mode none")
    
    print("\n===========================")

def main():
    parser = argparse.ArgumentParser(description="Check all available video inputs for Live API")
    parser.add_argument("--camera-preview", action="store_true", help="Show a preview of each camera")
    parser.add_argument("--screen-preview", action="store_true", help="Show a preview of each screen")
    parser.add_argument("--preview-time", type=int, default=2000, 
                        help="Time in milliseconds to show each preview")
    args = parser.parse_args()
    
    # Check camera devices
    cameras = check_camera_devices(args.camera_preview, args.preview_time)
    
    # Check screen devices
    screens = check_screen_devices(args.screen_preview, args.preview_time)
    
    # Print summary for cameras
    print("\n=== CAMERA DEVICE SUMMARY ===")
    if cameras:
        print(f"Found {len(cameras)} camera device(s):")
        for cam in cameras:
            print(f"  Camera index {cam['index']}: {cam['resolution']} @ {cam['fps']:.1f} FPS ({cam['backend']} backend)")
    else:
        print("No working camera devices found.")
        print("Check your camera connections or permissions.")
    
    # Print summary for screens
    print("\n=== SCREEN DEVICE SUMMARY ===")
    if screens:
        print(f"Found {len(screens)} screen device(s):")
        for screen in screens:
            print(f"  Monitor {screen['index']}: {screen['resolution']} at position {screen['position']}")
    else:
        print("No screen devices found.")
    
    # Print usage examples
    print_live_api_usage_examples(cameras, screens)
    
    # Print current configuration in live_api_component.py
    print("\n=== CURRENT CONFIGURATION ===")
    print("In live_api_component.py, the Live API is started with:")
    print("  --camera-index 1")
    print("  (No --mode parameter, defaults to 'camera')")
    print("\nTo change this, modify the subprocess.Popen call in the start_live_api() function.")
    print("===========================")

if __name__ == "__main__":
    main() 