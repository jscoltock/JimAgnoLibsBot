"""
Core chatbot logic handling agent creation, storage, and context management.
"""

from agno.agent import Agent, AgentMemory
from agno.models.google import Gemini
from agno.storage.agent.sqlite import SqliteAgentStorage
from agno.memory.summarizer import MemorySummarizer
from pathlib import Path
from .media_manager import MediaManager

class ChatbotManager:
    def __init__(self):
        self.storage = self._init_storage()
        self.media_manager = MediaManager()
        
    def _init_storage(self):
        """Initialize and return agent storage for session management"""
        return SqliteAgentStorage(
            table_name="chat_sessions",
            db_file=str(Path(__file__).parent.parent / "chat_storage.db")
        )
    
    def create_agent(self, session_id: str = None, session_name: str = None) -> Agent:
        """Create and return a configured chatbot agent"""
        memory = AgentMemory(
            create_session_summary=True,
            update_session_summary_after_run=False,
        )
        
        agent = Agent(
            model=Gemini(id="gemini-2.0-flash-exp"),
            storage=self.storage,
            memory=memory,
            session_id=session_id,
            session_name=session_name,
            add_history_to_messages=True,
            description="You are a helpful assistant that always responds in a polite, upbeat and positive manner.",
            markdown=True,
        )
        
        # Load existing session data if session_id is provided
        if session_id:
            agent.load_session()
            
        return agent
    
    def list_sessions(self) -> list:
        """Get all available sessions"""
        return self.storage.get_all_sessions()
    
    def delete_session(self, session_id: str) -> None:
        """Delete a session and its associated media files"""
        # Delete media files first
        self.media_manager.cleanup_session(session_id)
        # Delete session from storage
        if self.storage:
            self.storage.delete_session(session_id)
    
    def manage_context(self, agent: Agent) -> None:
        """Check token usage and manage context window by summarizing older messages if needed"""
        if not agent.memory or not agent.memory.messages:
            return
            
        total_tokens = sum(
            (msg.metrics.get('total_tokens', 0) if msg.metrics else 0)
            for msg in agent.memory.messages
        )
        
        if total_tokens > 800000:
            tokens_to_summarize = total_tokens // 10
            messages_to_summarize = []
            summarize_tokens = 0
            
            for msg in agent.memory.messages:
                msg_tokens = msg.metrics.get('total_tokens', 0) if msg.metrics else 0
                if summarize_tokens + msg_tokens <= tokens_to_summarize:
                    messages_to_summarize.append(msg)
                    summarize_tokens += msg_tokens
                else:
                    break
            
            if messages_to_summarize:
                message_pairs = []
                for i in range(0, len(messages_to_summarize)-1, 2):
                    if i+1 < len(messages_to_summarize):
                        message_pairs.append((messages_to_summarize[i], messages_to_summarize[i+1]))
                
                if agent.memory.summarizer is None:
                    agent.memory.summarizer = MemorySummarizer()
                
                summary = agent.memory.summarizer.run(message_pairs)
                if summary:
                    agent.memory.messages = agent.memory.messages[len(messages_to_summarize):]
                    agent.memory.summary = summary
                    
                    remaining_tokens = sum((msg.metrics.get('total_tokens', 0) if msg.metrics else 0) for msg in agent.memory.messages)
                    if remaining_tokens > 900000:
                        self.manage_context(agent) 