"""
Media storage manager for handling multimodal content.
"""

from pathlib import Path
import shutil
import hashlib
import logging
from typing import Dict, Any
from uuid import uuid4

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class MediaManager:
    def __init__(self):
        self.media_dir = Path(__file__).parent.parent / "media_storage"
        self.media_dir.mkdir(exist_ok=True)
        logger.debug(f"Initialized MediaManager with media_dir: {self.media_dir}")
        
    def _generate_short_filename(self, file_hash: str, session_id: str, unique_id: str, file_ext: str) -> str:
        """Generate a short filename that complies with API limits while maintaining uniqueness"""
        # Use first 8 chars of hash, first 8 of session_id, and first 4 of unique_id
        short_name = f"{file_hash[:8]}_{session_id[:8]}_{unique_id[:4]}{file_ext}"
        logger.debug(f"Generated short filename: {short_name} (length: {len(short_name)})")
        return short_name
        
    def store_media(self, session_id: str, file_data: dict) -> dict:
        """Store media file with session-specific unique identifier using shortened names"""
        session_dir = self.media_dir / session_id
        session_dir.mkdir(exist_ok=True)
        logger.debug(f"Storing media in session directory: {session_dir}")
        
        # Create unique identifier for this file in this session
        file_hash = hashlib.md5(file_data['data']).hexdigest()
        unique_id = str(uuid4())
        file_ext = Path(file_data['name']).suffix
        
        # Generate shortened filename
        filename = self._generate_short_filename(file_hash, session_id, unique_id, file_ext)
        stored_path = session_dir / filename
        logger.debug(f"Generated stored path with shortened unique ID: {stored_path}")
        
        # Store the file
        with open(stored_path, 'wb') as f:
            f.write(file_data['data'])
        logger.debug(f"File written successfully: {stored_path}")
            
        return {
            'type': file_data['type'],
            'original_name': file_data['name'],
            'stored_path': str(stored_path.relative_to(self.media_dir)),
            'file_hash': file_hash,
            'unique_id': unique_id[:4],  # Store shortened unique_id
            'short_name': filename  # Store the short name for reference
        }
    
    def get_media_path(self, stored_path: str) -> Path:
        """Get the full path for a stored media file"""
        try:
            # Handle both absolute and relative paths
            if Path(stored_path).is_absolute():
                # If it's already an absolute path, check if it's within our media directory
                path = Path(stored_path)
                if not str(path).startswith(str(self.media_dir)):
                    logger.warning(f"Absolute path is outside media directory: {path}")
                    # Try to extract the relative part and reconstruct
                    try:
                        # Extract the session_id and filename from the path
                        parts = path.parts
                        if len(parts) >= 2:
                            # Assume the last two parts are session_id/filename
                            session_id = parts[-2]
                            filename = parts[-1]
                            corrected_path = self.media_dir / session_id / filename
                            logger.info(f"Corrected path to: {corrected_path}")
                            return corrected_path
                    except Exception as e:
                        logger.error(f"Failed to correct path: {e}")
                return path
            else:
                # It's a relative path, construct the full path
                full_path = self.media_dir / stored_path
                logger.debug(f"Resolved media path: {stored_path} -> {full_path}")
                return full_path
        except Exception as e:
            logger.error(f"Error resolving media path '{stored_path}': {e}")
            # Return the original path as a fallback
            return self.media_dir / stored_path
    
    def cleanup_session(self, session_id: str) -> None:
        """Remove all media files for a session"""
        session_dir = self.media_dir / session_id
        logger.debug(f"Attempting to cleanup session directory: {session_dir}")
        
        if session_dir.exists():
            logger.debug(f"Session directory exists, contains: {list(session_dir.glob('*'))}")
            try:
                shutil.rmtree(session_dir)
                logger.debug(f"Successfully deleted session directory: {session_dir}")
            except Exception as e:
                logger.error(f"Error deleting session directory: {e}", exc_info=True)
                raise
        else:
            logger.debug(f"Session directory does not exist: {session_dir}")
    
    def cleanup_file(self, stored_path: str) -> None:
        """Remove a specific media file"""
        file_path = self.media_dir / stored_path
        logger.debug(f"Attempting to delete file: {file_path}")
        if file_path.exists():
            try:
                file_path.unlink()
                logger.debug(f"Successfully deleted file: {file_path}")
            except Exception as e:
                logger.error(f"Error deleting file: {e}", exc_info=True)
                raise
        else:
            logger.debug(f"File does not exist: {file_path}")
            
    def serialize_media_ref(self, media_ref: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare media reference for storage"""
        return {
            'type': media_ref['type'],
            'original_name': media_ref['original_name'],
            'stored_path': media_ref['stored_path'],
            'file_hash': media_ref['file_hash'],
            'unique_id': media_ref.get('unique_id'),
            'short_name': media_ref.get('short_name')  # Include short_name in serialization
        } 