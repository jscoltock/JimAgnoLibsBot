import asyncio
import base64
import io
import json
import os
import queue
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
import argparse
import logging
import signal
import wave
import subprocess
import platform

import cv2
import numpy as np
import pyaudio
import google.generativeai as genai
from PIL import Image as PILImage
from mss import mss

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent / "logs" / "live_api.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("live_api")

# Constants
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
DEFAULT_SILENCE_THRESHOLD = 300
SILENCE_DURATION = 1.0  # seconds
DEFAULT_MODE = "camera"
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
SCREEN_WIDTH = 640
SCREEN_HEIGHT = 480
DEFAULT_CAMERA_INDEX = 1  # Changed default camera index to 1

# Configure Google Generative AI
API_KEY = os.environ.get("GOOGLE_API_KEY")
if not API_KEY:
    logger.error("GOOGLE_API_KEY environment variable not set")
    sys.exit(1)

genai.configure(api_key=API_KEY)

def list_available_cameras():
    """List all available camera devices."""
    index = 0
    available_cameras = []
    while True:
        cap = cv2.VideoCapture(index)
        if not cap.read()[0]:
            break
        available_cameras.append(index)
        cap.release()
        index += 1
    return available_cameras

def test_camera_access(camera_index):
    """Test if a camera can be accessed."""
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        logger.error(f"Failed to open camera {camera_index}")
        return False
    ret, frame = cap.read()
    cap.release()
    if not ret:
        logger.error(f"Failed to read from camera {camera_index}")
        return False
    return True

def create_wav_file(audio_data, filename="temp_audio.wav"):
    """Create a WAV file from audio data."""
    try:
        # Create a temporary directory if it doesn't exist
        temp_dir = Path(__file__).parent / "tmp"
        temp_dir.mkdir(exist_ok=True)
        
        # Create the full path for the WAV file
        wav_path = temp_dir / filename
        
        # Create the WAV file
        with wave.open(str(wav_path), 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)  # 2 bytes for paInt16
            wf.setframerate(RATE)
            wf.writeframes(audio_data)
        
        return wav_path
    except Exception as e:
        logger.error(f"Error creating WAV file: {e}")
        return None

def play_audio(text, volume=0.5):
    """Play audio response using text-to-speech."""
    try:
        # Create a temporary directory if it doesn't exist
        temp_dir = Path(__file__).parent / "tmp"
        temp_dir.mkdir(exist_ok=True)
        
        # Create a temporary file for the response
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        response_file = temp_dir / f"response_{timestamp}.txt"
        
        # Write the text to the file
        with open(response_file, "w", encoding="utf-8") as f:
            f.write(text)
        
        # Use platform-specific text-to-speech
        if platform.system() == "Windows":
            # Use PowerShell's text-to-speech on Windows
            volume_percent = int(volume * 100)
            ps_command = f'powershell -Command "Add-Type -AssemblyName System.Speech; $speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; $speak.Volume = {volume_percent}; $speak.Speak([System.IO.File]::ReadAllText(\'{response_file}\'))"'
            subprocess.Popen(ps_command, shell=True)
        elif platform.system() == "Darwin":  # macOS
            # Use say command on macOS
            subprocess.Popen(["say", "-f", str(response_file)])
        else:  # Linux and others
            # Try using espeak on Linux
            try:
                subprocess.Popen(["espeak", "-f", str(response_file)])
            except:
                logger.warning("Could not play audio response. Text-to-speech not available.")
        
        # Return the path to the response file for cleanup
        return response_file
    except Exception as e:
        logger.error(f"Error playing audio response: {e}")
        return None

