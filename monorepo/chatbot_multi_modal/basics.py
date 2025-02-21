from pathlib import Path
from agno.agent import Agent
from agno.media import Audio
from agno.media import Image
from agno.media import Video
from agno.models.google import Gemini

model = Gemini(id="gemini-2.0-flash-exp")
agent = Agent(
    model=model,
    markdown=True,
)

audio_path = r"C:\Users\jscol\OneDrive\Desktop\Projects\JimAgnoLibsBot\output.mp3"

answer = agent.run(
    "Tell me about this audio",
    audio=[Audio(filepath=audio_path)],
    stream=False,
)
print(answer.content)
print("--------------------------------")

image_path = r"C:\Users\jscol\OneDrive\Desktop\racecars\iStock-157310689.jpg"

answer = agent.run(
    "describe this image in detail",
    images=[Image(filepath=image_path)],
    stream=False,
)
print(answer.content)
print("--------------------------------")
video_path = r"C:\Users\jscol\OneDrive\Desktop\test55.mp4"
answer = agent.run(
    "What is happening in this video?",
    videos=[Video(filepath=video_path)],
    stream=False,
)
print(answer.content)
print("--------------------------------")

