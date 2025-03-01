# -*- coding: utf-8 -*-
# Copyright 2023 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
## Setup

To install the dependencies for this script, run:

``` 
pip install google-genai opencv-python pyaudio pillow mss
```

Before running this script, ensure the `GOOGLE_API_KEY` environment
variable is set to the api-key you obtained from Google AI Studio.

Important: **Use headphones**. This script uses the system default audio
input and output, which often won't include echo cancellation. So to prevent
the model from interrupting itself it is important that you use headphones. 

## Run

To run the script:

```
python live_api_starter.py
```

The script takes a video-mode flag `--mode`, this can be "camera", "screen", or "none".
The default is "camera". To share your screen run:

```
python live_api_starter.py --mode screen
```
"""

import asyncio
import base64
import io
import os
import sys
import traceback

import cv2
import pyaudio
import PIL.Image
import mss

import argparse

from google import genai

if sys.version_info < (3, 11, 0):
    import taskgroup, exceptiongroup

    asyncio.TaskGroup = taskgroup.TaskGroup
    asyncio.ExceptionGroup = exceptiongroup.ExceptionGroup

FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

MODEL = "models/gemini-2.0-flash-exp"

DEFAULT_MODE = "camera"

# Add your API key here
GOOGLE_API_KEY = "AIzaSyAs8OV7InA2A1bNnTVvhJiaioAiylIAuYQ"  # Replace with your actual API key
client = genai.Client(api_key=GOOGLE_API_KEY, http_options={"api_version": "v1alpha"})

# While Gemini 2.0 Flash is in experimental preview mode, only one of AUDIO or
# TEXT may be passed here.
CONFIG = {"generation_config": {"response_modalities": ["AUDIO"]}}

pya = pyaudio.PyAudio()


def list_available_cameras():
    """List all available camera devices."""
    index = 0
    available_cameras = []
    while True:
        try:
            cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if not cap.isOpened():
                break
            ret, _ = cap.read()
            if ret:
                available_cameras.append(index)
            cap.release()
            index += 1
            if index > 10:  # Limit search to 10 cameras
                break
        except Exception as e:
            print(f"Error checking camera {index}: {e}")
            break
    return available_cameras


def test_camera_access(camera_index):
    """Test if a camera can be accessed and return detailed information."""
    print(f"Testing camera at index {camera_index}...")
    
    # Try DirectShow first
    print("Attempting to open with DirectShow...")
    try:
        cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                print(f"✓ Successfully accessed camera {camera_index} with DirectShow")
                print(f"  Resolution: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
                print(f"  FPS: {cap.get(cv2.CAP_PROP_FPS)}")
                cap.release()
                return True
            else:
                print(f"✗ Could open camera {camera_index} with DirectShow but couldn't read frame")
                cap.release()
        else:
            print(f"✗ Failed to open camera {camera_index} with DirectShow")
    except Exception as e:
        print(f"✗ Error with DirectShow: {e}")
    
    # Try default backend
    print("Attempting to open with default backend...")
    try:
        cap = cv2.VideoCapture(camera_index)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                print(f"✓ Successfully accessed camera {camera_index} with default backend")
                print(f"  Resolution: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
                print(f"  FPS: {cap.get(cv2.CAP_PROP_FPS)}")
                cap.release()
                return True
            else:
                print(f"✗ Could open camera {camera_index} with default backend but couldn't read frame")
                cap.release()
        else:
            print(f"✗ Failed to open camera {camera_index} with default backend")
    except Exception as e:
        print(f"✗ Error with default backend: {e}")
    
    return False


class AudioLoop:
    def __init__(self, video_mode=DEFAULT_MODE, camera_index=0):
        self.video_mode = video_mode
        self.camera_index = camera_index

        self.audio_in_queue = None
        self.out_queue = None

        self.session = None

        self.send_text_task = None
        self.receive_audio_task = None
        self.play_audio_task = None

    async def send_text(self):
        while True:
            text = await asyncio.to_thread(
                input,
                "message > ",
            )
            if text.lower() == "q":
                break
            await self.session.send(input=text or ".", end_of_turn=True)

    def _get_frame(self, cap):
        # Read the frameq
        ret, frame = cap.read()
        # Check if the frame was read successfully
        if not ret:
            return None
        # Fix: Convert BGR to RGB color space
        # OpenCV captures in BGR but PIL expects RGB format
        # This prevents the blue tint in the video feed
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = PIL.Image.fromarray(frame_rgb)  # Now using RGB frame
        img.thumbnail([1024, 1024])

        image_io = io.BytesIO()
        img.save(image_io, format="jpeg")
        image_io.seek(0)

        mime_type = "image/jpeg"
        image_bytes = image_io.read()
        return {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode()}

    async def get_frames(self):
        """Get frames from the camera."""
        # Explicitly disable any Android ADB connections
        os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'
        os.environ['OPENCV_VIDEOIO_PRIORITY_GSTREAMER'] = '0'
        
        # Try multiple approaches to open the camera
        cap = None
        
        # Approach 1: DirectShow
        try:
            print(f"Trying to open camera {self.camera_index} with DirectShow...")
            cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if cap.isOpened():
                ret, _ = cap.read()
                if not ret:
                    print("Could open camera but couldn't read frame with DirectShow")
                    cap.release()
                    cap = None
                else:
                    print(f"Successfully opened camera {self.camera_index} with DirectShow")
        except Exception as e:
            print(f"Error with DirectShow approach: {e}")
            if cap and cap.isOpened():
                cap.release()
            cap = None
        
        # Approach 2: Default backend
        if cap is None:
            try:
                print(f"Trying to open camera {self.camera_index} with default backend...")
                cap = cv2.VideoCapture(self.camera_index)
                if cap.isOpened():
                    ret, _ = cap.read()
                    if not ret:
                        print("Could open camera but couldn't read frame with default backend")
                        cap.release()
                        cap = None
                    else:
                        print(f"Successfully opened camera {self.camera_index} with default backend")
                else:
                    print(f"Failed to open camera {self.camera_index} with default backend")
            except Exception as e:
                print(f"Error with default backend approach: {e}")
                if cap and cap.isOpened():
                    cap.release()
                cap = None
        
        # Approach 3: Try other indices if specified index failed
        if cap is None and self.camera_index == 0:
            for idx in range(1, 5):  # Try indices 1-4
                try:
                    print(f"Trying camera index {idx}...")
                    cap = cv2.VideoCapture(idx)
                    if cap.isOpened():
                        ret, _ = cap.read()
                        if ret:
                            print(f"Successfully opened camera at index {idx}")
                            self.camera_index = idx  # Update the index
                            break
                        else:
                            print(f"Could open camera {idx} but couldn't read frame")
                            cap.release()
                            cap = None
                    else:
                        print(f"Failed to open camera at index {idx}")
                except Exception as e:
                    print(f"Error trying camera {idx}: {e}")
                    if cap and cap.isOpened():
                        cap.release()
                    cap = None
            
        if cap is None or not cap.isOpened():
            print("Error: Could not open any webcam")
            return
            
        # Force webcam properties
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        
        print(f"Camera properties:")
        print(f"  Resolution: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
        print(f"  FPS: {cap.get(cv2.CAP_PROP_FPS)}")

        while True:
            frame = await asyncio.to_thread(self._get_frame, cap)
            if frame is None:
                break

            await asyncio.sleep(1.0)

            await self.out_queue.put(frame)

        # Release the VideoCapture object
        cap.release()

    def _get_screen(self):
        sct = mss.mss()
        monitor = sct.monitors[0]

        i = sct.grab(monitor)

        mime_type = "image/jpeg"
        image_bytes = mss.tools.to_png(i.rgb, i.size)
        img = PIL.Image.open(io.BytesIO(image_bytes))

        image_io = io.BytesIO()
        img.save(image_io, format="jpeg")
        image_io.seek(0)

        image_bytes = image_io.read()
        return {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode()}

    async def get_screen(self):

        while True:
            frame = await asyncio.to_thread(self._get_screen)
            if frame is None:
                break

            await asyncio.sleep(1.0)

            await self.out_queue.put(frame)

    async def send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send(input=msg)

    async def listen_audio(self):
        mic_info = pya.get_default_input_device_info()
        self.audio_stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=SEND_SAMPLE_RATE,
            input=True,
            input_device_index=mic_info["index"],
            frames_per_buffer=CHUNK_SIZE,
        )
        if __debug__:
            kwargs = {"exception_on_overflow": False}
        else:
            kwargs = {}
        while True:
            data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **kwargs)
            await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})

    async def receive_audio(self):
        "Background task to reads from the websocket and write pcm chunks to the output queue"
        while True:
            turn = self.session.receive()
            async for response in turn:
                if data := response.data:
                    self.audio_in_queue.put_nowait(data)
                    continue
                if text := response.text:
                    print(text, end="")

            # If you interrupt the model, it sends a turn_complete.
            # For interruptions to work, we need to stop playback.
            # So empty out the audio queue because it may have loaded
            # much more audio than has played yet.
            while not self.audio_in_queue.empty():
                self.audio_in_queue.get_nowait()

    async def play_audio(self):
        stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE,
            output=True,
        )
        while True:
            bytestream = await self.audio_in_queue.get()
            await asyncio.to_thread(stream.write, bytestream)

    async def run(self):
        try:
            async with (
                client.aio.live.connect(model=MODEL, config=CONFIG) as session,
                asyncio.TaskGroup() as tg,
            ):
                self.session = session

                self.audio_in_queue = asyncio.Queue()
                self.out_queue = asyncio.Queue(maxsize=5)

                send_text_task = tg.create_task(self.send_text())
                tg.create_task(self.send_realtime())
                tg.create_task(self.listen_audio())
                if self.video_mode == "camera":
                    tg.create_task(self.get_frames())
                elif self.video_mode == "screen":
                    tg.create_task(self.get_screen())

                tg.create_task(self.receive_audio())
                tg.create_task(self.play_audio())

                await send_text_task
                raise asyncio.CancelledError("User requested exit")

        except asyncio.CancelledError:
            pass
        except ExceptionGroup as EG:
            self.audio_stream.close()
            traceback.print_exception(EG)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        type=str,
        default=DEFAULT_MODE,
        help="pixels to stream from",
        choices=["camera", "screen", "none"],
    )
    parser.add_argument(
        "--camera-index",
        type=int,
        default=0,
        help="index of the camera to use",
    )
    parser.add_argument(
        "--list-cameras",
        action="store_true",
        help="list available cameras and exit",
    )
    parser.add_argument(
        "--test-camera",
        action="store_true",
        help="test camera access and exit",
    )
    parser.add_argument(
        "--disable-android",
        action="store_true",
        help="explicitly disable Android ADB connections",
    )
    args = parser.parse_args()
    
    # Disable Android connections if requested
    if args.disable_android:
        os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'
        os.environ['OPENCV_VIDEOIO_PRIORITY_GSTREAMER'] = '0'
    
    if args.list_cameras:
        print("Searching for available cameras...")
        cameras = list_available_cameras()
        if cameras:
            print("Available cameras:")
            for idx in cameras:
                print(f"  Camera index {idx}")
            print(f"\nUse --camera-index to select a specific camera (e.g., --camera-index {cameras[0]})")
        else:
            print("No cameras found")
        sys.exit(0)
    
    if args.test_camera:
        success = test_camera_access(args.camera_index)
        if success:
            print(f"\nCamera test successful. Use this camera with: --camera-index {args.camera_index}")
        else:
            print("\nCamera test failed. Try a different camera index or check your webcam connection.")
        sys.exit(0)
        
    main = AudioLoop(video_mode=args.mode, camera_index=args.camera_index)
    asyncio.run(main.run())