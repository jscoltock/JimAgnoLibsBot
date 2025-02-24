"""
Streamlit UI implementation for the chatbot.
"""

import streamlit as st
import sys
from pathlib import Path
import os
import tempfile
import json
sys.path.append(str(Path(__file__).parent.parent))
from chatbot.logic import ChatbotManager
from agno.media import Audio, Image, Video
import logging

# Create a temp directory for video files
TEMP_VIDEO_DIR = Path(tempfile.gettempdir()) / "agno_videos"
TEMP_VIDEO_DIR.mkdir(exist_ok=True)

logger = logging.getLogger(__name__)

class ChatbotUI:
    def __init__(self):
        self.manager = ChatbotManager()
        self.initialize_session_state()
        
    @staticmethod
    def safe_decode_text(content, filename):
        """Helper function to safely decode text content"""
        encodings_to_try = ['utf-8', 'utf-16', 'ascii', 'iso-8859-1', 'cp1252']
        for encoding in encodings_to_try:
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        # If all encodings fail, use utf-8 with error handling
        return content.decode('utf-8', errors='replace')

    @staticmethod
    def safe_read_text_file(filepath):
        """Helper function to safely read text files"""
        encodings_to_try = ['utf-8', 'utf-16', 'ascii', 'iso-8859-1', 'cp1252']
        for encoding in encodings_to_try:
            try:
                with open(filepath, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        # If all encodings fail, use utf-8 with error handling
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
        
    def initialize_session_state(self):
        """Initialize session state variables"""
        if "uploaded_files" not in st.session_state:
            st.session_state.uploaded_files = []
        if "last_upload_id" not in st.session_state:
            st.session_state.last_upload_id = None
        if "temp_video_paths" not in st.session_state:
            st.session_state.temp_video_paths = []
        if "media_refs" not in st.session_state:
            st.session_state.media_refs = []
            
    def _save_last_session(self, session_id: str):
        """Save the last used session ID to a file"""
        try:
            with open("last_session.txt", "w") as f:
                f.write(session_id if session_id else "")
        except Exception:
            # Silently fail if we can't write the file
            pass
            
    def _load_last_session(self) -> str:
        """Load the last used session ID from file"""
        try:
            if not os.path.exists("last_session.txt"):
                return None
            with open("last_session.txt", "r") as f:
                session_id = f.read().strip()
                return session_id if session_id else None
        except Exception:
            return None
        
    @staticmethod
    def handle_file_upload():
        """Callback to handle file upload changes"""
        # Clear existing files first
        st.session_state.uploaded_files = []
        st.session_state.media_refs = []
        
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
        elif extension in ['.txt']:
            return 'text'
        return None
    
    def get_media_objects(self):
        """Convert uploaded files to Agno media objects"""
        media_objects = {
            'images': [],
            'videos': [],
            'audio': [],
            'media_refs': []  # Store references for persistence
        }
        
        # Clean up old temp video files
        for path in st.session_state.temp_video_paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
        st.session_state.temp_video_paths = []
        
        # Store and process each file
        for file in st.session_state.uploaded_files:
            # Store media file and get reference
            media_ref = self.manager.media_manager.store_media(
                st.session_state.current_session_id or 'temp', 
                file
            )
            media_objects['media_refs'].append(media_ref)
            
            # Get the full path for the stored file
            stored_path = self.manager.media_manager.get_media_path(media_ref['stored_path'])
            
            # Create appropriate media object
            if file['type'] == 'image':
                media_objects['images'].append(Image(filepath=str(stored_path)))
            elif file['type'] == 'video':
                media_objects['videos'].append(Video(filepath=str(stored_path)))
            elif file['type'] == 'audio':
                media_objects['audio'].append(Audio(filepath=str(stored_path)))
                
        # Save media references to session state
        st.session_state.media_refs = media_objects['media_refs']
        return media_objects
    
    def render_session_selector(self) -> tuple[str, str]:
        """Render session selection UI and return selected session info"""
        st.sidebar.title("Session Management")
        
        # File uploader
        st.sidebar.markdown("---")
        st.sidebar.subheader("Upload Files")
        
        # File uploader with callback
        _ = st.sidebar.file_uploader(
            "Choose files",
            type=['png', 'jpg', 'jpeg', 'mp4', 'avi', '.mov', 'mp3', 'wav', 'txt'],
            accept_multiple_files=True,
            key="file_uploader",
            on_change=ChatbotUI.handle_file_upload
        )
        
        # Get available sessions
        existing_sessions = self.manager.list_sessions()
        
        # Create session options
        session_options = ["New Session"]
        session_id_to_name = {}
        if existing_sessions:
            for session in existing_sessions:
                name = session.session_data.get("session_name", "Unnamed") if session.session_data else "Unnamed"
                option = f"{name} ({session.session_id})"
                session_options.append(option)
                session_id_to_name[session.session_id] = name
        
        # Load last session
        last_session_id = self._load_last_session()
        default_index = 0
        
        # Find the index of the last session if it exists
        if last_session_id and last_session_id in session_id_to_name:
            last_session_name = session_id_to_name[last_session_id]
            last_session_option = f"{last_session_name} ({last_session_id})"
            if last_session_option in session_options:
                default_index = session_options.index(last_session_option)
        
        # Create columns for session selector and delete button
        col1, col2 = st.sidebar.columns([3, 1])
        
        # Show session selector in first column
        with col1:
            selected_option = st.selectbox(
                "Choose a session",
                session_options,
                index=default_index,
                key="session_selector"
            )
        
        # Handle session selection
        if selected_option == "New Session":
            session_name = st.sidebar.text_input("Enter a name for the new session", "", key="new_session_name")
            if session_name.strip():
                if "last_session" not in st.session_state or st.session_state.last_session != "new":
                    st.session_state.last_session = "new"
                    self._save_last_session("")  # Clear last session when creating new
                    st.rerun()
                return None, session_name.strip()
            st.sidebar.warning("Please enter a session name")
            st.stop()
        else:
            session_id = selected_option.split("(")[-1].rstrip(")")
            session_name = selected_option.split(" (")[0]
            
            # Show delete button in second column when a session is selected
            with col2:
                st.write("")  # Add some spacing to align with selectbox
                if st.button("🗑️", help="Delete this session", type="secondary", key="delete_button"):
                    # Show confirmation dialog
                    st.session_state.show_delete_confirm = True
                    
            # Handle delete confirmation
            if st.session_state.get('show_delete_confirm', False):
                with st.sidebar.expander("⚠️ Confirm Deletion", expanded=True):
                    st.warning(f"Are you sure you want to delete session '{session_name}'?")
                    st.write("This action cannot be undone.")
                    col3, col4 = st.columns([1, 1])
                    with col3:
                        if st.button("Yes, Delete", type="primary", key="confirm_delete"):
                            try:
                                # Delete the session
                                self.manager.delete_session(session_id)
                                st.success("Session deleted successfully!")
                                # Clear session state
                                st.session_state.current_session_id = None
                                st.session_state.agent = None
                                st.session_state.last_session = None
                                # Clear the last session file
                                self._save_last_session("")
                                st.session_state.show_delete_confirm = False
                                # Force reload to show updated session list
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error deleting session: {str(e)}")
                    with col4:
                        if st.button("Cancel", type="secondary", key="cancel_delete"):
                            st.session_state.show_delete_confirm = False
                            st.rerun()
            
            if "last_session" not in st.session_state or st.session_state.last_session != session_id:
                st.session_state.last_session = session_id
                self._save_last_session(session_id)  # Save the selected session
                st.rerun()
            
            return session_id, session_name
    
    def render_chat(self, agent):
        """Render chat interface for the given agent"""
        if not agent:
            return
            
        # Display messages from agent memory
        if agent.memory and agent.memory.messages:
            for idx, msg in enumerate(agent.memory.messages):
                # Create columns for message and delete button
                msg_col, del_col = st.columns([20, 1])
                
                with msg_col:
                    with st.chat_message(msg.role):
                        st.markdown(msg.content)
                        # Display media if present in message metadata
                        if hasattr(msg, 'metadata') and msg.metadata and 'media_refs' in msg.metadata:
                            with st.expander("📎 View Media", expanded=False):
                                for media_ref in msg.metadata['media_refs']:
                                    stored_path = self.manager.media_manager.get_media_path(media_ref['stored_path'])
                                    st.write(f"**{media_ref['original_name']}**")
                                    if media_ref['type'] == 'image':
                                        st.image(str(stored_path))
                                    elif media_ref['type'] == 'video':
                                        st.video(str(stored_path))
                                    elif media_ref['type'] == 'audio':
                                        st.audio(str(stored_path))
                                    elif media_ref['type'] == 'text':
                                        try:
                                            text_content = self.safe_read_text_file(stored_path)
                                            st.text_area(
                                                "Text Content",
                                                value=text_content[:500] + '...' if len(text_content) > 500 else text_content,
                                                height=150,
                                                disabled=True
                                            )
                                        except Exception as e:
                                            st.error(f"Error displaying text content from {media_ref['original_name']}: {str(e)}")
                
                # Show delete button for the message
                with del_col:
                    if st.button("🗑️", key=f"delete_msg_{idx}", help="Delete this message"):
                        # Remove message from memory
                        agent.memory.messages.pop(idx)
                        # Update session in storage
                        agent.write_to_storage()
                        st.rerun()
        
        # Display uploaded files in a collapsible section right before chat input
        if st.session_state.uploaded_files:
            with st.expander("📎 Uploaded Files", expanded=True):
                cols = st.columns(min(3, len(st.session_state.uploaded_files)))
                for idx, file in enumerate(st.session_state.uploaded_files):
                    with cols[idx % 3]:
                        st.write(f"**{file['name']}**")
                        if file['type'] == 'image':
                            st.image(file['data'])
                        elif file['type'] == 'video':
                            st.video(file['data'])
                        elif file['type'] == 'audio':
                            st.audio(file['data'])
                        elif file['type'] == 'text':
                            try:
                                text_content = self.safe_decode_text(file['data'], file['name'])
                                st.text_area(
                                    "Text Content",
                                    value=text_content[:500] + '...' if len(text_content) > 500 else text_content,
                                    height=150,
                                    disabled=True
                                )
                            except Exception as e:
                                st.error(f"Error displaying text content from {file['name']}: {str(e)}")
        
        # Chat input
        if prompt := st.chat_input("Type your message here..."):
            # Process text files and append their content to the prompt
            text_contents = []
            for file in st.session_state.uploaded_files:
                if file['type'] == 'text':
                    try:
                        text_content = self.safe_decode_text(file['data'], file['name'])
                        text_contents.append(f"\nContent from {file['name']}:\n{text_content}")
                    except Exception as e:
                        st.error(f"Error processing text content from {file['name']}: {str(e)}")
            
            if text_contents:
                prompt = prompt + '\n' + '\n'.join(text_contents)
            
            # Get media objects for the query
            media_objects = self.get_media_objects()
            
            # Log conversation state before new message
            self.manager._log_conversation_state(agent, "Before new message")
            
            # Display user message with media
            with st.chat_message("user"):
                st.markdown(prompt)
                # Display media files
                if media_objects['media_refs']:
                    with st.expander("📎 View Media", expanded=True):
                        for media_ref in media_objects['media_refs']:
                            stored_path = self.manager.media_manager.get_media_path(media_ref['stored_path'])
                            st.write(f"**{media_ref['original_name']}**")
                            if media_ref['type'] == 'image':
                                st.image(str(stored_path))
                            elif media_ref['type'] == 'video':
                                st.video(str(stored_path))
                            elif media_ref['type'] == 'audio':
                                st.audio(str(stored_path))
                            elif media_ref['type'] == 'text':
                                try:
                                    text_content = self.safe_read_text_file(stored_path)
                                    st.text_area(
                                        "Text Content",
                                        value=text_content[:500] + '...' if len(text_content) > 500 else text_content,
                                        height=150,
                                        disabled=True
                                    )
                                except Exception as e:
                                    st.error(f"Error displaying text content from {media_ref['original_name']}: {str(e)}")
            
            # Get and display bot response with streaming
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                full_response = ""
                
                # Add media references to message metadata
                metadata = {'media_refs': media_objects['media_refs']} if media_objects['media_refs'] else None
                
                # Log the message being sent to the model
                logger.debug("Sending message to model:")
                logger.debug(json.dumps({
                    'prompt': prompt,
                    'has_images': bool(media_objects['images']),
                    'has_videos': bool(media_objects['videos']),
                    'has_audio': bool(media_objects['audio']),
                    'has_media_refs': bool(media_objects['media_refs'])
                }, indent=2))
                
                # Stream the response with media objects
                for response in agent.run(
                    prompt,
                    stream=True,
                    images=media_objects['images'],
                    videos=media_objects['videos'],
                    audio=media_objects['audio'],
                    metadata=metadata  # Add metadata to the message
                ):
                    if response.content:
                        full_response += response.content
                        message_placeholder.markdown(full_response + "▌")
                message_placeholder.markdown(full_response)
                
                # Log conversation state after response
                self.manager._log_conversation_state(agent, "After model response")
            
            # Manage context after each interaction
            #self.manager.manage_context(agent) 