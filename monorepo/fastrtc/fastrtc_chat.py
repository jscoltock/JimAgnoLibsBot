import os

from fastrtc import (ReplyOnPause, Stream, get_stt_model, get_tts_model)
from openai import OpenAI

sambanova_client = OpenAI(
    #api_key=os.getenv("f024cf57-77fd-487f-8b0c-7717fb4b5cec"), base_url="https://api.sambanova.ai/v1"
    api_key="f024cf57-77fd-487f-8b0c-7717fb4b5cec", base_url="https://api.sambanova.ai/v1"
)
stt_model = get_stt_model()
tts_model = get_tts_model()

def echo(audio):
    prompt = stt_model.stt(audio)
    response = sambanova_client.chat.completions.create(
        model="Meta-Llama-3.2-3B-Instruct",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
    )
    prompt = response.choices[0].message.content
    for audio_chunk in tts_model.stream_tts_sync(prompt):
        yield audio_chunk

stream = Stream(ReplyOnPause(echo), modality="audio", mode="send-receive")
stream.ui.launch()
