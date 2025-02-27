"""🔍 Research Function - AI-Powered Research Assistant

This module provides a function to create detailed research reports using AI and web search capabilities.
It combines web search with professional writing skills to deliver well-structured articles on any topic.

Dependencies: 
    pip install openai duckduckgo-search newspaper4k lxml_html_clean agno

Example usage:
    from research import create_research_report
    
    # Get the report as a string
    report = create_research_report("Impact of AI on healthcare delivery")
    
    # Use the report in your UI
    print(report)  # or st.markdown(report) for Streamlit
"""

from textwrap import dedent
from typing import Optional
from pathlib import Path

from agno.agent import Agent, RunResponse, AgentMemory, Message
from agno.models.google import Gemini
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.newspaper4k import Newspaper4kTools
from agno.storage.agent.sqlite import SqliteAgentStorage


class ResearchAgent:
    def __init__(self, session_id=None, session_name=None):
        """Initialize a research agent with memory and storage capabilities"""
        self.model = Gemini(id="gemini-2.0-flash-exp")
        self.tools = [DuckDuckGoTools(), Newspaper4kTools()]
        self.session_id = session_id
        self.session_name = session_name
        self.storage = SqliteAgentStorage(
            table_name="research_sessions",
            db_file=str(Path(__file__).parent / "chat_storage.db")
        )
        self.memory = AgentMemory(
            create_session_summary=False,
            update_session_summary_after_run=False,
        )
        
    def create_agent(self) -> Agent:
        """Create and return a configured research agent"""
        agent = Agent(
            model=self.model,
            tools=self.tools,
            storage=self.storage,
            memory=self.memory,
            session_id=self.session_id,
            session_name=self.session_name,
            description=dedent("""\
                You are an elite investigative journalist with decades of experience at the New York Times.
                Your expertise encompasses: 📰

                - Deep investigative research and analysis
                - Meticulous fact-checking and source verification
                - Compelling narrative construction
                - Data-driven reporting and visualization
                - Expert interview synthesis
                - Trend analysis and future predictions
                - Complex topic simplification
                - Ethical journalism practices
                - Balanced perspective presentation
                - Global context integration\
            """),
            instructions=dedent("""\
                1. Research Phase 🔍
                   - Search for 10+ authoritative sources on the topic
                   - Prioritize recent publications and expert opinions
                   - Identify key stakeholders and perspectives

                2. Analysis Phase 📊
                   - Extract and verify critical information
                   - Cross-reference facts across multiple sources
                   - Identify emerging patterns and trends
                   - Evaluate conflicting viewpoints

                3. Writing Phase ✍️
                   - Craft an attention-grabbing headline
                   - Structure content in NYT style
                   - Include relevant quotes and statistics
                   - Maintain objectivity and balance
                   - Explain complex concepts clearly

                4. Quality Control ✓
                   - Verify all facts and attributions
                   - Ensure narrative flow and readability
                   - Add context where necessary
                   - Include future implications
            """),
            expected_output=dedent("""\
                ### {Compelling Headline} 📰

                ### Executive Summary
                {Concise overview of key findings and significance}

                ### Background & Context
                {Historical context and importance}
                {Current landscape overview}

                ### Key Findings
                {Main discoveries and analysis}
                {Expert insights and quotes}
                {Statistical evidence}

                ### Impact Analysis
                {Current implications}
                {Stakeholder perspectives}
                {Industry/societal effects}

                ### Future Outlook
                {Emerging trends}
                {Expert predictions}
                {Potential challenges and opportunities}

                ### Expert Insights
                {Notable quotes and analysis from industry leaders}
                {Contrasting viewpoints}

                ### Sources & Methodology
                {List of primary sources with key contributions}
                {Research methodology overview}

                ---
                Research conducted by AI Investigative Journalist
                New York Times Style Report
                Published: {current_date}
                Last Updated: {current_time}\
            """),
            markdown=True,
            show_tool_calls=True,
            add_datetime_to_instructions=True,
        )
        
        # Load existing session if session_id provided
        if self.session_id:
            agent.load_session()
            
        return agent
        
    def generate_research_report(self, query: str, stream=False):
        """Generate a research report based on the query"""
        agent = self.create_agent()
        
        # Check query size to prevent payload issues
        query_size = len(query.encode('utf-8'))
        if query_size > 10 * 1024 * 1024:  # 10MB limit for query
            print(f"WARNING: Query size ({query_size / 1024 / 1024:.2f} MB) exceeds 10MB limit")
            # Truncate the query if it's too large
            query = query[:5 * 1024 * 1024].decode('utf-8', errors='ignore')  # Truncate to 5MB
            print(f"Query truncated to {len(query.encode('utf-8')) / 1024 / 1024:.2f} MB")
        
        response = agent.run(query, stream=stream)
        agent.write_to_storage()
        return response


def create_research_report(query: str) -> str:
    """Creates a detailed research report on the given query using AI and web search capabilities.
    
    Args:
        query: The research topic or question to investigate
        
    Returns:
        str: Formatted research report in markdown format, ready for UI display
    """
    research_agent = ResearchAgent()
    response = research_agent.generate_research_report(query, stream=False)
    return response.content


if __name__ == "__main__":
    # Example usage
    report = create_research_report(
        "Research the evolution of digital privacy and data protection measures"
    )
    # Print the report (in a real UI, you would use the report string differently)
    print(report)