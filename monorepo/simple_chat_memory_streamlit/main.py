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
    if "current_session" not in st.session_state:
        st.session_state.current_session = None
    
    # Handle session selection
    session = ui.render_session_selector()
    if session:
        st.session_state.current_session = session
        
        # Display current session info
        st.sidebar.markdown("---")
        st.sidebar.markdown(f"**Current Session:** {session['name']}")
        
        # Render chat interface
        ui.render_chat(session)

if __name__ == "__main__":
    main() 