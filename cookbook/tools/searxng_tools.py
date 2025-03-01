from agno.agent import Agent
from agno.tools.searxng import Searxng

# Initialize Searxng with your Searxng instance URL
searxng = Searxng(
    host="http://localhost:4000",
    engines=[],
    fixed_max_results=5,
    news=True,
    science=True,
)

# Create an agent with Searxng
agent = Agent(tools=[searxng])

# Example: Ask the agent to search using Searxng
agent.print_response("""
Please search for information about artificial intelligence 
and summarize the key points from the top results
""")
