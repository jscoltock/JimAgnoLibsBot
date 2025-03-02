"""
Enhanced Live API component with input selection options.

This component extends the original Live API component by adding:
1. Option to select between camera and screen inputs
2. Option to select camera index
"""

import streamlit as st
import sys
import os
import asyncio
import threading
import traceback
from pathlib import Path
import logging
import subprocess

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent.parent / "logs" / "enhanced_live_api_component.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("enhanced_live_api_component")

def initialize_live_api_state():
    """Initialize session state variables for the Live API component."""
    if 'live_api_running' not in st.session_state:
        st.session_state.live_api_running = False
    if 'live_api_process' not in st.session_state:
        st.session_state.live_api_process = None
    if 'input_mode' not in st.session_state:
        st.session_state.input_mode = "camera"
    if 'camera_index' not in st.session_state:
        st.session_state.camera_index = 0

def start_live_api():
    """Start the Live API as a separate process."""
    # If we think it's already running, check if the process is actually still alive
    if st.session_state.live_api_running:
        if st.session_state.live_api_process and st.session_state.live_api_process.poll() is None:
            # Process is still running
            logger.info("Live API is already running")
            return
        else:
            # Process has terminated or is not valid
            logger.warning("Live API was marked as running but process is not active. Resetting state.")
            st.session_state.live_api_process = None
            st.session_state.live_api_running = False
    
    try:
        logger.info(f"Starting Live API process with mode={st.session_state.input_mode}, camera_index={st.session_state.camera_index}")
        
        # Get the path to the live_api_starter.py script
        script_path = Path(__file__).parent.parent / "live_api_starter.py"
        
        # Build command based on selected input mode
        cmd = [sys.executable, str(script_path), "--mode", st.session_state.input_mode]
        
        # Add camera index if in camera mode
        if st.session_state.input_mode == "camera":
            cmd.extend(["--camera-index", str(st.session_state.camera_index)])
        
        # Start the process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Check if process started successfully
        if process.poll() is not None:
            # Process terminated immediately
            returncode = process.poll()
            stdout, stderr = process.communicate()
            error_msg = f"Live API process failed to start (exit code {returncode})"
            if stderr:
                error_msg += f": {stderr}"
            logger.error(error_msg)
            st.error(error_msg)
            return
        
        # Store the process
        st.session_state.live_api_process = process
        st.session_state.live_api_running = True
        
        logger.info(f"Live API process started with PID {process.pid}")
        
    except Exception as e:
        logger.error(f"Error starting Live API process: {e}")
        logger.error(traceback.format_exc())
        st.error(f"Live API error: {str(e)}")
        
        # Ensure state is reset
        st.session_state.live_api_process = None
        st.session_state.live_api_running = False

def stop_live_api():
    """Stop the Live API process."""
    if not st.session_state.live_api_running:
        return
    
    logger.info("Stopping Live API process")
    
    try:
        # Terminate the process
        if st.session_state.live_api_process:
            # First try to terminate gracefully
            st.session_state.live_api_process.terminate()
            
            # Wait a short time for it to terminate
            try:
                st.session_state.live_api_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                # If it doesn't terminate, force kill it
                logger.warning("Process did not terminate gracefully, killing it")
                st.session_state.live_api_process.kill()
            
            # Clean up any remaining resources
            try:
                stdout, stderr = st.session_state.live_api_process.communicate(timeout=1)
                if stderr:
                    logger.warning(f"Process stderr: {stderr}")
            except:
                pass
                
            # Reset the process
            st.session_state.live_api_process = None
        
        # Reset the running state
        st.session_state.live_api_running = False
        logger.info("Live API process stopped")
        
    except Exception as e:
        logger.error(f"Error stopping Live API process: {e}")
        logger.error(traceback.format_exc())
        st.error(f"Error stopping Live API: {str(e)}")
        
        # Force reset state even if there was an error
        st.session_state.live_api_process = None
        st.session_state.live_api_running = False

def update_input_mode():
    """Update the input mode in session state."""
    # Only allow changes when the API is not running
    if not st.session_state.live_api_running:
        st.session_state.input_mode = st.session_state.temp_input_mode
        logger.info(f"Input mode updated to: {st.session_state.input_mode}")

def update_camera_index():
    """Update the camera index in session state."""
    # Only allow changes when the API is not running
    if not st.session_state.live_api_running:
        st.session_state.camera_index = st.session_state.temp_camera_index
        logger.info(f"Camera index updated to: {st.session_state.camera_index}")

