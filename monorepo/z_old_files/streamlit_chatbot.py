"""
Streamlit UI for the agno chatbot. All core functionality remains unchanged from the CLI version.
The only modification is the UI layer which is handled by Streamlit.
"""

from agno.agent import Agent, AgentMemory
from agno.models.google import Gemini
from agno.storage.agent.sqlite import SqliteAgentStorage
from agno.memory.summarizer import MemorySummarizer
from pathlib import Path
import streamlit as st

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
        create_session_summary=True,
        update_session_summary_after_run=False,
    )
    
    agent = Agent(
        model=Gemini(id="gemini-2.0-flash-exp"),
        storage=storage,
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

def check_and_manage_context(agent: Agent) -> None:
    """Check token usage and manage context window by summarizing older messages if needed."""
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
                    check_and_manage_context(agent)

def handle_session_selection():
    """Handle session selection and return the selected session ID."""
    storage = get_agent_storage()
    existing_sessions = storage.get_all_sessions()
    
    st.sidebar.title("Session Management")
    
    # Add "New Session" option
    session_options = ["New Session"]
    
    # Add existing sessions to the options
    if existing_sessions:
        for session in existing_sessions:
            name = session.session_data.get("session_name", "Unnamed") if session.session_data else "Unnamed"
            session_options.append(f"{name} ({session.session_id})")
    
    selected_option = st.sidebar.selectbox(
        "Choose a session",
        session_options,
        key="session_selector"  # Unique key for the selectbox
    )
    
    if selected_option == "New Session":
        session_name = st.sidebar.text_input("Enter a name for the new session", "", key="new_session_name")
        if session_name.strip():
            return None, session_name.strip()
        st.sidebar.warning("Please enter a session name")
        st.stop()
    else:
        # Extract session_id from the selected option
        session_id = selected_option.split("(")[-1].rstrip(")")
        session_name = selected_option.split(" (")[0]
        return session_id, session_name

def main():
    st.title("Agno Chatbot")
    
    # Initialize session state variables
    if "current_session_id" not in st.session_state:
        st.session_state.current_session_id = None
    
    # Always show session selector
    session_id, session_name = handle_session_selection()
    
    # Check if session changed or agent needs initialization
    if (session_id != st.session_state.current_session_id) or ("agent" not in st.session_state):
        st.session_state.current_session_id = session_id
        st.session_state.agent = create_agent(session_id, session_name)
    
    # Display current session info
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**Current Session:** {session_name}")
    
    # Display messages directly from agent memory
    if st.session_state.agent.memory and st.session_state.agent.memory.messages:
        for msg in st.session_state.agent.memory.messages:
            with st.chat_message("user" if msg.role == "user" else "assistant"):
                st.markdown(msg.content)

    # Chat input
    if prompt := st.chat_input("Type your message here..."):
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get bot response
        with st.chat_message("assistant"):
            response = st.session_state.agent.run(prompt)
            st.markdown(response.content)

        # Manage context after each interaction
        check_and_manage_context(st.session_state.agent)

if __name__ == "__main__":
    main()