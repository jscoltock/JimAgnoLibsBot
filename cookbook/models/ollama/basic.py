from agno.agent import Agent, RunResponse  # noqa
from agno.models.ollama import Ollama
import os

os.environ["OLLAMA_HOST"] = "http://localhost:11434"

agent = Agent(model=Ollama(id="gemma3:12b"), markdown=True)

# Get the response in a variable
# run: RunResponse = agent.run("Share a 2 sentence horror story")
# print(run.content)

# Print the response in the terminal
agent.print_response("Share a 2 sentence horror story")
