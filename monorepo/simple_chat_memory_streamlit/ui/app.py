"""
Streamlit UI implementation for the chatbot.
"""

import streamlit as st
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from chatbot.logic import ChatbotManager

class ChatbotUI:
    def __init__(self):
        self.manager = ChatbotManager()
    
    def render_session_selector(self) -> dict:
        """Render session selection UI and return selected session info"""
        st.sidebar.title("Session Management")
        
        # Get available sessions
        sessions = self.manager.list_sessions()
        
        # Create session options
        session_options = ["New Session"] + [
            f"{s['name']} ({s['session_id']})" 
            for s in sessions
        ]
        
        # Show session selector
        selected_option = st.sidebar.selectbox(
            "Choose a session",
            session_options,
            key="session_selector"
        )
        
        # Handle session selection
        if selected_option == "New Session":
            session_name = st.sidebar.text_input("Enter a name for the new session", "", key="new_session_name")
            if session_name.strip():
                return self.manager.create_session(session_name.strip())
            st.sidebar.warning("Please enter a session name")
            st.stop()
        else:
            # Extract session_id from the selected option
            session_id = selected_option.split("(")[-1].rstrip(")")
            return self.manager.get_session(session_id)
    
    def render_chat(self, session: dict):
        """Render chat interface for the given session"""
        agent = session["agent"]
        
        # Display messages from agent memory
        if agent.memory and agent.memory.messages:
            for msg in agent.memory.messages:
                with st.chat_message("user" if msg.role == "user" else "assistant"):
                    st.markdown(msg.content)
        
        # Chat input
        if prompt := st.chat_input("Type your message here..."):
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Get and display bot response
            with st.chat_message("assistant"):
                response = agent.run(prompt)
                st.markdown(response.content)
            
            # Manage context after each interaction
            self.manager.manage_context(agent) 