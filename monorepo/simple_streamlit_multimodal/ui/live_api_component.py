"""
Minimal Live API component with just an on/off toggle.
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
        logging.FileHandler(Path(__file__).parent.parent / "logs" / "live_api_component.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("live_api_component")

def initialize_live_api_state():
    """Initialize session state variables for the Live API component."""
    if 'live_api_running' not in st.session_state:
        st.session_state.live_api_running = False
    if 'live_api_process' not in st.session_state:
        st.session_state.live_api_process = None

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
        logger.info("Starting Live API process")
        
        # Get the path to the live_api_starter.py script
        script_path = Path(__file__).parent.parent / "live_api_starter.py"
        
        # Start the process
        process = subprocess.Popen(
            [sys.executable, str(script_path), "--camera-index", "0"],
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

def render_live_api_toggle():
    """Render just a simple on/off toggle for the Live API."""
    # Initialize session state
    initialize_live_api_state()
    
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
    
    # Simple on/off toggle
    col1, col2 = st.columns([1, 3])
    
    with col1:
        if not st.session_state.live_api_running:
            if st.button("Start Live API", type="primary"):
                start_live_api()
                st.rerun()  # Force UI update
        else:
            if st.button("Stop Live API", type="secondary"):
                stop_live_api()
                st.rerun()  # Force UI update
    
    with col2:
        if st.session_state.live_api_running:
            st.success("Live API is running")
            st.caption("Speak into your microphone to interact with the model")
        else:
            st.info("Live API is stopped") 