def render_enhanced_live_api_toggle():
    """Render an enhanced Live API toggle with input selection options."""
    # Initialize session state
    initialize_live_api_state()
    
    # Add custom CSS to make the sidebar components more compact
    st.markdown("""
    <style>
    /* Reduce padding in sidebar */
    [data-testid="stSidebar"] .block-container {
        padding-top: 1rem;
        padding-bottom: 0.5rem;
    }
    
    /* Make selectbox and number input more compact */
    .stSelectbox, .stNumberInput {
        margin-bottom: 0.5rem;
    }
    
    /* Reduce spacing between elements */
    div.row-widget.stSelectbox, div.row-widget.stNumberInput {
        padding-bottom: 0.25rem;
    }
    
    /* Make captions more compact */
    .stCaption {
        margin-top: 0;
        margin-bottom: 0.25rem;
        font-size: 0.8rem;
    }
    
    /* Make buttons more compact */
    .stButton button {
        padding: 0.25rem 0.5rem;
        font-size: 0.8rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Check if process is still running
    if st.session_state.live_api_running and st.session_state.live_api_process:
        if st.session_state.live_api_process.poll() is not None:
            # Process has terminated
            returncode = st.session_state.live_api_process.poll()
            stdout, stderr = st.session_state.live_api_process.communicate()
            
            if returncode != 0:
                error_msg = f"Live API process terminated unexpectedly with code {returncode}"
                if stderr:
                    error_msg += f": {stderr}"
                logger.error(error_msg)
                st.error(error_msg)
            else:
                logger.info("Live API process completed successfully")
            
            # Reset state
            st.session_state.live_api_process = None
            st.session_state.live_api_running = False
            st.rerun()
    
    # Input selection options (only enabled when API is not running)
    if not st.session_state.live_api_running:
        # Create temporary variables for the selectors
        if 'temp_input_mode' not in st.session_state:
            st.session_state.temp_input_mode = st.session_state.input_mode
        
        # Initialize temp_camera_index only once if it doesn't exist
        if 'temp_camera_index' not in st.session_state:
            st.session_state.temp_camera_index = st.session_state.camera_index
        
        # Input mode selector with compact label
        st.selectbox(
            "Input:",
            options=["camera", "screen", "none"],
            index=["camera", "screen", "none"].index(st.session_state.input_mode),
            key="temp_input_mode",
            on_change=update_input_mode,
            help="Select the input mode for the Live API"
        )
        
        # Camera index selector (only shown when camera mode is selected)
        if st.session_state.input_mode == "camera":
            # Fix: Don't set both value and key with session state
            camera_index = st.number_input(
                "Camera:",
                min_value=0,
                max_value=9,
                step=1,
                key="temp_camera_index",
                help="Select the camera index (0-9)"
            )
            
            # Update the session state if the value changes
            if camera_index != st.session_state.camera_index and not st.session_state.live_api_running:
                st.session_state.camera_index = camera_index
                logger.info(f"Camera index updated to: {st.session_state.camera_index}")
    
    # Status indicator
    if st.session_state.live_api_running:
        st.success("Live API is running")
        
        # Show compact status message
        if st.session_state.input_mode == "camera":
            st.caption(f"Camera {st.session_state.camera_index}")
        elif st.session_state.input_mode == "screen":
            st.caption("Screen sharing")
        else:  # none
            st.caption("Audio only")
    else:
        st.info("Live API is stopped")
    
    # Start/Stop button
    if not st.session_state.live_api_running:
        if st.button("Start Live API", type="primary", use_container_width=True):
            start_live_api()
            st.rerun()  # Force UI update
    else:
        if st.button("Stop Live API", type="secondary", use_container_width=True):
            stop_live_api()
            st.rerun()  # Force UI update

# For testing the component directly
if __name__ == "__main__":
    st.set_page_config(page_title="Enhanced Live API Component Test", page_icon="🎥")
    st.title("Enhanced Live API Component")
    st.write("This component allows you to select between camera and screen inputs for the Live API.")
    
    render_enhanced_live_api_toggle()
    
    # Add some additional information
    with st.expander("About this component"):
        st.write("""
        This enhanced component extends the original Live API component by adding:
        
        1. **Input Mode Selection**: Choose between camera, screen, or audio-only modes
        2. **Camera Index Selection**: Select which camera to use (if multiple are available)
        
        To find available cameras, run the `check_video_inputs.py` script.
        """) 