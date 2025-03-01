"""
Main entry point for the Streamlit chatbot application.
"""

import streamlit as st
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))
from ui.app import ChatbotUI

def main():
    st.title("Agno Chatbot")
    
    # Initialize UI
    ui = ChatbotUI()
    
    # Initialize session state
    if "current_session_id" not in st.session_state:
        st.session_state.current_session_id = None
    if "agent" not in st.session_state:
        st.session_state.agent = None
    if "last_session" not in st.session_state:
        st.session_state.last_session = None
    
    # Handle session selection
    session_id, session_name = ui.render_session_selector()
    
    # Check if session changed or agent needs initialization
    if (session_id != st.session_state.current_session_id) or (st.session_state.agent is None):
        st.session_state.current_session_id = session_id
        st.session_state.agent = ui.manager.create_agent(session_id, session_name)
        if session_id:
            st.session_state.last_session = session_id
        else:
            st.session_state.last_session = "new"
    
    # Display current session info
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**Current Session:** {session_name}")
    
    # Render chat interface
    ui.render_chat(st.session_state.agent)

if __name__ == "__main__":
    main() 