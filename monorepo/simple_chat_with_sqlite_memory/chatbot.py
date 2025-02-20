"""
This is a command-line chatbot application that uses Gemini (via agno) with persistent memory storage in SQLite. 
It allows users to create new chat sessions or continue existing ones, with each session's history stored in a SQLite database. 
The app includes a context management system that automatically summarizes older messages when approaching the token limit
 (800K tokens), ensuring continuous operation during long conversations. The chatbot maintains session summaries and 
 conversation history, making it possible to resume previous conversations while keeping track of discussed topics.
 
Key components:
Storage: SQLite for persistent session storage
Model: Gemini for chat responses
Memory: AgentMemory for conversation history and summarization
Session Management: Ability to create new or select existing chat sessions
Context Management: Automatic summarization of old messages when nearing token limits
"""

from agno.agent import Agent, AgentMemory
from agno.models.google import Gemini
from agno.storage.agent.sqlite import SqliteAgentStorage
from agno.memory.summarizer import MemorySummarizer  
from pathlib import Path
#from rich.console import Console
import typer

# Get the current directory
CURRENT_DIR = Path(__file__).parent.resolve()

def get_agent_storage():
    """Return agent storage for session management"""
    return SqliteAgentStorage(
        table_name="chat_sessions",
        db_file=str(CURRENT_DIR / "chat_storage.db")
    )

def create_agent(session_id: str = None, session_name: str = None):
    """Create and return a configured chatbot agent."""
    storage = get_agent_storage()
    
    memory = AgentMemory(
        create_session_summary=True,  # Enable summarization capability
        update_session_summary_after_run=False,  # We'll control this manually
    )
    
    return Agent(
        model=Gemini(id="gemini-2.0-flash-exp"),
        storage=storage,
        memory=memory,
        session_id=session_id,
        session_name=session_name,
        add_history_to_messages=True,
        description="You are a helpful assistant that always responds in a polite, upbeat and positive manner.",
        markdown=True,
    )

# TODO: console is used for rich output and formatting, but it's not used in the code.
#console = Console()

def handle_session_selection():
    """Handle session selection and return the selected session ID."""
    storage = get_agent_storage()
    
    new = typer.confirm("Do you want to start a new session?", default=True)
    if new:
        session_name = typer.prompt("Enter a name for this session", default="")
        return None, session_name
        
    existing_sessions = storage.get_all_sessions()
    if not existing_sessions:
        print("No existing sessions found. Starting a new session.")
        session_name = typer.prompt("Enter a name for this session", default="")
        return None, session_name
        
    print("\nExisting sessions:")
    for i, session in enumerate(existing_sessions, 1):
        name = session.session_data.get("session_name", "Unnamed") if session.session_data else "Unnamed"
        print(f"{i}. {name} ({session.session_id})")
        
    session_idx = typer.prompt(
        "Choose a session number to continue (or press Enter for most recent)",
        default=1,
    )
    
    try:
        selected_session = existing_sessions[int(session_idx) - 1]
        return selected_session.session_id, selected_session.session_data.get("session_name") if selected_session.session_data else None
    except (ValueError, IndexError):
        return existing_sessions[0].session_id, existing_sessions[0].session_data.get("session_name") if existing_sessions[0].session_data else None


def check_and_manage_context(agent: Agent) -> None:
    """Check token usage and manage context window by summarizing older messages if needed."""
    if not agent.memory or not agent.memory.messages:
        return
        
    # Calculate total tokens in current context
    total_tokens = sum(
        (msg.metrics.get('total_tokens', 0) if msg.metrics else 0)
        for msg in agent.memory.messages
    )
    
    # If we're approaching the 1M token context limit, summarize older messages
    if total_tokens > 800000:  # Start managing at 80% of context window
        print("\n=== Managing context window ===")
        print(f"Current token usage: {total_tokens}")
        
        # Calculate how many tokens to summarize (10% of total)
        tokens_to_summarize = total_tokens // 10
        
        # Find the oldest messages that make up ~10% of total tokens
        messages_to_summarize = []
        summarize_tokens = 0
        
        # Start from the oldest messages
        for msg in agent.memory.messages:
            msg_tokens = msg.metrics.get('total_tokens', 0) if msg.metrics else 0
            if summarize_tokens + msg_tokens <= tokens_to_summarize:
                messages_to_summarize.append(msg)
                summarize_tokens += msg_tokens
            else:
                break
        
        if messages_to_summarize:
            print(f"\nSummarizing {len(messages_to_summarize)} oldest messages ({summarize_tokens} tokens)")
            
            # Create message pairs from messages to summarize
            message_pairs = []
            for i in range(0, len(messages_to_summarize)-1, 2):
                if i+1 < len(messages_to_summarize):
                    message_pairs.append((messages_to_summarize[i], messages_to_summarize[i+1]))
            
            # Update the summary
            if agent.memory.summarizer is None:
                agent.memory.summarizer = MemorySummarizer()
            
            summary = agent.memory.summarizer.run(message_pairs)
            if summary:
                print("\nSummarized older messages:")
                print(f"Summary: {summary.summary}")
                if summary.topics:
                    print(f"Topics: {', '.join(summary.topics)}")
                
                # Keep all messages except the ones we just summarized
                agent.memory.messages = agent.memory.messages[len(messages_to_summarize):]
                agent.memory.summary = summary
                
                print(f"\nKept {len(agent.memory.messages)} more recent messages")
                print(f"New total tokens: {sum((msg.metrics.get('total_tokens', 0) if msg.metrics else 0) for msg in agent.memory.messages)}")
                print("===========================")
                
                # If we're still over 90% capacity after summarizing 10%, recursively call to summarize more
                remaining_tokens = sum((msg.metrics.get('total_tokens', 0) if msg.metrics else 0) for msg in agent.memory.messages)
                if remaining_tokens > 900000:  # If still over 90% capacity
                    print("\nStill close to context limit, summarizing more messages...")
                    check_and_manage_context(agent)  # Recursive call to summarize more if needed

def chat():
    session_id, session_name = handle_session_selection()
    agent = create_agent(session_id, session_name)
    
    print("Chatbot initialized! Type 'quit' to exit.")
    
    if session_id is None:
        session_id = agent.session_id
        if session_id is not None:
            name_display = f" ({session_name})" if session_name else ""
            print(f"Started new session: {session_id}{name_display}\n")
        else:
            print("Started new session\n")
    else:
        name_display = f" ({session_name})" if session_name else ""
        print(f"Continuing session: {session_id}{name_display}")
        if agent.memory.summary:
            print("\n=== Current Session Summary ===")
            print(f"Summary: {agent.memory.summary.summary}")
            if agent.memory.summary.topics:
                print(f"Topics: {', '.join(agent.memory.summary.topics)}")
            print("===========================\n")
    
    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() == 'quit':
            break
            
        response = agent.run(user_input)
        print(f"\nAssistant: {response.content}")
        
        # Check and manage context window after each interaction
        check_and_manage_context(agent)

if __name__ == "__main__":
    chat() 