"""🎥 YouTube Summary - Video Content Analyzer

This module provides functionality to analyze and summarize YouTube videos using AI.
It extracts key points, creates timestamps, and provides detailed summaries of video content.

Dependencies: 
    pip install youtube_transcript_api agno

Example usage:
    from youtube import YouTubeSummaryAgent
    
    # Create an agent
    youtube_agent = YouTubeSummaryAgent()
    
    # Get a summary of a YouTube video
    summary = youtube_agent.generate_video_summary("https://www.youtube.com/watch?v=example")
    
    # Use the summary in your UI
    print(summary)  # or st.markdown(summary) for Streamlit
"""

from textwrap import dedent
from typing import Optional
from pathlib import Path

from agno.agent import Agent, RunResponse, AgentMemory, Message
from agno.models.google import Gemini
from agno.tools.youtube import YouTubeTools
from agno.storage.agent.sqlite import SqliteAgentStorage
import logging

# Set up logging
logger = logging.getLogger(__name__)

class YouTubeSummaryAgent:
    def __init__(self, session_id=None, session_name=None):
        """Initialize a YouTube summary agent with memory and storage capabilities"""
        self.model = Gemini(id="gemini-2.0-flash-exp")
        self.tools = [YouTubeTools()]
        self.session_id = session_id
        self.session_name = session_name
        self.storage = SqliteAgentStorage(
            table_name="youtube_sessions",
            db_file=str(Path(__file__).parent / "chat_storage.db")
        )
        self.memory = AgentMemory(
            create_session_summary=False,
            update_session_summary_after_run=False,
        )
        
    def create_agent(self) -> Agent:
        """Create and return a configured YouTube summary agent"""
        agent = Agent(
            model=self.model,
            tools=self.tools,
            storage=self.storage,
            memory=self.memory,
            session_id=self.session_id,
            session_name=self.session_name,
            description=dedent("""\
                You are an expert YouTube content analyst with a keen eye for detail! 🎓
                Your expertise encompasses:
                
                - Video content analysis and summarization
                - Key point extraction and organization
                - Timestamp creation and organization
                - Topic identification and categorization
                - Technical explanation simplification
                - Educational content breakdown
                - Visual content description
                - Narrative structure analysis
            """),
            instructions=dedent("""\
                Analyze YouTube videos to provide helpful summaries that include:
                
                - A brief overview of the video content and purpose
                - Key timestamps for important moments in the video
                - Main points and concepts covered in the video
                - Important takeaways or conclusions
                
                Present your analysis in a conversational, helpful manner. Include timestamps in [HH:MM:SS] format 
                when referencing specific parts of the video. Make your summary easy to read and navigate.
                
                Respond in a natural, conversational style as if you're having a chat with the user.
            """),
            markdown=True,
            show_tool_calls=True,
        )
        
        # Load existing session if session_id provided
        if self.session_id:
            agent.load_session()
            logger.debug(f"Loaded YouTube session {self.session_id}")
            
        return agent
    
    def generate_video_summary(self, video_url: str, stream=False) -> RunResponse:
        """Generate a summary of a YouTube video based on the URL"""
        agent = self.create_agent()
        
        # Construct a prompt that asks for a comprehensive video analysis
        prompt = f"Analyze this YouTube video and provide a detailed summary with timestamps and key points: {video_url}"
        
        # Run the agent with the prompt
        response = agent.run(prompt, stream=stream)
        
        # Save the session
        agent.write_to_storage()
        
        return response


def create_youtube_summary(video_url: str) -> str:
    """Creates a detailed summary of a YouTube video with timestamps and key points.
    
    Args:
        video_url: The URL of the YouTube video to analyze
        
    Returns:
        str: Formatted video summary in markdown format, ready for UI display
    """
    youtube_agent = YouTubeSummaryAgent()
    response = youtube_agent.generate_video_summary(video_url, stream=False)
    return response.content


if __name__ == "__main__":
    # Example usage
    summary = create_youtube_summary(
        "https://www.youtube.com/watch?v=izHDm4Vf3lQ"
    )
    # Print the summary (in a real UI, you would use the summary string differently)
    print(summary) 