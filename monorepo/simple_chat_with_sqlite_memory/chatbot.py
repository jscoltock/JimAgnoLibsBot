from agno.agent import Agent
from agno.models.google import Gemini
from agno.storage.agent.sqlite import SqliteAgentStorage
from pathlib import Path
import json
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
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
    
    return Agent(
        model=Gemini(id="gemini-2.0-flash-exp"),
        # Store chat history in SQLite
        storage=storage,
        # Resume last session if provided
        session_id=session_id,
        # Set session name if provided
        session_name=session_name,
        # Add chat history to messages
        add_history_to_messages=True,
        # Set to None for unlimited history (Gemini has 1M token context)
        num_history_responses=None,
        # Description creates a system prompt for the agent
        description="You are a helpful assistant that always responds in a polite, upbeat and positive manner.",
        # Enable markdown formatting
        markdown=True,
    )

console = Console()

# def print_chat_history(agent):
#     # -*- Print history
#     console.print(
#         Panel(
#             JSON(
#                 json.dumps(
#                     [
#                         m.model_dump(include={"role", "content"})
#                         for m in agent.memory.messages
#                     ]
#                 ),
#                 indent=4,
#             ),
#             title=f"Chat History for session_id: {agent.session_id}",
#             expand=True,
#         )
#     )

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
        print(f"Continuing session: {session_id}{name_display}\n")
    
    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() == 'quit':
            break
            
        response = agent.run(user_input)
        print(f"\nAssistant: {response.content}")

if __name__ == "__main__":
    chat() 