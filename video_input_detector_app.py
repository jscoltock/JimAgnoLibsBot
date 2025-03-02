"""
Streamlit app to detect and display available video inputs.

This app uses the check_video_inputs.py script to detect and display:
1. Available camera devices
2. Available screen capture options
3. Command-line options for using them with the Live API
"""

import streamlit as st
import cv2
import mss
import mss.tools
import numpy as np
import io
from PIL import Image
import time
import sys
import os
from pathlib import Path

# Import functions from check_video_inputs.py
from check_video_inputs import check_camera_devices, check_screen_devices

# Set page config
st.set_page_config(
    page_title="Video Input Detector",
    page_icon="🎥",
    layout="wide"
)

# Initialize session state for storing scan results
if 'cameras' not in st.session_state:
    st.session_state.cameras = []
if 'screens' not in st.session_state:
    st.session_state.screens = []

# Title and description
st.title("🎥 Video Input Detector")
st.write("""
This app detects and displays all available video inputs (cameras and screens) on your system.
You can use this information to configure the Live API component.
""")

# Create tabs for different sections
tab1, tab2, tab3 = st.tabs(["Camera Devices", "Screen Devices", "Live API Usage"])

# Function to capture and display a camera preview
def show_camera_preview(camera_index, preview_time=5):
    """Capture and display a preview from the specified camera."""
    try:
        # Try DirectShow first (Windows-specific)
        cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            # Try default backend
            cap = cv2.VideoCapture(camera_index)
            if not cap.isOpened():
                st.error(f"Could not open camera {camera_index}")
                return False
        
        # Create a placeholder for the video
        preview_placeholder = st.empty()
        
        # Display frames for the specified time
        start_time = time.time()
        while time.time() - start_time < preview_time:
            ret, frame = cap.read()
            if not ret:
                st.error("Failed to capture frame")
                break
            
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Display the frame
            preview_placeholder.image(frame_rgb, caption=f"Camera {camera_index} Live Preview", use_column_width=True)
            
            # Short delay
            time.sleep(0.03)
        
        # Release the camera
        cap.release()
        
        # Clear the placeholder
        preview_placeholder.empty()
        
        return True
    
    except Exception as e:
        st.error(f"Error previewing camera {camera_index}: {str(e)}")
        return False

# Function to capture and display a screen preview
def show_screen_preview(monitor_index, preview_time=5):
    """Capture and display a preview of the specified monitor."""
    try:
        # Create MSS instance
        with mss.mss() as sct:
            # Check if monitor index is valid
            if monitor_index >= len(sct.monitors):
                st.error(f"Invalid monitor index: {monitor_index}")
                return False
            
            # Get the monitor
            monitor = sct.monitors[monitor_index]
            
            # Create a placeholder for the preview
            preview_placeholder = st.empty()
            
            # Display frames for the specified time
            start_time = time.time()
            while time.time() - start_time < preview_time:
                # Capture the screen
                screenshot = sct.grab(monitor)
                
                # Convert to PIL Image
                img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
                
                # Display the image
                preview_placeholder.image(img, caption=f"Monitor {monitor_index} Live Preview", use_column_width=True)
                
                # Short delay
                time.sleep(0.2)
            
            # Clear the placeholder
            preview_placeholder.empty()
            
            return True
    
    except Exception as e:
        st.error(f"Error previewing monitor {monitor_index}: {str(e)}")
        return False

