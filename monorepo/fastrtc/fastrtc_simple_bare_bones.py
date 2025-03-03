from fastrtc import Stream, ReplyOnPause
import numpy as np

def echo(audio):  # Removed type hints for the audio argument
    yield audio

stream = Stream(ReplyOnPause(echo), modality="audio", mode="send-receive")
stream.ui.launch()