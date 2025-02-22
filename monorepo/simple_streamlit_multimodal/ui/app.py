"""
Streamlit UI implementation for the chatbot.
"""

import streamlit as st
import sys
from pathlib import Path
import os
import tempfile
sys.path.append(str(Path(__file__).parent.parent))
from chatbot.logic import ChatbotManager
from agno.media import Audio, Image, Video

# Create a temp directory for video files
TEMP_VIDEO_DIR = Path(tempfile.gettempdir()) / "agno_videos"
TEMP_VIDEO_DIR.mkdir(exist_ok=True)

class ChatbotUI:
    def __init__(self):
        self.manager = ChatbotManager()
        self.initialize_session_state()
        
    def initialize_session_state(self):
        """Initialize session state variables"""
        if "uploaded_files" not in st.session_state:
            st.session_state.uploaded_files = []
        if "last_upload_id" not in st.session_state:
            st.session_state.last_upload_id = None
        if "temp_video_paths" not in st.session_state:
            st.session_state.temp_video_paths = []
            
    @staticmethod
    def handle_file_upload():
        """Callback to handle file upload changes"""
        # Clear existing files first
        st.session_state.uploaded_files = []
        
        # Process new files if any
        if st.session_state.file_uploader:
            for file in st.session_state.file_uploader:
                file_type = ChatbotUI.get_file_type(file)
                if file_type:
                    file_data = {
                        'name': file.name,
                        'data': file.getvalue(),
                        'type': file_type
                    }
                    st.session_state.uploaded_files.append(file_data)
        
        # Force a rerun to update the UI
        st.rerun()
        
    @staticmethod
    def get_file_type(file):
        """Determine the type of uploaded file based on extension"""
        extension = Path(file.name).suffix.lower()
        if extension in ['.png', '.jpg', '.jpeg']:
            return 'image'
        elif extension in ['.mp4', '.avi', '.mov']:
            return 'video'
        elif extension in ['.mp3', '.wav']:
            return 'audio'
        return None
        
    def save_uploaded_file(self, uploaded_file):
        """Store uploaded file data in session state"""
        return {
            'name': uploaded_file.name,
            'data': uploaded_file.getvalue(),
            'type': self.get_file_type(uploaded_file)
        }
            
    def render_session_selector(self) -> tuple[str, str]:
        """Render session selection UI and return selected session info"""
        st.sidebar.title("Session Management")
        
        # File uploader
        st.sidebar.markdown("---")
        st.sidebar.subheader("Upload Files")
        
        # File uploader with callback
        _ = st.sidebar.file_uploader(
            "Choose files",
            type=['png', 'jpg', 'jpeg', 'mp4', 'avi', '.mov', 'mp3', 'wav'],
            accept_multiple_files=True,
            key="file_uploader",
            on_change=ChatbotUI.handle_file_upload
        )
        
        # Get available sessions
        existing_sessions = self.manager.list_sessions()
        
        # Create session options
        session_options = ["New Session"]
        if existing_sessions:
            for session in existing_sessions:
                name = session.session_data.get("session_name", "Unnamed") if session.session_data else "Unnamed"
                session_options.append(f"{name} ({session.session_id})")
        
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
                if "last_session" not in st.session_state or st.session_state.last_session != "new":
                    st.session_state.last_session = "new"
                    st.rerun()
                return None, session_name.strip()
            st.sidebar.warning("Please enter a session name")
            st.stop()
        else:
            session_id = selected_option.split("(")[-1].rstrip(")")
            session_name = selected_option.split(" (")[0]
            
            if "last_session" not in st.session_state or st.session_state.last_session != session_id:
                st.session_state.last_session = session_id
                st.rerun()
            
            return session_id, session_name
    
    def get_media_objects(self):
        """Convert uploaded files to Agno media objects"""
        media_objects = {
            'images': [],
            'videos': [],
            'audio': []
        }
        
        # Clean up old temp video files
        for path in st.session_state.temp_video_paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
        st.session_state.temp_video_paths = []
        
        for file in st.session_state.uploaded_files:
            if file['type'] == 'image':
                media_objects['images'].append(Image(content=file['data']))
            elif file['type'] == 'video':
                # Save video to temp file
                temp_path = TEMP_VIDEO_DIR / f"{hash(file['name'])}{Path(file['name']).suffix}"
                with open(temp_path, 'wb') as f:
                    f.write(file['data'])
                media_objects['videos'].append(Video(filepath=str(temp_path)))
                st.session_state.temp_video_paths.append(str(temp_path))
            elif file['type'] == 'audio':
                media_objects['audio'].append(Audio(content=file['data']))
                
        return media_objects
    
    def render_chat(self, agent):
        """Render chat interface for the given agent"""
        if not agent:
            return
            
        # Display messages from agent memory
        if agent.memory and agent.memory.messages:
            for msg in agent.memory.messages:
                with st.chat_message(msg.role):
                    st.markdown(msg.content)
        
        # Display uploaded files in a collapsible section right before chat input
        if st.session_state.uploaded_files:
            with st.expander("📎 Uploaded Files", expanded=True):
                cols = st.columns(min(3, len(st.session_state.uploaded_files)))
                for idx, file in enumerate(st.session_state.uploaded_files):
                    with cols[idx % 3]:
                        st.write(f"**{file['name']}**")
                        if file['type'] == 'image':
                            st.image(file['data'], use_container_width=True)
                        elif file['type'] == 'video':
                            st.video(file['data'])
                        elif file['type'] == 'audio':
                            st.audio(file['data'])
        
        # Chat input
        if prompt := st.chat_input("Type your message here..."):
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Get media objects for the query
            media_objects = self.get_media_objects()
            
            # Get and display bot response with streaming
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                full_response = ""
                # Stream the response with media objects
                for response in agent.run(
                    prompt,
                    stream=True,
                    images=media_objects['images'],
                    videos=media_objects['videos'],
                    audio=media_objects['audio']
                ):
                    if response.content:
                        full_response += response.content
                        message_placeholder.markdown(full_response + "▌")
                message_placeholder.markdown(full_response)
            
            # Manage context after each interaction
            self.manager.manage_context(agent) 