# Camera Devices Tab
with tab1:
    st.header("Camera Devices")
    
    # Scan for cameras button
    if st.button("Scan for Camera Devices", key="scan_cameras"):
        with st.spinner("Scanning for camera devices..."):
            st.session_state.cameras = check_camera_devices(show_preview=False)
        
    # Display camera information if available
    if st.session_state.cameras:
        st.success(f"Found {len(st.session_state.cameras)} camera device(s)")
        
        # Display camera information in a table
        camera_data = []
        for cam in st.session_state.cameras:
            camera_data.append({
                "Index": cam["index"],
                "Resolution": cam["resolution"],
                "FPS": f"{cam['fps']:.1f}",
                "Backend": cam["backend"]
            })
        
        st.table(camera_data)
        
        # Camera preview section
        st.subheader("Camera Preview")
        
        # Create columns for the camera selection and preview button
        col1, col2 = st.columns([3, 1])
        
        # Select a camera to preview
        with col1:
            selected_camera = st.selectbox(
                "Select a camera to preview",
                options=[cam["index"] for cam in st.session_state.cameras],
                format_func=lambda x: f"Camera {x} ({next((c['resolution'] for c in st.session_state.cameras if c['index'] == x), 'Unknown')})",
                key="selected_camera"
            )
        
        # Preview button
        with col2:
            if st.button("Show Camera Preview", key="preview_camera_button"):
                with st.spinner(f"Previewing camera {selected_camera}..."):
                    show_camera_preview(selected_camera, preview_time=5)
    else:
        if "scan_cameras" in st.session_state and st.session_state.scan_cameras:
            st.warning("No camera devices found")
            st.info("Check your camera connections or permissions")
        else:
            st.info("Click 'Scan for Camera Devices' to detect available cameras")

# Screen Devices Tab
with tab2:
    st.header("Screen Devices")
    
    # Scan for screens button
    if st.button("Scan for Screen Devices", key="scan_screens"):
        with st.spinner("Scanning for screen devices..."):
            st.session_state.screens = check_screen_devices(show_preview=False)
    
    # Display screen information if available
    if st.session_state.screens:
        st.success(f"Found {len(st.session_state.screens)} screen device(s)")
        
        # Display screen information in a table
        screen_data = []
        for screen in st.session_state.screens:
            screen_data.append({
                "Index": screen["index"],
                "Resolution": screen["resolution"],
                "Position": screen["position"]
            })
        
        st.table(screen_data)
        
        # Screen preview section
        st.subheader("Screen Preview")
        
        # Create columns for the screen selection and preview button
        col1, col2 = st.columns([3, 1])
        
        # Select a screen to preview
        with col1:
            selected_screen = st.selectbox(
                "Select a screen to preview",
                options=[screen["index"] for screen in st.session_state.screens],
                format_func=lambda x: f"Monitor {x} ({next((s['resolution'] for s in st.session_state.screens if s['index'] == x), 'Unknown')})",
                key="selected_screen"
            )
        
        # Preview button
        with col2:
            if st.button("Show Screen Preview", key="preview_screen_button"):
                with st.spinner(f"Previewing monitor {selected_screen}..."):
                    show_screen_preview(selected_screen, preview_time=5)
    else:
        if "scan_screens" in st.session_state and st.session_state.scan_screens:
            st.warning("No screen devices found")
        else:
            st.info("Click 'Scan for Screen Devices' to detect available screens")

# Live API Usage Tab
with tab3:
    st.header("Live API Usage")
    
    st.subheader("Current Configuration")
    st.code("""
# In live_api_component.py, the Live API is started with:
process = subprocess.Popen(
    [sys.executable, str(script_path), "--camera-index", "1"],
    # ... other parameters ...
)
    """)
    
    st.info("This means it's using camera mode (default) with camera index 1")
    
    st.subheader("Command-Line Options")
    
    # Camera mode
    st.write("**Camera Mode**")
    st.code("python live_api_starter.py --mode camera --camera-index INDEX")
    
    # Screen mode
    st.write("**Screen Mode**")
    st.code("python live_api_starter.py --mode screen")
    
    # Audio only mode
    st.write("**Audio Only Mode**")
    st.code("python live_api_starter.py --mode none")
    
    st.subheader("Enhanced Component")
    st.write("""
    We've created an enhanced version of the Live API component that allows selecting between camera and screen inputs:
    
    ```python
    from monorepo.simple_streamlit_multimodal.ui.enhanced_live_api_component import render_enhanced_live_api_toggle
    
    # In your Streamlit app
    render_enhanced_live_api_toggle()
    ```
    
    This component provides a dropdown to select the input mode and camera index.
    """)

# Footer
st.markdown("---")
st.caption("Video Input Detector | Created for the Live API component")

if __name__ == "__main__":
    # This will only run when the script is executed directly
    pass 