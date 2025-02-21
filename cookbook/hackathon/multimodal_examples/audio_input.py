from agno.agent import Agent
from agno.media import Audio
from agno.models.openai import OpenAIChat
from agno.models.google import Gemini

#url = "https://openaiassets.blob.core.windows.net/$web/API/docs/audio/alloy.wav"

file_path = r"C:\Users\jscol\OneDrive\Desktop\Projects\JimAgnoLibsBot\output.mp3"

agent = Agent(
    model=Gemini(id="gemini-2.0-flash-exp"),
    markdown=True,
)

if __name__ == "__main__":
    # agent.print_response(
    #     "What is in this audio?", audio=[Audio(url=url, format="wav")], stream=True
    #)

    agent.print_response(
        "what is in this audio?", audio=[Audio(filepath=file_path, format="mp3")], stream=True
        
        #"What is in this audio?", audio=[Audio(url=url, format="wav")], stream=True
    )
