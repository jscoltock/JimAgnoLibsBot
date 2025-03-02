"""
List all available camera devices with their indices and details.

This script will:
1. Detect all available camera devices
2. Try to open each one and get its properties
3. Display a list of all working cameras with their indices and properties

Usage:
    python list_camera_devices.py
"""

import cv2
import sys
import argparse

def list_camera_devices(show_preview=False, preview_time=2000):
    """
    List all available camera devices with their properties.
    
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

def main():
    parser = argparse.ArgumentParser(description="List available camera devices")
    parser.add_argument("--preview", action="store_true", help="Show a preview of each camera")
    parser.add_argument("--preview-time", type=int, default=2000, 
                        help="Time in milliseconds to show each preview")
    args = parser.parse_args()
    
    # List camera devices
    cameras = list_camera_devices(args.preview, args.preview_time)
    
    # Print summary
    print("\n=== CAMERA DEVICE SUMMARY ===")
    if cameras:
        print(f"Found {len(cameras)} camera device(s):")
        for cam in cameras:
            print(f"  Camera index {cam['index']}: {cam['resolution']} @ {cam['fps']:.1f} FPS ({cam['backend']} backend)")
        
        print("\nTo use a specific camera with the Live API, use:")
        print(f"  --camera-index {cameras[0]['index']}")
    else:
        print("No working camera devices found.")
        print("Check your camera connections or permissions.")
    
    print("\nNote: Some virtual camera software may not be detected correctly.")
    print("===========================")

if __name__ == "__main__":
    main() 