class LiveAPIController:
    """Controller for the Live API that can be started and stopped programmatically."""
    
    def __init__(self, video_mode=DEFAULT_MODE, camera_index=DEFAULT_CAMERA_INDEX):
        """Initialize the controller."""
        self.video_mode = video_mode
        self.camera_index = camera_index
        self.running = False
        self.stop_event = threading.Event()
        self.audio = None  # Initialize audio when needed
        self.audio_queue = queue.Queue()
        self.model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={
                "temperature": 0.4,
                "top_p": 1,
                "top_k": 32,
                "max_output_tokens": 8192,
            },
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ],
        )
        self.thread = None
        self.loop = None
        self.temp_files = []  # Track temporary files for cleanup
        self.silence_threshold = DEFAULT_SILENCE_THRESHOLD
        self.volume = 0.5  # Default volume
        self.last_response = ""  # Store the last response
        self.is_playing_audio = False  # Flag to prevent feedback loops
        self.user_initiated = False  # Flag to ensure responses are user-initiated
        logger.info(f"Initialized LiveAPIController with video_mode={video_mode}, camera_index={camera_index}")

    def set_volume(self, volume):
        """Set the volume for audio output."""
        self.volume = max(0.0, min(1.0, volume))  # Ensure volume is between 0.0 and 1.0
        logger.info(f"Volume set to {self.volume}")

    def set_silence_threshold(self, threshold):
        """Set the silence threshold for audio detection."""
        self.silence_threshold = threshold
        logger.info(f"Silence threshold set to {self.silence_threshold}")

    def _get_frame(self, cap):
        """Get a frame from the camera."""
        ret, frame = cap.read()
        if not ret:
            logger.error("Failed to capture frame")
            return None
        
        # Resize frame
        frame = cv2.resize(frame, (CAMERA_WIDTH, CAMERA_HEIGHT))
        
        # Convert to RGB (from BGR)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        return frame

    def _get_screen(self):
        """Capture the screen."""
        with mss() as sct:
            monitor = sct.monitors[1]  # Primary monitor
            sct_img = sct.grab(monitor)
            img = np.array(sct_img)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
            img = cv2.resize(img, (SCREEN_WIDTH, SCREEN_HEIGHT))
            return img

    async def get_frames(self):
        """Get frames from the camera or screen."""
        if self.video_mode == "none":
            return
        
        if self.video_mode == "camera":
            cap = cv2.VideoCapture(self.camera_index)
            if not cap.isOpened():
                logger.error(f"Failed to open camera {self.camera_index}")
                return
            
            try:
                while not self.stop_event.is_set():
                    frame = self._get_frame(cap)
                    if frame is None:
                        continue
                    
                    # Only process frames if user has initiated interaction
                    # This prevents automatic responses to camera input
                    if not self.user_initiated:
                        await asyncio.sleep(0.1)
                        continue
                    
                    # Convert to base64
                    pil_img = PILImage.fromarray(frame)
                    img_byte_arr = io.BytesIO()
                    pil_img.save(img_byte_arr, format='JPEG')
                    img_bytes = img_byte_arr.getvalue()
                    img_b64 = base64.b64encode(img_bytes).decode('utf-8')
                    
                    # Create content part
                    content_part = {
                        "role": "user",
                        "parts": [
                            {"text": "Please describe what you see in this image."},
                            {
                                "inline_data": {
                                    "mime_type": "image/jpeg",
                                    "data": img_b64
                                }
                            }
                        ]
                    }
                    
                    try:
                        # Send to model
                        response = await self.model.generate_content_async([content_part])
                        
                        # Process response
                        if hasattr(response, 'text'):
                            response_text = response.text
                            print(f"Response: {response_text}")
                            
                            # Store the last response
                            self.last_response = response_text
                            
                            # Set flag to prevent audio feedback
                            self.is_playing_audio = True
                            
                            # Play audio response
                            response_file = play_audio(response_text, self.volume)
                            if response_file:
                                self.temp_files.append(response_file)
                            
                            # Wait a bit for the audio to finish playing
                            # This is an estimate - text-to-speech duration varies
                            # Roughly estimate 100ms per character
                            estimated_duration = len(response_text) * 0.1
                            await asyncio.sleep(max(2.0, estimated_duration))
                            
                            # Reset flag after estimated playback time
                            self.is_playing_audio = False
                            
                            # Reset user_initiated flag after response
                            self.user_initiated = False
                    except Exception as e:
                        logger.error(f"Error generating content: {e}")
                        self.is_playing_audio = False  # Reset flag in case of error
                        self.user_initiated = False  # Reset user_initiated flag in case of error
                    
                    await asyncio.sleep(1)  # Adjust rate as needed
            except Exception as e:
                logger.error(f"Error in camera capture: {e}")
            finally:
                cap.release()
        
        elif self.video_mode == "screen":
            try:
                while not self.stop_event.is_set():
                    frame = self._get_screen()
                    
                    # Only process frames if user has initiated interaction
                    # This prevents automatic responses to screen input
                    if not self.user_initiated:
                        await asyncio.sleep(0.1)
                        continue
                    
                    # Convert to base64
                    pil_img = PILImage.fromarray(frame)
                    img_byte_arr = io.BytesIO()
                    pil_img.save(img_byte_arr, format='JPEG')
                    img_bytes = img_byte_arr.getvalue()
                    img_b64 = base64.b64encode(img_bytes).decode('utf-8')
                    
                    # Create content part
                    content_part = {
                        "role": "user",
                        "parts": [
                            {"text": "Please describe what you see on this screen."},
                            {
                                "inline_data": {
                                    "mime_type": "image/jpeg",
                                    "data": img_b64
                                }
                            }
                        ]
                    }
                    
                    try:
                        # Send to model
                        response = await self.model.generate_content_async([content_part])
                        
                        # Process response
                        if hasattr(response, 'text'):
                            response_text = response.text
                            print(f"Response: {response_text}")
                            
                            # Store the last response
                            self.last_response = response_text
                            
                            # Set flag to prevent audio feedback
                            self.is_playing_audio = True
                            
                            # Play audio response
                            response_file = play_audio(response_text, self.volume)
                            if response_file:
                                self.temp_files.append(response_file)
                            
                            # Wait a bit for the audio to finish playing
                            # This is an estimate - text-to-speech duration varies
                            # Roughly estimate 100ms per character
                            estimated_duration = len(response_text) * 0.1
                            await asyncio.sleep(max(2.0, estimated_duration))
                            
                            # Reset flag after estimated playback time
                            self.is_playing_audio = False
                            
                            # Reset user_initiated flag after response
                            self.user_initiated = False
                    except Exception as e:
                        logger.error(f"Error generating content: {e}")
                        self.is_playing_audio = False  # Reset flag in case of error
                        self.user_initiated = False  # Reset user_initiated flag in case of error
                    
                    await asyncio.sleep(1)  # Adjust rate as needed
            except Exception as e:
                logger.error(f"Error in screen capture: {e}")

    async def listen_audio(self):
        """Listen to audio from the microphone."""
        # Initialize audio if not already done
        if self.audio is None:
            try:
                self.audio = pyaudio.PyAudio()
            except Exception as e:
                logger.error(f"Failed to initialize audio: {e}")
                return
        
        try:
            stream = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )
            
            logger.info("Started listening to audio")
            audio_data = []
            silence_frames = 0
            speaking = False
            
            while not self.stop_event.is_set():
                # Skip audio capture if we're currently playing audio to prevent feedback loops
                if self.is_playing_audio:
                    await asyncio.sleep(0.1)
                    continue
                
                try:
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    audio_array = np.frombuffer(data, dtype=np.int16)
                    
                    # Check if speaking using the current silence threshold
                    if np.abs(audio_array).mean() > self.silence_threshold:
                        silence_frames = 0
                        if not speaking:
                            speaking = True
                            logger.info("Started speaking")
                        audio_data.append(data)
                    else:
                        silence_frames += 1
                        if speaking:
                            audio_data.append(data)
                        
                        # Check if silence duration exceeded
                        if speaking and silence_frames > (RATE / CHUNK) * SILENCE_DURATION:
                            speaking = False
                            if audio_data:
                                logger.info("Stopped speaking, processing audio")
                                audio_bytes = b''.join(audio_data)
                                self.audio_queue.put(audio_bytes)
                                # Set user_initiated flag when audio is detected
                                self.user_initiated = True
                                audio_data = []
                except Exception as e:
                    logger.error(f"Error reading audio: {e}")
                    break
                
                await asyncio.sleep(0.01)
        except Exception as e:
            logger.error(f"Error in audio stream: {e}")
        finally:
            try:
                stream.stop_stream()
                stream.close()
            except Exception as e:
                logger.error(f"Error closing audio stream: {e}")
            logger.info("Stopped listening to audio")

    async def process_audio(self):
        """Process audio from the queue."""
        while not self.stop_event.is_set():
            try:
                if not self.audio_queue.empty():
                    audio_bytes = self.audio_queue.get()
                    
                    # Create a WAV file from the audio data
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    wav_path = create_wav_file(audio_bytes, f"audio_{timestamp}.wav")
                    
                    if wav_path and wav_path.exists():
                        # Add to temp files list for cleanup
                        self.temp_files.append(wav_path)
                        
                        try:
                            # Read the file as binary data
                            with open(wav_path, "rb") as f:
                                audio_file_data = f.read()
                            
                            # Convert to base64
                            audio_b64 = base64.b64encode(audio_file_data).decode('utf-8')
                            
                            # Create content part with proper prompt
                            content_part = {
                                "role": "user",
                                "parts": [
                                    {"text": "Please transcribe and respond to this audio."},
                                    {
                                        "inline_data": {
                                            "mime_type": "audio/wav",
                                            "data": audio_b64
                                        }
                                    }
                                ]
                            }
                            
                            # Send to model
                            response = await self.model.generate_content_async([content_part])
                            
                            # Process response
                            if hasattr(response, 'text'):
                                response_text = response.text
                                print(f"Response: {response_text}")
                                
                                # Store the last response
                                self.last_response = response_text
                                
                                # Set flag to prevent audio feedback
                                self.is_playing_audio = True
                                
                                # Play audio response
                                response_file = play_audio(response_text, self.volume)
                                if response_file:
                                    self.temp_files.append(response_file)
                                
                                # Wait a bit for the audio to finish playing
                                # This is an estimate - text-to-speech duration varies
                                # Roughly estimate 100ms per character plus a base time
                                estimated_duration = len(response_text) * 0.1
                                await asyncio.sleep(max(3.0, estimated_duration))
                                
                                # Reset flag after estimated playback time
                                self.is_playing_audio = False
                                
                                # Reset user_initiated flag after response
                                self.user_initiated = False
                        except Exception as e:
                            logger.error(f"Error generating content from audio file: {e}")
                            self.is_playing_audio = False  # Reset flag in case of error
                            self.user_initiated = False  # Reset user_initiated flag in case of error
                    else:
                        logger.error("Failed to create WAV file from audio data")
                
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error processing audio: {e}")
                self.is_playing_audio = False  # Reset flag in case of error
                self.user_initiated = False  # Reset user_initiated flag in case of error

    async def run(self):
        """Run the controller."""
        logger.info(f"Starting LiveAPIController with video_mode={self.video_mode}")
        tasks = []
        
        # Add video task if needed
        if self.video_mode != "none":
            tasks.append(self.get_frames())
        
        # Add audio tasks
        tasks.append(self.listen_audio())
        tasks.append(self.process_audio())
        
        # Run all tasks
        await asyncio.gather(*tasks)

    def start(self):
        """Start the controller in a separate thread."""
        if self.running:
            logger.warning("Controller is already running")
            return
        
        self.stop_event.clear()
        self.running = True
        
        def run_async_loop():
            # Create a new event loop for this thread
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            try:
                # Initialize audio here to ensure it's in the right thread
                if self.audio is None:
                    try:
                        self.audio = pyaudio.PyAudio()
                    except Exception as e:
                        logger.error(f"Failed to initialize audio: {e}")
                
                # Run the main task
                self.loop.run_until_complete(self.run())
            except Exception as e:
                logger.error(f"Error in async loop: {e}")
            finally:
                # Clean up the loop properly
                try:
                    # Cancel all running tasks
                    pending = asyncio.all_tasks(self.loop)
                    for task in pending:
                        task.cancel()
                    
                    # Run the event loop until all tasks are cancelled
                    if pending:
                        self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    
                    # Close the loop
                    self.loop.close()
                except Exception as e:
                    logger.error(f"Error cleaning up event loop: {e}")
        
        self.thread = threading.Thread(target=run_async_loop)
        self.thread.daemon = True
        self.thread.start()
        logger.info("Controller started")

    def stop(self):
        """Stop the controller."""
        if not self.running:
            logger.warning("Controller is not running")
            return
        
        logger.info("Stopping controller")
        self.stop_event.set()
        self.running = False
        
        if self.thread:
            try:
                self.thread.join(timeout=5)
                if self.thread.is_alive():
                    logger.warning("Thread did not terminate properly")
            except Exception as e:
                logger.error(f"Error joining thread: {e}")
        
        logger.info("Controller stopped")

    def cleanup(self):
        """Clean up resources."""
        try:
            self.stop()
            
            # Clean up audio
            if self.audio:
                try:
                    self.audio.terminate()
                    self.audio = None
                except Exception as e:
                    logger.error(f"Error terminating audio: {e}")
            
            # Clean up temporary files
            for file_path in self.temp_files:
                try:
                    if file_path.exists():
                        file_path.unlink()
                        logger.info(f"Removed temporary file: {file_path}")
                except Exception as e:
                    logger.error(f"Error removing temporary file {file_path}: {e}")
            
            # Clear the list
            self.temp_files = []
            
            logger.info("Resources cleaned up")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def get_last_response(self):
        """Get the last response from the model."""
        return self.last_response

# For testing the controller directly
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live API Controller")
    parser.add_argument("--mode", choices=["camera", "screen", "none"], default=DEFAULT_MODE, help="Video mode")
    parser.add_argument("--camera", type=int, default=0, help="Camera index")
    args = parser.parse_args()
    
    controller = LiveAPIController(video_mode=args.mode, camera_index=args.camera)
    
    # Handle Ctrl+C
    def signal_handler(sig, frame):
        print("Stopping controller...")
        controller.cleanup()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        controller.start()
        print("Controller started. Press Ctrl+C to stop.")
        while controller.running:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        controller.cleanup() 