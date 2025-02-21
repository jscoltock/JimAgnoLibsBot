from pathlib import Path
from agno.agent import Agent
from agno.media import Audio
from agno.models.google import Gemini

audio_path = r"C:\Users\jscol\OneDrive\Desktop\Projects\JimAgnoLibsBot\output.mp3"

model = Gemini(id="gemini-2.0-flash-exp")
agent = Agent(
    model=model,
    markdown=True,
)

answer = agent.run(
    "Tell me about this audio",
    audio=[Audio(filepath=audio_path)],
    stream=False,
)

print(answer.content)
