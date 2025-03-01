"""
Core chatbot logic handling agent creation, storage, and context management.
"""

from agno.agent import Agent, AgentMemory
from agno.models.google import Gemini
from agno.storage.agent.sqlite import SqliteAgentStorage
from agno.memory.summarizer import MemorySummarizer
from pathlib import Path
import logging
import sqlite3
import json
from .media_manager import MediaManager

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class ChatbotManager:
    def __init__(self):
        self.storage = self._init_storage()
        self.media_manager = MediaManager()
        self.db_path = Path(__file__).parent.parent / "chat_storage.db"
        self._init_media_metadata_table()
        
    def _init_storage(self):
        """Initialize and return agent storage for session management"""
        return SqliteAgentStorage(
            table_name="chat_sessions",
            db_file=str(Path(__file__).parent.parent / "chat_storage.db")
        )
    
    def _init_media_metadata_table(self):
        """Initialize the media metadata table"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS media_metadata (
                        session_id TEXT,
                        message_id TEXT,
                        metadata TEXT,
                        PRIMARY KEY (session_id, message_id)
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Error creating media metadata table: {str(e)}")
            
    def _save_media_metadata(self, session_id: str, message_id: str, metadata: dict):
        """Save media metadata to the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO media_metadata (session_id, message_id, metadata) VALUES (?, ?, ?)",
                    (session_id, message_id, json.dumps(metadata))
                )
                conn.commit()
                logger.debug(f"Saved metadata for session {session_id}, message {message_id}")
        except Exception as e:
            logger.error(f"Error saving media metadata: {str(e)}")
            
    def _load_media_metadata(self, session_id: str) -> dict:
        """Load media metadata for a session"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT message_id, metadata FROM media_metadata WHERE session_id = ?",
                    (session_id,)
                )
                metadata_dict = {}
                for message_id, metadata_json in cursor:
                    metadata_dict[message_id] = json.loads(metadata_json)
                logger.debug(f"Loaded metadata for session {session_id}: {metadata_dict}")
                return metadata_dict
        except Exception as e:
            logger.error(f"Error loading media metadata: {str(e)}")
            return {}
            
    def _log_conversation_state(self, agent: Agent, stage: str):
        """Log the current state of the conversation"""
        if not agent.memory or not agent.memory.messages:
            logger.debug(f"{stage} - No messages in memory")
            return
            
        messages = []
        for msg in agent.memory.messages:
            metadata = getattr(msg, 'metadata', {}) or {}
            msg_dict = {
                'role': msg.role,
                'content': msg.content[:100] + '...' if len(msg.content) > 100 else msg.content,
                'has_media': bool(metadata.get('media_refs', None))
            }
            messages.append(msg_dict)
            
        logger.debug(f"{stage} - Conversation state:")
        logger.debug(json.dumps(messages, indent=2))
    
    def create_agent(self, session_id: str = None, session_name: str = None) -> Agent:
        """Create and return a configured chatbot agent"""
        memory = AgentMemory(
            create_session_summary=False,
            update_session_summary_after_run=False,
        )
        
        agent = Agent(
            model=Gemini(id="gemini-2.0-flash-exp"),
            storage=self.storage,
            memory=memory,
            session_id=session_id,
            session_name=session_name,
            add_history_to_messages=True,
            num_history_responses=None,
            description="You are a helpful assistant that always responds in a polite, upbeat and positive manner.",
            markdown=True,
            debug_mode=True
        )
        
        # Load existing session if session_id provided
        if session_id:
            # Load the session first
            agent.load_session()
            logger.debug(f"Loaded session {session_id}")
            
            # Load media metadata from our table
            stored_metadata = self._load_media_metadata(session_id)
            logger.debug(f"Loaded media metadata from database: {stored_metadata}")
            
            # Restore metadata for each message
            if agent.memory and agent.memory.messages:
                for msg in agent.memory.messages:
                    # Skip system messages
                    if msg.role == 'system':
                        continue
                        
                    # Get stored metadata for this message
                    msg_id = f"{msg.role}_{agent.memory.messages.index(msg)}"
                    if msg_id in stored_metadata:
                        msg.metadata = stored_metadata[msg_id].copy()
                        logger.debug(f"Restored metadata for message {msg_id}: {msg.metadata}")
            
            self._log_conversation_state(agent, "After session load")
            
        return agent
    
    def save_message_metadata(self, agent: Agent, message_id: str, metadata: dict):
        """Save metadata for a specific message"""
        if agent.session_id:
            self._save_media_metadata(agent.session_id, message_id, metadata)
            logger.debug(f"Saved metadata for message {message_id} in session {agent.session_id}")
            
    def list_sessions(self) -> list:
        """Get all available sessions"""
        return self.storage.get_all_sessions()
    
    def delete_session(self, session_id: str) -> None:
        """Delete a session and its associated media files"""
        logger.debug(f"Starting deletion of session {session_id}")
        
        try:
            # Delete media files first
            logger.debug("Attempting to delete media files...")
            self.media_manager.cleanup_session(session_id)
            logger.debug("Media files deleted successfully")
            
            # Delete media metadata
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM media_metadata WHERE session_id = ?", (session_id,))
                conn.commit()
            logger.debug("Media metadata deleted successfully")
            
            # Delete session using Agno storage
            logger.debug("Attempting to delete session from database...")
            self.storage.delete_session(session_id=session_id)
            logger.debug("Session deleted from database successfully")
                
        except Exception as e:
            logger.error(f"Error during session deletion: {str(e)}", exc_info=True)
            raise
    
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