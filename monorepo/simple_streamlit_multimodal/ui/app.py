"""
Streamlit UI implementation for the chatbot.
"""

import streamlit as st
import sys
from pathlib import Path
import os
import tempfile
import json
import PyPDF2
from datetime import datetime
sys.path.append(str(Path(__file__).parent.parent.parent))
from js_utils.web_utils import summarize_web_search
sys.path.append(str(Path(__file__).parent.parent))
from chatbot.logic import ChatbotManager
from agno.media import Audio, Image, Video
from agno.agent import Message
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
    def extract_pdf_text(pdf_data):
        """Helper function to extract text from PDF data"""
        # Create a PDF reader object
        pdf_reader = PyPDF2.PdfReader(pdf_data)
        
        # Extract text from all pages
        text = []
        for page in pdf_reader.pages:
            text.append(page.extract_text())
            
        return '\n'.join(text)

    @staticmethod
    def safe_decode_text(content, filename):
        """Helper function to safely decode text content"""
        # Check if it's a PDF file
        if filename.lower().endswith('.pdf'):
            from io import BytesIO
            return ChatbotUI.extract_pdf_text(BytesIO(content))
            
        # Handle other text files
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

    @staticmethod
    def format_chat_message(content: str, max_preview_length: int = 500) -> tuple[str, str]:
        """Format chat message for display, returns (preview, full_content)"""
        # If content is short enough, return as is
        if len(content) <= max_preview_length:
            return content, content
            
        # Create preview by truncating at the last complete sentence within limit
        preview = content[:max_preview_length]
        last_sentence = max(
            preview.rfind('.'),
            preview.rfind('!'),
            preview.rfind('?')
        )
        if last_sentence > 0:
            preview = content[:last_sentence + 1]
        else:
            preview = content[:max_preview_length] + "..."
            
        return preview, content

    @staticmethod
    def has_non_text_media(media_refs: list) -> bool:
        """Check if there are any non-text media files in the references"""
        if not media_refs:
            return False
        return any(
            ref.get('type') in ['image', 'video', 'audio']
            for ref in media_refs
        )
        
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
        if "use_web_search" not in st.session_state:
            st.session_state.use_web_search = False
        if "message_metadata" not in st.session_state:
            st.session_state.message_metadata = {}
        if "current_media_refs" not in st.session_state:
            st.session_state.current_media_refs = None
        
    def _save_last_session(self, session_id: str):
        """Save the last used session ID to a file"""
        with open("last_session.txt", "w") as f:
            f.write(session_id if session_id else "")
            
    def _load_last_session(self) -> str:
        """Load the last used session ID from file"""
        if not os.path.exists("last_session.txt"):
            return None
        with open("last_session.txt", "r") as f:
            session_id = f.read().strip()
            return session_id if session_id else None
        
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
        elif extension in ['.txt', '.pdf']:  # Add PDF to text types
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
            if os.path.exists(path):
                os.remove(path)
        st.session_state.temp_video_paths = []
        
        # Store and process each file
        for file in st.session_state.uploaded_files:
            try:
                # Store media file and get reference
                media_ref = self.manager.media_manager.store_media(
                    st.session_state.current_session_id or 'temp', 
                    file
                )
                media_objects['media_refs'].append(media_ref)
                
                # Get the full path for the stored file
                stored_path = self.manager.media_manager.get_media_path(media_ref['stored_path'])
                
                # Create appropriate media object with error handling
                try:
                    if file['type'] == 'image':
                        media_objects['images'].append(Image(filepath=str(stored_path)))
                    elif file['type'] == 'video':
                        # Check video file size
                        file_size = os.path.getsize(stored_path)
                        max_size = 20 * 1024 * 1024  # 20MB limit for Gemini
                        
                        if file_size > max_size:
                            logger.warning(f"Video file too large ({file_size} bytes) for Gemini API. Max size is {max_size} bytes.")
                            st.warning(f"Video '{file['name']}' is too large for AI processing. The video will be displayed but not processed by the AI.")
                        else:
                            try:
                                video_obj = Video(filepath=str(stored_path))
                                media_objects['videos'].append(video_obj)
                            except Exception as e:
                                logger.error(f"Error creating video object: {str(e)}")
                                st.error(f"Error processing video '{file['name']}'. The video will be displayed but not processed by the AI.")
                    elif file['type'] == 'audio':
                        media_objects['audio'].append(Audio(filepath=str(stored_path)))
                except Exception as e:
                    logger.error(f"Error creating media object for {file['name']}: {str(e)}")
                    st.error(f"Error processing {file['type']} file '{file['name']}'. The file will be stored but may not be fully functional.")
                    
            except Exception as e:
                logger.error(f"Error storing media file {file['name']}: {str(e)}")
                st.error(f"Error uploading file '{file['name']}'. Please try again or use a different file.")
                continue
                
        # Save media references to session state
        st.session_state.media_refs = media_objects['media_refs']
        return media_objects
    
    def render_session_selector(self) -> tuple[str, str]:
        """Render session selection UI and return selected session info"""
        # Get available sessions
        existing_sessions = self.manager.list_sessions()
        
        # Create session options and maintain internal mapping
        session_options = ["➕ New Session"]
        session_id_map = {}  # Map display names to session IDs
        if existing_sessions:
            for session in existing_sessions:
                name = session.session_data.get("session_name", "Unnamed")
                session_id_map[name] = session.session_id
                session_options.append(name)
        
        # Load last session
        last_session_id = self._load_last_session()
        default_index = 0
        
        # Find the index of the last session if it exists
        if last_session_id:
            for session in existing_sessions:
                if session.session_id == last_session_id:
                    name = session.session_data.get("session_name", "Unnamed")
                    if name in session_options:
                        default_index = session_options.index(name)
                    break
        
        # Create session management expander
        with st.sidebar.expander("💬 Sessions", expanded=False):
            # Show session selector as radio buttons
            selected_option = st.radio(
                "Select a session",
                session_options,
                index=default_index,
                key="session_selector",
                label_visibility="collapsed"
            )
            
            # Handle session selection
            if selected_option == "➕ New Session":
                session_name = st.text_input("Enter a name for the new session", "", key="new_session_name")
                if session_name.strip():
                    if "last_session" not in st.session_state or st.session_state.last_session != "new":
                        st.session_state.last_session = "new"
                        self._save_last_session("")  # Clear last session when creating new
                        st.rerun()
                    return None, session_name.strip()
                st.warning("Please enter a session name")
                st.stop()
            else:
                # Get session ID from the mapping
                session_id = session_id_map[selected_option]
                session_name = selected_option
                
                # Create columns for each session's delete button
                col1, col2 = st.columns([6, 1])
                with col2:
                    if st.button("🗑️", key=f"delete_{session_id}", help="Delete this session"):
                        st.session_state.show_delete_confirm = True
                        st.session_state.delete_session_id = session_id
                        st.session_state.delete_session_name = session_name
                
                # Handle delete confirmation
                if st.session_state.get('show_delete_confirm', False) and st.session_state.get('delete_session_id') == session_id:
                    st.warning(f"Are you sure you want to delete session '{session_name}'?")
                    st.write("This action cannot be undone.")
                    col3, col4 = st.columns([1, 1])
                    with col3:
                        if st.button("Yes, Delete", type="primary", key=f"confirm_delete_{session_id}"):
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
                        if st.button("Cancel", type="secondary", key=f"cancel_delete_{session_id}"):
                            st.session_state.show_delete_confirm = False
                            st.rerun()
                
                if "last_session" not in st.session_state or st.session_state.last_session != session_id:
                    st.session_state.last_session = session_id
                    self._save_last_session(session_id)  # Save the selected session
                    st.rerun()
        
        # Display current session info outside the expander
        st.sidebar.markdown("---")
        st.sidebar.markdown(f"**Current Session:** {session_name}")
        
        # File uploader in expander
        with st.sidebar.expander("📎 Upload Files", expanded=False):
            # File uploader with callback - add PDF to accepted types
            _ = st.file_uploader(
                "Choose files",
                type=['png', 'jpg', 'jpeg', 'mp4', 'avi', '.mov', 'mp3', 'wav', 'txt', 'pdf'],
                accept_multiple_files=True,
                key="file_uploader",
                on_change=ChatbotUI.handle_file_upload
            )
        
        # Web search controls in expander
        with st.sidebar.expander("🔍 Web Search", expanded=False):
            use_web_search = st.checkbox("Use Web Search", value=False, key="use_web_search")
            num_pages = st.number_input(
                "Number of Pages to Search",
                min_value=1,
                max_value=10,
                value=3,
                key="num_pages",
                help="Number of web pages to search and summarize"
            )
        
        return session_id, session_name
    
    def render_chat(self, agent):
        """Render chat interface for the given agent"""
        if not agent:
            return
            
        # Display messages from agent memory
        if agent.memory and agent.memory.messages:
            for idx, msg in enumerate(agent.memory.messages):
                # Generate a unique message ID
                message_id = f"{msg.role}_{idx}"
                
                # Create columns for message and delete button
                msg_col, del_col = st.columns([20, 1])
                
                with msg_col:
                    with st.chat_message(msg.role):
                        # Format and display message content
                        preview, full_content = self.format_chat_message(msg.content)
                        if preview != full_content:
                            st.markdown(preview)
                            with st.expander("Show full message", expanded=False):
                                st.markdown(full_content)
                        else:
                            st.markdown(full_content)
                        
                        # Get metadata from session state or message object
                        metadata = st.session_state.message_metadata.get(message_id, {})
                        if not metadata and hasattr(msg, 'metadata') and msg.metadata:
                            metadata = msg.metadata
                            # Store in session state for persistence
                            st.session_state.message_metadata[message_id] = metadata
                            
                            # Also store in agent session data
                            if not hasattr(agent, 'session_data') or agent.session_data is None:
                                agent.session_data = {}
                            if 'message_metadata' not in agent.session_data:
                                agent.session_data['message_metadata'] = {}
                            agent.session_data['message_metadata'][message_id] = metadata.copy()  # Make a copy to prevent reference issues
                            # Ensure storage is updated
                            agent.write_to_storage()
                            print(f"Saved metadata to storage for message {message_id}: {metadata}")
                            
                        # Display media if present in metadata
                        if metadata:
                            # Log metadata for debugging
                            print(f"Message {idx} metadata from session state: {metadata}")
                            
                            media_refs = metadata.get('media_refs', [])
                            # Only show media expander if there are non-text media files
                            if self.has_non_text_media(media_refs):
                                with st.expander("📎 View Media", expanded=False):
                                    for media_ref in media_refs:
                                        if media_ref['type'] != 'text':  # Skip text files
                                            try:
                                                stored_path = self.manager.media_manager.get_media_path(media_ref['stored_path'])
                                                if stored_path.exists():
                                                    st.write(f"**{media_ref['original_name']}**")
                                                    if media_ref['type'] == 'image':
                                                        st.image(str(stored_path))
                                                    elif media_ref['type'] == 'video':
                                                        st.video(str(stored_path))
                                                    elif media_ref['type'] == 'audio':
                                                        st.audio(str(stored_path))
                                                else:
                                                    st.warning(f"Media file not found: {media_ref['original_name']}")
                                                    logger.warning(f"Media file not found at path: {stored_path}")
                                            except Exception as e:
                                                logger.error(f"Error displaying media {media_ref['original_name']}: {str(e)}")
                                                st.error(f"Unable to display media: {media_ref['original_name']}")
                
                # Show delete button for the message
                with del_col:
                    if st.button("🗑️", key=f"delete_msg_{idx}", help="Delete this message"):
                        # Remove message from memory and session state
                        agent.memory.messages.pop(idx)
                        if message_id in st.session_state.message_metadata:
                            del st.session_state.message_metadata[message_id]
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
            # Check if web search is enabled
            if st.session_state.use_web_search:
                with st.spinner("Searching the web..."):
                    # Add date and URL request to query
                    current_date = datetime.now().strftime("%Y-%m-%d")
                    web_query = f"Today's date is: {current_date}. {prompt} Include the source urls at the end of your summary."
                    
                    # Add user's query to memory
                    user_message = Message(role="user", content=prompt)
                    agent.memory.add_message(user_message)
                    
                    # Display user message
                    with st.chat_message("user"):
                        st.markdown(prompt)
                    
                    # Perform web search
                    web_results = summarize_web_search(web_query, st.session_state.num_pages)
                    
                    # Add web search results to memory
                    assistant_message = Message(role="assistant", content=web_results)
                    agent.memory.add_message(assistant_message)
                    
                    # Display assistant message
                    with st.chat_message("assistant"):
                        preview, full_content = self.format_chat_message(web_results)
                        if preview != full_content:
                            st.markdown(preview)
                            with st.expander("Show full response", expanded=False):
                                st.markdown(full_content)
                        else:
                            st.markdown(full_content)
                    
                    # Save the updated memory to storage
                    agent.write_to_storage()
                    
                    # Log conversation state after web search
                    self.manager._log_conversation_state(agent, "After web search")
                    return
            
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
                # Display original prompt first
                original_prompt = prompt.split("\nContent from")[0]
                preview, full_content = self.format_chat_message(original_prompt)
                if preview != full_content:
                    st.markdown(preview)
                    with st.expander("Show full message", expanded=False):
                        st.markdown(full_content)
                else:
                    st.markdown(full_content)
                
                # If there are text files, show them in an expander
                if "\nContent from" in prompt:
                    with st.expander("📄 Uploaded Text Content", expanded=False):
                        # Extract and display each text file content
                        text_parts = prompt.split("\nContent from")[1:]
                        for part in text_parts:
                            filename = part.split(":\n")[0]
                            content = part.split(":\n")[1]
                            st.markdown(f"**{filename}**")
                            st.text_area(
                                "",  # No label needed since we show filename above
                                value=content,
                                height=150,
                                disabled=True
                            )
                
                # Display media files and save metadata
                if media_objects['media_refs']:
                    # Only show media expander if there are non-text media files
                    if self.has_non_text_media(media_objects['media_refs']):
                        with st.expander("📎 View Media", expanded=True):
                            for media_ref in media_objects['media_refs']:
                                if media_ref['type'] != 'text':  # Skip text files
                                    try:
                                        stored_path = self.manager.media_manager.get_media_path(media_ref['stored_path'])
                                        if stored_path.exists():
                                            st.write(f"**{media_ref['original_name']}**")
                                            if media_ref['type'] == 'image':
                                                st.image(str(stored_path))
                                            elif media_ref['type'] == 'video':
                                                st.video(str(stored_path))
                                            elif media_ref['type'] == 'audio':
                                                st.audio(str(stored_path))
                                        else:
                                            st.warning(f"Media file not found: {media_ref['original_name']}")
                                            logger.warning(f"Media file not found at path: {stored_path}")
                                    except Exception as e:
                                        logger.error(f"Error displaying media {media_ref['original_name']}: {str(e)}")
                                        st.error(f"Unable to display media: {media_ref['original_name']}")
                    
                    # Save metadata for user message
                    message_id = f"user_{len(agent.memory.messages)}"
                    metadata = {
                        'media_refs': media_objects['media_refs'],
                        'has_media': True
                    }
                    self.manager.save_message_metadata(agent, message_id, metadata)
                    msg.metadata = metadata.copy()
            
            # Get and display bot response with streaming
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                full_response = ""
                
                # Add media references to message metadata
                metadata = None
                if media_objects['media_refs']:
                    metadata = {
                        'media_refs': media_objects['media_refs'],
                        'has_media': True  # Always set to True if we have media refs
                    }
                    # Store current media refs in session state
                    st.session_state.current_media_refs = media_objects['media_refs']
                    # Log metadata for debugging
                    print(f"Creating new message with metadata: {metadata}")
                
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
                        # Format the streaming response
                        preview, _ = self.format_chat_message(full_response)
                        message_placeholder.markdown(preview + "▌")
                
                # After streaming completes, store metadata for the new message
                if metadata:
                    message_id = f"assistant_{len(agent.memory.messages)}"
                    self.manager.save_message_metadata(agent, message_id, metadata)
                    msg.metadata = metadata.copy()
                
                # After streaming completes, show the full response with expander if needed
                preview, full_content = self.format_chat_message(full_response)
                if preview != full_content:
                    message_placeholder.markdown(preview)
                    with st.expander("Show full response", expanded=False):
                        st.markdown(full_content)
                else:
                    message_placeholder.markdown(full_content)
                
                # Log conversation state after response
                self.manager._log_conversation_state(agent, "After model response")
            
            # Manage context after each interaction
            #self.manager.manage_context(agent) 